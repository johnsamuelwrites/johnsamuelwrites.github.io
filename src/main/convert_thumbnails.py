#
# SPDX-FileCopyrightText: 2025 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

#!/usr/bin/env python3
"""
Script to convert Wikimedia Commons thumbnail URLs to 1024x768 versions
"""

import re
from argparse import ArgumentParser


def convert_wikimedia_url(url):
    """
    Convert a Wikimedia Commons URL to use 1024px width thumbnail

    Examples:
    - /320px-Image.jpg -> /1024px-Image.jpg
    - /thumb/.../320px-Image.jpg -> /thumb/.../1024px-Image.jpg
    """
    # Pattern to match Wikimedia Commons thumbnail URLs with size
    # Matches: /NNNpx-filename or /thumb/.../NNNpx-filename
    pattern = r"/(\d+)px-([^/]+\.jpg)"

    # Replace with 1024px version
    new_url = re.sub(pattern, r"/1024px-\2", url)

    return new_url


def process_html_file(input_file, output_file):
    """
    Read HTML file, convert all Wikimedia Commons URLs, and write to output
    """
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Find all img src attributes with Wikimedia Commons URLs
        def replace_src(match):
            full_match = match.group(0)
            url = match.group(1)

            # Only convert if it's a Wikimedia Commons URL with a size specification
            if "wikimedia.org" in url and re.search(r"/\d+px-", url):
                new_url = convert_wikimedia_url(url)
                return f'src="{new_url}"'
            return full_match

        # Pattern to match img src attributes
        pattern = r'src="([^"]+)"'
        new_content = re.sub(pattern, replace_src, content)

        # Count how many URLs were changed
        original_urls = re.findall(r'src="[^"]*wikimedia\.org[^"]*"', content)
        new_urls = re.findall(r'src="[^"]*wikimedia\.org[^"]*"', new_content)

        changes = sum(1 for o, n in zip(original_urls, new_urls) if o != n)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"✅ Conversion complete!")
        print(f"   Input: {input_file}")
        print(f"   Output: {output_file}")
        print(f"   URLs converted: {changes}")

        if changes > 0:
            print("\n📝 Sample conversions:")
            for i, (old, new) in enumerate(zip(original_urls[:3], new_urls[:3])):
                if old != new:
                    print(f"   Before: ...{old[-60:]}")
                    print(f"   After:  ...{new[-60:]}")
                    print()

        return True

    except FileNotFoundError:
        print(f"❌ Error: File '{input_file}' not found")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def parse_args(argv=None):
    parser = ArgumentParser(
        description="Convert Wikimedia Commons thumbnail URLs to 1024px variants."
    )
    parser.add_argument("input_file", help="Input HTML file")
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Optional output HTML file. Defaults to '<input>-1024.html'.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    input_file = args.input_file

    # Determine output file
    if args.output_file:
        output_file = args.output_file
    else:
        # Auto-generate output filename
        if input_file.endswith(".html"):
            output_file = input_file[:-5] + "-1024.html"
        else:
            output_file = input_file + "-1024"

    success = process_html_file(input_file, output_file)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
