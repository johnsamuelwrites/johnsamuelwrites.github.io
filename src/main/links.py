#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Check the presence of broken links in one or more HTML files
"""
Broken Link Checker

This script checks HTML files for broken links, distinguishing between:
- External links (HTTP/HTTPS)
- Internal links (relative file paths)
- Anchor links (same-page fragments)
- Favicon links
- Style and script references
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class LinkType:
    """Enumeration of link types"""

    EXTERNAL = "external"
    INTERNAL = "internal"
    ANCHOR = "anchor"
    MAILTO = "mailto"
    JAVASCRIPT = "javascript"
    FAVICON = "favicon"
    STYLESHEET = "stylesheet"
    SCRIPT = "script"
    OTHER = "other"


class BrokenLink:
    """Represents a broken link with metadata"""

    def __init__(
        self,
        source_file: str,
        url: str,
        link_type: str,
        status_code: int = None,
        error: str = None,
    ):
        self.source_file = source_file
        self.url = url
        self.link_type = link_type
        self.status_code = status_code
        self.error = error

    def __str__(self):
        if self.status_code:
            return f"[{self.link_type.upper()}] {self.status_code}: {self.url}"
        elif self.error:
            return f"[{self.link_type.upper()}] ERROR: {self.url} - {self.error}"
        else:
            return f"[{self.link_type.upper()}] NOT FOUND: {self.url}"


class LinkChecker:
    """Main class for checking broken links in HTML files"""

    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 3,
        check_external: bool = True,
        check_internal: bool = True,
        check_favicon: bool = True,
        check_styles: bool = True,
        check_scripts: bool = True,
    ):
        """
        Initialize the LinkChecker

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for HTTP requests
            check_external: Whether to check external links
            check_internal: Whether to check internal links
            check_favicon: Whether to check favicon links
            check_styles: Whether to check stylesheet links
            check_scripts: Whether to check script links
        """
        self.timeout = timeout
        self.check_external = check_external
        self.check_internal = check_internal
        self.check_favicon = check_favicon
        self.check_styles = check_styles
        self.check_scripts = check_scripts
        self.session = self._create_session(max_retries)
        self.checked_urls: Dict[str, int] = {}  # Cache for external URLs

    def _create_session(self, max_retries: int) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set a reasonable user agent
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; LinkChecker/1.0; +https://github.com)"
            }
        )

        return session

    def classify_link(
        self, href: str, element_type: str = "a", rel: Optional[str] = None
    ) -> str:
        """
        Classify a link into its type

        Args:
            href: The href/src attribute value
            element_type: The HTML element type (a, link, script)
            rel: The rel attribute value (for link elements)

        Returns:
            LinkType constant
        """
        if not href or href.strip() == "":
            return LinkType.OTHER

        href = href.strip()

        # Check element-specific types
        if element_type == "link":
            if rel and "icon" in rel.lower():
                return LinkType.FAVICON
            if rel and "stylesheet" in rel.lower():
                return LinkType.STYLESHEET

        if element_type == "script":
            return LinkType.SCRIPT

        # Anchor links
        if href.startswith("#"):
            return LinkType.ANCHOR

        # Mailto links
        if href.startswith("mailto:"):
            return LinkType.MAILTO

        # JavaScript links
        if href.startswith("javascript:"):
            return LinkType.JAVASCRIPT

        # Parse URL to determine if external or internal
        parsed = urlparse(href)

        # External links (with scheme)
        if parsed.scheme in ("http", "https"):
            return LinkType.EXTERNAL

        # Internal links (relative paths or file protocol)
        if parsed.scheme == "" or parsed.scheme == "file":
            return LinkType.INTERNAL

        return LinkType.OTHER

    def check_external_link(self, url: str) -> tuple:
        """
        Check if an external URL is accessible

        Args:
            url: The URL to check

        Returns:
            Tuple of (is_broken, status_code, error_message)
        """
        # Check cache first
        if url in self.checked_urls:
            cached_status = self.checked_urls[url]
            return (cached_status != 200, cached_status, None)

        try:
            # Use HEAD request first (faster)
            response = self.session.head(
                url, timeout=self.timeout, allow_redirects=True
            )
            status_code = response.status_code

            # Some servers don't support HEAD, try GET
            if status_code == 405:
                response = self.session.get(
                    url, timeout=self.timeout, allow_redirects=True, stream=True
                )
                status_code = response.status_code
                response.close()

            # Cache the result
            self.checked_urls[url] = status_code

            # Consider 2xx and 3xx as success
            is_broken = status_code >= 400
            return (is_broken, status_code, None)

        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            self.checked_urls[url] = 0
            return (True, None, error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error"
            self.checked_urls[url] = 0
            return (True, None, error_msg)
        except requests.exceptions.TooManyRedirects:
            error_msg = "Too many redirects"
            self.checked_urls[url] = 0
            return (True, None, error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            self.checked_urls[url] = 0
            return (True, None, error_msg)

    def check_internal_link(self, filepath: str, href: str) -> tuple:
        """
        Check if an internal file link exists

        Args:
            filepath: Path to the source HTML file
            href: The href attribute value

        Returns:
            Tuple of (is_broken, error_message)
        """
        try:
            # Get directory of the source file
            source_dir = Path(filepath).parent.resolve()

            # Parse the href to separate path and fragment
            parsed = urlparse(href)
            link_path = parsed.path

            # Handle empty path
            if not link_path:
                return (False, None)

            # Resolve the target path
            target_path = (source_dir / link_path).resolve()

            # Check if file exists
            if not target_path.exists():
                return (True, "File not found")

            # Check if it's a file (not directory)
            if not target_path.is_file():
                return (True, "Path is not a file")

            return (False, None)

        except Exception as e:
            return (True, str(e))

    def check_file(self, filepath: str) -> List[BrokenLink]:
        """
        Check all links in a single HTML file

        Args:
            filepath: Path to the HTML file

        Returns:
            List of BrokenLink objects
        """
        broken_links = []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with latin-1 encoding as fallback
            try:
                with open(filepath, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Cannot read file {filepath}: {e}")
                return broken_links
        except Exception as e:
            logger.error(f"Cannot read file {filepath}: {e}")
            return broken_links

        # Parse HTML
        try:
            soup = BeautifulSoup(content, "html.parser")
        except Exception as e:
            logger.error(f"Cannot parse HTML in {filepath}: {e}")
            return broken_links

        # Check regular anchor links
        links = soup.find_all("a", href=True)
        for link in links:
            href = link.get("href")
            if not href:
                continue

            link_type = self.classify_link(href, element_type="a")
            broken_link = self._check_single_link(filepath, href, link_type)
            if broken_link:
                broken_links.append(broken_link)

        # Check favicon and stylesheet links in <head>
        if self.check_favicon or self.check_styles:
            link_elements = soup.find_all("link", href=True)
            for link_elem in link_elements:
                href = link_elem.get("href")
                rel = link_elem.get("rel")
                if not href:
                    continue

                # Convert rel list to string if needed
                rel_str = " ".join(rel) if isinstance(rel, list) else (rel or "")

                link_type = self.classify_link(href, element_type="link", rel=rel_str)

                # Skip if we're not checking this type
                if link_type == LinkType.FAVICON and not self.check_favicon:
                    continue
                if link_type == LinkType.STYLESHEET and not self.check_styles:
                    continue

                broken_link = self._check_single_link(filepath, href, link_type)
                if broken_link:
                    broken_links.append(broken_link)

        # Check script links in <head>
        if self.check_scripts:
            script_elements = soup.find_all("script", src=True)
            for script_elem in script_elements:
                src = script_elem.get("src")
                if not src:
                    continue

                link_type = self.classify_link(src, element_type="script")
                broken_link = self._check_single_link(filepath, src, link_type)
                if broken_link:
                    broken_links.append(broken_link)

        return broken_links

    def _check_single_link(
        self, filepath: str, href: str, link_type: str
    ) -> Optional[BrokenLink]:
        """
        Check a single link and return BrokenLink if broken

        Args:
            filepath: Source file path
            href: The link URL
            link_type: Type of link

        Returns:
            BrokenLink object if broken, None otherwise
        """
        # Skip certain link types
        if link_type in (
            LinkType.ANCHOR,
            LinkType.MAILTO,
            LinkType.JAVASCRIPT,
            LinkType.OTHER,
        ):
            return None

        # Check external links
        if link_type in (LinkType.EXTERNAL,) and self.check_external:
            is_broken, status_code, error = self.check_external_link(href)
            if is_broken:
                return BrokenLink(filepath, href, link_type, status_code, error)

        # Check internal links (includes favicon, stylesheet, script if internal)
        elif link_type in (
            LinkType.INTERNAL,
            LinkType.FAVICON,
            LinkType.STYLESHEET,
            LinkType.SCRIPT,
        ):
            # Determine if it's an external resource
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https"):
                # It's an external resource
                if self.check_external:
                    is_broken, status_code, error = self.check_external_link(href)
                    if is_broken:
                        return BrokenLink(filepath, href, link_type, status_code, error)
            else:
                # It's an internal resource
                if self.check_internal:
                    is_broken, error = self.check_internal_link(filepath, href)
                    if is_broken:
                        return BrokenLink(filepath, href, link_type, error=error)

        return None

    def check_files(
        self, filepaths: List[str], recursive: bool = False
    ) -> Dict[str, List[BrokenLink]]:
        """
        Check all links in multiple HTML files

        Args:
            filepaths: List of paths to HTML files or directories
            recursive: Whether to recursively scan directories

        Returns:
            Dictionary mapping filepaths to lists of broken links
        """
        results = {}
        html_files = []

        # Collect all HTML files
        for filepath in filepaths:
            if not os.path.exists(filepath):
                logger.error(f"Path not found: {filepath}")
                continue

            if os.path.isfile(filepath):
                # Single file
                html_files.append(filepath)
            elif os.path.isdir(filepath):
                # Directory - scan for HTML files
                html_files.extend(self._scan_directory(filepath, recursive))
            else:
                logger.error(f"Invalid path: {filepath}")

        # Check each HTML file
        for filepath in html_files:
            logger.info(f"Checking: {filepath}")
            broken_links = self.check_file(filepath)

            if broken_links:
                results[filepath] = broken_links

        return results

    def _scan_directory(self, directory: str, recursive: bool) -> List[str]:
        """
        Scan a directory for HTML files

        Args:
            directory: Directory path to scan
            recursive: Whether to scan recursively

        Returns:
            List of HTML file paths
        """
        html_files = []
        dir_path = Path(directory)

        # HTML file extensions to look for
        html_extensions = {".html", ".htm", ".xhtml"}

        if recursive:
            # Recursive scan
            for file_path in dir_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in html_extensions:
                    html_files.append(str(file_path))
        else:
            # Non-recursive scan (only immediate directory)
            for file_path in dir_path.glob("*"):
                if file_path.is_file() and file_path.suffix.lower() in html_extensions:
                    html_files.append(str(file_path))

        return sorted(html_files)


def print_results(
    results: Dict[str, List[BrokenLink]],
    show_external: bool = True,
    show_internal: bool = True,
    show_favicon: bool = True,
    show_styles: bool = True,
    show_scripts: bool = True,
):
    """
    Print the results in a formatted manner

    Args:
        results: Dictionary of broken links per file
        show_external: Whether to show external broken links
        show_internal: Whether to show internal broken links
        show_favicon: Whether to show broken favicon links
        show_styles: Whether to show broken stylesheet links
        show_scripts: Whether to show broken script links
    """
    if not results:
        print("\n✓ No broken links found!")
        return

    total_broken = sum(len(links) for links in results.values())
    external_count = sum(
        1
        for links in results.values()
        for link in links
        if link.link_type == LinkType.EXTERNAL
    )
    internal_count = sum(
        1
        for links in results.values()
        for link in links
        if link.link_type == LinkType.INTERNAL
    )
    favicon_count = sum(
        1
        for links in results.values()
        for link in links
        if link.link_type == LinkType.FAVICON
    )
    stylesheet_count = sum(
        1
        for links in results.values()
        for link in links
        if link.link_type == LinkType.STYLESHEET
    )
    script_count = sum(
        1
        for links in results.values()
        for link in links
        if link.link_type == LinkType.SCRIPT
    )

    print(f"\n{'='*70}")
    print(f"BROKEN LINKS SUMMARY")
    print(f"{'='*70}")
    print(f"Total broken links: {total_broken}")
    print(f"  - External: {external_count}")
    print(f"  - Internal: {internal_count}")
    print(f"  - Favicon: {favicon_count}")
    print(f"  - Stylesheet: {stylesheet_count}")
    print(f"  - Script: {script_count}")
    print(f"{'='*70}\n")

    for filepath, broken_links in results.items():
        print(f"\n{'='*70}")
        print(f"FILE: {filepath}")
        print(f"{'='*70}")

        for link in broken_links:
            show_link = False
            if link.link_type == LinkType.EXTERNAL and show_external:
                show_link = True
            elif link.link_type == LinkType.INTERNAL and show_internal:
                show_link = True
            elif link.link_type == LinkType.FAVICON and show_favicon:
                show_link = True
            elif link.link_type == LinkType.STYLESHEET and show_styles:
                show_link = True
            elif link.link_type == LinkType.SCRIPT and show_scripts:
                show_link = True

            if show_link:
                print(f"  {link}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Check for broken links in HTML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s index.html
  %(prog)s *.html
  %(prog)s --recursive docs/
  %(prog)s --no-external index.html
  %(prog)s --no-internal index.html
  %(prog)s --no-favicon --no-styles --no-scripts index.html
  %(prog)s --timeout 5 index.html
        """,
    )

    parser.add_argument(
        "files",
        metavar="FILE",
        type=str,
        nargs="+",
        help="HTML file(s) or directory to check",
    )

    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan directories for HTML files",
    )

    parser.add_argument(
        "--no-external", action="store_true", help="Skip checking external links"
    )

    parser.add_argument(
        "--no-internal", action="store_true", help="Skip checking internal links"
    )

    parser.add_argument(
        "--no-favicon", action="store_true", help="Skip checking favicon links"
    )

    parser.add_argument(
        "--no-styles", action="store_true", help="Skip checking stylesheet links"
    )

    parser.add_argument(
        "--no-scripts", action="store_true", help="Skip checking script links"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout for external requests in seconds (default: 10)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries for failed requests (default: 3)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Validate arguments
    if not args.files:
        parser.print_usage()
        sys.exit(1)

    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Create checker
    checker = LinkChecker(
        timeout=args.timeout,
        max_retries=args.max_retries,
        check_external=not args.no_external,
        check_internal=not args.no_internal,
        check_favicon=not args.no_favicon,
        check_styles=not args.no_styles,
        check_scripts=not args.no_scripts,
    )

    # Check files
    results = checker.check_files(args.files, recursive=args.recursive)

    # Print results
    print_results(
        results,
        show_external=not args.no_external,
        show_internal=not args.no_internal,
        show_favicon=not args.no_favicon,
        show_styles=not args.no_styles,
        show_scripts=not args.no_scripts,
    )

    # Exit with error code if broken links found
    if results:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
