#!/usr/bin/env python3
"""Audit translations changed since a Git revision against live Wikibase.

Labels must already agree with the reviewed repository values. Only existing
P40 statements on atomic content items are updated; statement IDs, qualifiers,
references and ranks are preserved. Default mode writes a review report only.
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from paths import REPO_ROOT
from wikibase_api import DEFAULT_API, WikibaseClient
from wikibase_write import load_env
from abstract.normalize_untranslatable_names import sign_in, write_with_retry
from languages import ORDER as LANGUAGES
from abstract.local_text import local_text_qids

LABELS = 'src/main/abstract/data/labels-wikibase.csv'


def changed_values(before: str, after: str) -> dict[str, dict[str, str]]:
    old = {r['identifier']: r for r in csv.DictReader(io.StringIO(before))}
    result = {}
    for row in csv.DictReader(io.StringIO(after)):
        qid = row['identifier']
        values = {lang: row[lang] for lang in LANGUAGES
                  if row.get(lang) and row[lang] != old.get(qid, {}).get(lang, '')}
        if values:
            result[qid] = values
    return result


def plan(entity: dict, values: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Return safe in-place claim edits and reasons needing manual review."""
    claims = entity.get('claims', {})
    types = {c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id')
             for c in claims.get('P8', [])}
    edits, blocked = [], []
    if 'missing' in entity:
        return [], ['missing entity']
    for lang, wanted in values.items():
        if entity.get('labels', {}).get(lang, {}).get('value') != wanted:
            blocked.append(f'{lang}: live label differs from reviewed value')
            continue
        statements = [c for c in claims.get('P40', [])
                      if c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('language') == lang]
        if not statements:
            continue  # Entity labels need not carry content statements.
        if len(statements) != 1:
            blocked.append(f'{lang}: multiple P40 statements')
            continue
        claim = statements[0]
        if claim['mainsnak']['datavalue']['value']['text'] == wanted:
            continue
        if 'Q3185' not in types or types & {'Q3835', 'Q3836'}:
            blocked.append(f'{lang}: non-atomic content')
            continue
        if not claim.get('id') or len(wanted) > 400:
            blocked.append(f'{lang}: missing statement ID or oversized content')
            continue
        replacement = copy.deepcopy(claim)
        replacement['mainsnak']['datavalue']['value']['text'] = wanted
        edits.append(replacement)
    return edits, blocked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--since', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    before = subprocess.check_output(['git', 'show', f'{args.since}:{LABELS}'],
                                     cwd=REPO_ROOT, text=True)
    changed = changed_values(before, (REPO_ROOT / LABELS).read_text())
    excluded = local_text_qids()
    changed = {qid: values for qid, values in changed.items() if qid not in excluded}
    load_env(REPO_ROOT / '.env')
    client = WikibaseClient(os.getenv('WIKIBASE_API', DEFAULT_API),
                            pause=0.5 if args.apply else 0)
    report = {'since': args.since, 'items_checked': len(changed),
              'values_checked': sum(map(len, changed.values())), 'changes': [], 'blocked': []}
    planned = {}
    ids = list(changed)
    for start in range(0, len(ids), 50):
        entities = client.entities(ids[start:start + 50])
        for qid in ids[start:start + 50]:
            entity = entities.get(qid, {'missing': True})
            edits, blocked = plan(entity, changed[qid])
            report['blocked'].extend({'qid': qid, 'reason': reason} for reason in blocked)
            if edits:
                planned[qid] = edits
                originals = {c['id']: c for c in entity['claims']['P40']}
                for edit in edits:
                    value = edit['mainsnak']['datavalue']['value']
                    report['changes'].append({'qid': qid, 'statement': edit['id'],
                        'language': value['language'], 'before': originals[edit['id']]['mainsnak']['datavalue']['value']['text'],
                        'after': value['text']})
        print(f'Checked {min(start + 50, len(ids))}/{len(ids)}', flush=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"{len(report['changes'])} P40 corrections on {len(planned)} items; {len(report['blocked'])} blocked values", flush=True)
    if report['blocked']:
        return 1
    if args.apply and planned:
        sign_in(client)
        for index, (qid, edits) in enumerate(planned.items(), 1):
            # Re-read immediately before writing; never use an outdated claim.
            fresh, blocked = plan(client.entities([qid])[qid], changed[qid])
            if blocked:
                raise RuntimeError(f'{qid}: {blocked}')
            if fresh and not write_with_retry(client, qid, {'claims': fresh},
                    f'Align P40 with reviewed translations since {args.since[:12]}'):
                raise RuntimeError(f'Failed to update {qid}; rerun to resume')
            print(f'Updated {index}/{len(planned)}: {qid}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
