#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

START = "-- СКАРОТЫ:"
END = "-- АЛЬФАБЭТ:"


def split_abbreviations(source):
    lines = source.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(START) + 1
        end = lines.index(END)
    except ValueError as exc:
        raise SystemExit(f"{source}: missing abbreviation section marker") from exc

    abbreviations = {}
    for line in lines[start:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(" - ")
        if not sep:
            raise SystemExit(f"{source}: bad abbreviation row: {line!r}")
        abbreviations[key] = value
    return abbreviations


def self_check():
    data = split_abbreviations(Path("vbrs.txt"))
    assert data["м."] == "мужчынскі род (masculinus)"
    assert data["чэс."] == "чэскае"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="vbrs.txt")
    parser.add_argument("--out", default="json/abbreviations.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        self_check()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = split_abbreviations(Path(args.source))
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(data)} abbreviations")


if __name__ == "__main__":
    main()
