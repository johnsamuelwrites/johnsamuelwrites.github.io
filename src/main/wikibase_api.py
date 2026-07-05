#!/usr/bin/env python3
"""Small dependency-free MediaWiki/Wikibase API client."""

from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable


DEFAULT_API = "https://jsamwrites.wikibase.cloud/w/api.php"
USER_AGENT = "johnsamuelwrites-wikibase-bot/1.0"


class WikibaseError(RuntimeError):
    """An error returned by MediaWiki or its transport."""


class WikibaseClient:
    def __init__(
        self, api: str = DEFAULT_API, *, timeout: int = 30,
        retries: int = 3, pause: float = 0.0,
    ) -> None:
        self.api = api
        self.timeout = timeout
        self.retries = retries
        self.pause = pause
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )
        self.csrf_token: str | None = None

    def request(self, params: dict[str, Any], *, post: bool = False) -> dict:
        values = {"format": "json", "formatversion": "2", **params}
        encoded = urllib.parse.urlencode(values).encode()
        url = self.api if post else f"{self.api}?{encoded.decode()}"
        request = urllib.request.Request(
            url,
            data=encoded if post else None,
            headers={"User-Agent": USER_AGENT},
        )
        for attempt in range(self.retries + 1):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                if "error" in payload:
                    error = payload["error"]
                    raise WikibaseError(
                        f"{error.get('code', 'api-error')}: "
                        f"{error.get('info', error)}"
                    )
                if self.pause:
                    time.sleep(self.pause)
                return payload
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == self.retries:
                    raise WikibaseError(f"request failed: {exc}") from exc
                time.sleep(min(2 ** attempt, 8))
        raise AssertionError("unreachable")

    def login(self, username: str, password: str) -> None:
        token = self.request(
            {"action": "query", "meta": "tokens", "type": "login"}
        )["query"]["tokens"]["logintoken"]
        result = self.request(
            {
                "action": "login",
                "lgname": username,
                "lgpassword": password,
                "lgtoken": token,
            },
            post=True,
        ).get("login", {})
        if result.get("result") != "Success":
            raise WikibaseError(f"login failed: {result.get('reason', result)}")
        self.csrf_token = self.request(
            {"action": "query", "meta": "tokens"}
        )["query"]["tokens"]["csrftoken"]

    def edit_entity(
        self, data: dict, *, entity_id: str | None = None,
        summary: str = "Automated import", create_type: str = "item",
    ) -> dict:
        if not self.csrf_token:
            raise WikibaseError("login is required before writing")
        params: dict[str, Any] = {
            "action": "wbeditentity",
            "token": self.csrf_token,
            "data": json.dumps(data, ensure_ascii=False),
            "summary": summary,
            "bot": 1,
            "assert": "user",
        }
        params["id" if entity_id else "new"] = entity_id or create_type
        return self.request(params, post=True)

    def entities(self, ids: Iterable[str]) -> dict[str, dict]:
        entity_ids = list(ids)
        result: dict[str, dict] = {}
        for start in range(0, len(entity_ids), 50):
            payload = self.request({
                "action": "wbgetentities",
                "ids": "|".join(entity_ids[start:start + 50]),
                "props": "info|labels|descriptions|aliases|claims|sitelinks",
            })
            result.update(payload.get("entities", {}))
        return result

    def all_entity_ids(self, namespaces: Iterable[int]) -> list[str]:
        ids: list[str] = []
        for namespace in namespaces:
            continuation: dict[str, Any] = {}
            while True:
                payload = self.request({
                    "action": "query",
                    "list": "allpages",
                    "apnamespace": namespace,
                    "aplimit": "max",
                    **continuation,
                })
                ids.extend(
                    page["title"].removeprefix("Property:")
                    for page in payload["query"]["allpages"]
                )
                if "continue" not in payload:
                    break
                continuation = payload["continue"]
        return ids
