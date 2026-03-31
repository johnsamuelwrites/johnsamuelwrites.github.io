#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
import argparse
import re

from file_rewrite import rewrite_text_file


SECTION_RE = re.compile(
    r'<section class="slide" id="slide\d+">.*?</section>',
    re.IGNORECASE | re.DOTALL,
)
SECTION_ID_RE = re.compile(r'(<section class="slide" id="slide)\d+(">)', re.IGNORECASE)
NAVIGATION_NUMBER_RE = re.compile(r'(<div class="navigation">\s*)\d+', re.IGNORECASE)
PAGE_NUMBER_RE = re.compile(
    r'(<span class="page-number">\s*)\d+(?:\s*/\s*\d+)?(\s*</span>)',
    re.IGNORECASE,
)
PREV_RE = re.compile(r'(<a class="prev" href="#slide)\d+(">)', re.IGNORECASE)
NEXT_RE = re.compile(r'(<a class="next" href="#slide)\d+(">)', re.IGNORECASE)
NAV_BUTTON_RE = re.compile(r'(<a class="nav-btn" href="#slide)\d+(">)', re.IGNORECASE)
SCRIPT_MAX_SLIDE_RE = re.compile(r'(if\s*\(\s*slideId\s*<\s*)\d+(\s*\)\s*\{)')


def _replace_nav_button(match, slide_number):
    return f"{match.group(1)}{slide_number}{match.group(2)}"


def _update_nav_buttons(section_text, slide_number, total_slides):
    nav_matches = list(NAV_BUTTON_RE.finditer(section_text))
    if not nav_matches:
        return section_text

    replacements = []
    if len(nav_matches) >= 2:
        replacements.append((nav_matches[0], max(1, slide_number - 1)))
        replacements.append((nav_matches[1], min(total_slides, slide_number + 1)))
    elif slide_number == 1:
        replacements.append((nav_matches[0], min(total_slides, slide_number + 1)))
    else:
        replacements.append((nav_matches[0], max(1, slide_number - 1)))

    updated = []
    last_index = 0
    replacement_by_span = {
        (match.start(), match.end()): target for match, target in replacements
    }
    for match in nav_matches:
        updated.append(section_text[last_index:match.start()])
        target = replacement_by_span.get((match.start(), match.end()))
        if target is None:
            updated.append(match.group(0))
        else:
            updated.append(_replace_nav_button(match, target))
        last_index = match.end()
    updated.append(section_text[last_index:])
    return "".join(updated)


def _renumber_section(section_text, slide_number, total_slides):
    section_text = SECTION_ID_RE.sub(
        lambda match: f'{match.group(1)}{slide_number}{match.group(2)}',
        section_text,
        count=1,
    )
    section_text = NAVIGATION_NUMBER_RE.sub(
        lambda match: f"{match.group(1)}{slide_number}",
        section_text,
        count=1,
    )
    section_text = PAGE_NUMBER_RE.sub(
        lambda match: f"{match.group(1)}{slide_number} / {total_slides}{match.group(2)}",
        section_text,
        count=1,
    )
    section_text = PREV_RE.sub(
        lambda match: f'{match.group(1)}{max(1, slide_number - 1)}{match.group(2)}',
        section_text,
        count=1,
    )
    section_text = NEXT_RE.sub(
        lambda match: f'{match.group(1)}{min(total_slides, slide_number + 1)}{match.group(2)}',
        section_text,
        count=1,
    )
    return _update_nav_buttons(section_text, slide_number, total_slides)


def _renumber_content(content):
    sections = list(SECTION_RE.finditer(content))
    total_slides = len(sections)
    if not sections:
        return content

    updated_parts = []
    last_index = 0
    for slide_number, match in enumerate(sections, start=1):
        updated_parts.append(content[last_index:match.start()])
        updated_parts.append(
            _renumber_section(match.group(0), slide_number, total_slides)
        )
        last_index = match.end()
    updated_parts.append(content[last_index:])

    updated_content = "".join(updated_parts)
    return SCRIPT_MAX_SLIDE_RE.sub(
        lambda match: f"{match.group(1)}{total_slides}{match.group(2)}",
        updated_content,
        count=1,
    )


def enumerate_slides(filename):
    rewrite_text_file(filename, _renumber_content)


def modify_files(files):
    for filename in files:
        enumerate_slides(filename)

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Numbering the slides")
    parser.add_argument("files", metavar="F", type=str, nargs="+", help="HTML file")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    modify_files(args.files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
