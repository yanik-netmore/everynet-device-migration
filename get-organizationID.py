#!/usr/bin/env python3

import argparse
import json
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search an organizations JSON file by name and print its ID."
    )
    parser.add_argument(
        "-i", "--infile",
        required=True,
        help="Path to the organizations JSON file.",
    )
    parser.add_argument(
        "-org", "--org",
        required=True,
        help="Organization name to search for (case-insensitive).",
    )
    return parser.parse_args()


def load_organizations(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("organizations", "results", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Cannot find organization list in '{path}'.")


def main() -> int:
    args = parse_args()

    try:
        orgs = load_organizations(args.infile)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error loading file: {exc}", file=sys.stderr)
        return 1

    needle = args.org.lower()
    total = len(orgs)
    matches = [
        (i + 1, o) for i, o in enumerate(orgs)
        if isinstance(o, dict) and needle in o.get("name", "").lower()
    ]

    if not matches:
        print(f"No organization found matching '{args.org}'.", file=sys.stderr)
        return 1

    for pos, org in matches:
        print(f"{org['id']}\t{org['name']}\t({pos}/{total})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
