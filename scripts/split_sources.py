#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from split_vbrs import normalize_space, pull_parentheses

SOURCE_MARKER = "-- КРЫНІЦЫ:"
ABBREVIATIONS_MARKER = "-- СКАРОТЫ:"
SOURCE_CODE_RE = re.compile(r"^\[([^\]]+)\]\s*-\s*(.*)$")
YEAR_RE = re.compile(r"\b\d{4}(?:\s*[-—]\s*(?:\d{4}|выданне працягваецца)|\+)?\b")
NON_PLACE_RE = re.compile(r"выпуск|част|том|кн|варыянт|вариант|выдан", re.I)


def looks_like_person(text):
    words = text.replace(",", " ").split()
    return bool(words) and (
        any(re.match(r"^[А-ЯA-ZІЎЁ]\.", word) for word in words)
        or (len(words) in {2, 3} and all(word[:1].isupper() for word in words))
    )


def parse_source_text(text):
    title_text, notes = pull_parentheses(text)
    years = YEAR_RE.findall(text)
    places = []
    note_authors = []
    for note in notes:
        if " - " in note:
            author, _ = note.rsplit(" - ", 1)
            if looks_like_person(author):
                note_authors.append(author)
        elif not YEAR_RE.search(note):
            note_authors.extend(
                part.strip()
                for part in note.split(",")
                if looks_like_person(part.strip())
            )
            continue

        if YEAR_RE.search(note):
            parts = [part.strip() for part in note.rsplit(" - ", 1)[-1].split(",")]
            places.extend(
                part
                for part in parts
                if part and not YEAR_RE.search(part) and not NON_PLACE_RE.search(part)
            )

    chunks = [chunk.strip() for chunk in title_text.split(". ")]
    authors = []
    while (
        len(chunks) > 1
        and re.fullmatch(r"[^\d:()]{2,60}", chunks[0])
        and len(chunks[0].split()) <= 4
    ):
        authors.append(chunks.pop(0))
    authors.extend(note_authors)

    return {
        "title": normalize_space(". ".join(chunks) if chunks else title_text),
        "authors": list(dict.fromkeys(authors)),
        "years": years,
        "places": list(dict.fromkeys(places)),
        "notes": notes,
    }


def split_preface(vbrs_source):
    lines = vbrs_source.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(SOURCE_MARKER) + 1
        end = lines.index(ABBREVIATIONS_MARKER)
    except ValueError as exc:
        raise SystemExit(f"{vbrs_source}: missing source-code section marker") from exc

    rows = []
    for line_number, line in enumerate(lines[start:end], start + 1):
        match = SOURCE_CODE_RE.match(line)
        if match:
            rows.append(
                {
                    "line": line_number,
                    "raw": line,
                    "code": match.group(1),
                    **parse_source_text(match.group(2)),
                }
            )
    return rows


def split_krynicy(source):
    rows = []
    section = None
    for line_number, line in enumerate(
        source.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        if line.startswith("-- ") and line.endswith(":"):
            section = line[3:-1].strip()
            continue
        rows.append(
            {
                "line": line_number,
                "section": section,
                "raw": line,
                **parse_source_text(line),
            }
        )
    return rows


def self_check():
    source = parse_source_text(
        "Іван Насовіч. Словарь бѣлорусскаго нарѣчія (Носовичъ И. - Санкт-Петербург, 1870)"
    )
    assert source["authors"] == ["Іван Насовіч", "Носовичъ И."]
    assert source["title"] == "Словарь бѣлорусскаго нарѣчія"
    assert source["years"] == ["1870"]
    assert source["places"] == ["Санкт-Петербург"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vbrs", default="vbrs.txt")
    parser.add_argument("--krynicy", default="krynicy.vbrs.txt")
    parser.add_argument("--out", default="json/sources")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        self_check()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preface = split_preface(Path(args.vbrs))
    krynicy = split_krynicy(Path(args.krynicy))
    (out / "preface.json").write_text(
        json.dumps(preface, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "krynicy.json").write_text(
        json.dumps(krynicy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(preface)} preface sources and {len(krynicy)} krynicy sources")


if __name__ == "__main__":
    main()
