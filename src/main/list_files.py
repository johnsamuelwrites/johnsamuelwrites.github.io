import argparse
from pathlib import Path
from typing import Iterable


def list_contents(target_dir: str | Path, recursive: bool = False) -> list[Path]:
    path = Path(target_dir)

    if not path.exists():
        raise FileNotFoundError(f"The path '{target_dir}' does not exist.")

    # Select the search pattern: '**/*' for recursive, '*' for current dir
    search_pattern = "**/*" if recursive else "*"

    # Collect files
    files: list[Path] = [
        item for item in path.glob(search_pattern) if item.is_file()
    ]
    return files


def format_listing(files: Iterable[Path], root: Path, recursive: bool) -> str:
    header = f"{'Recursive' if recursive else 'Simple'} listing for: {root.absolute()}\n"
    body_lines = [str(p) for p in files]
    return header + "\n".join(body_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="List files in a directory.")

    # Positional argument for the directory path (defaults to current directory)
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="The directory to list.",
    )

    # Optional flag for recursion
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="List files recursively.",
    )

    # 1. Option: explicitly print the target directory
    parser.add_argument(
        "--print-target-dir",
        action="store_true",
        help="Print the absolute target directory path before listing.",
    )

    # 2. Option: write output to a file instead of stdout (or in addition)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write the listing to this output file instead of only printing.",
    )

    args = parser.parse_args()

    root = Path(args.path)

    try:
        files = list_contents(root, args.recursive)
    except FileNotFoundError as exc:
        # Keep CLI-friendly error handling
        print(f"Error: {exc}")
        return

    listing_text = format_listing(files, root, args.recursive)

    # Print target dir if requested
    if args.print_target_dir:
        print(root.absolute())

    # Always print listing to stdout (can be changed to 'if not args.output' if desired)
    print(listing_text)

    # Optionally write to file
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(listing_text, encoding="utf-8")


if __name__ == "__main__":
    main()
