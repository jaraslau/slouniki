#!/usr/bin/env python3
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

MARKER = "-- СЛОВЫ:"
SAYINGS_MARKER = "-- ВЫСЛОЎІ, ПАРАЎНАНЬНІ, ПРЫКАЗКІ Й ПРЫМАЎКІ:"
ENTRY_RE = re.compile(
    r"^(?P<head>.+?)\s+/(?P<latin>[^/]*)/\s*(?P<op>[-–—=])\s*(?P<body>.*)$"
)
TAG_RE = re.compile(r"м\.|ж\.|н\.|а\.|мн\.|ул\.")
TAG_GROUP_RE = re.compile(r"(?:(?:м|ж|н|а|мн|ул)\.)+$")
SOURCE_RE = re.compile(r"\[([^\]]+)\]")
DEF_RE = re.compile(r"(?:^|;\s*)(\d+\??)\)\s*")
LINK_RE = re.compile(r'гл\.?\s*"?([^")]+)"?')
SAYING_DEF_RE = re.compile(r"(?:^|;\s*)(\d+\??)\)\s*")


def normalize_space(text):
    return re.sub(r"\s+", " ", text).strip(" ;")


def pull_parentheses(text):
    notes = []
    spans = []
    stack = []
    for i, char in enumerate(text):
        if char == "(":
            stack.append(i)
        elif char == ")" and stack:
            start = stack.pop()
            if not stack:
                spans.append((start, i + 1))
                notes.append(text[start + 1 : i])

    cleaned = []
    last = 0
    for start, end in spans:
        cleaned.append(text[last:start])
        last = end
    cleaned.append(text[last:])
    return normalize_space("".join(cleaned)), [
        note.strip() for note in notes if note.strip()
    ]


def split_definitions(text):
    matches = list(DEF_RE.finditer(text))
    if not matches:
        cleaned, notes = pull_parentheses(text)
        return (
            [{"number": None, "text": cleaned, "ru_notes": notes}]
            if cleaned or notes
            else []
        )

    definitions = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        cleaned, notes = pull_parentheses(text[match.end() : end])
        definitions.append(
            {"number": match.group(1), "text": cleaned, "ru_notes": notes}
        )
    return definitions


def split_saying_separator(line):
    dash_candidates = []
    for i, char in enumerate(line):
        if char == "=" and line[max(0, i - 1) : i + 2].strip() == "=":
            return line[:i].strip(), "=", line[i + 1 :].strip()
        if char in "-–—" and (i == 0 or line[i - 1] != "\\"):
            if (
                i > 0
                and i + 1 < len(line)
                and line[i - 1].isspace()
                and line[i + 1].isspace()
            ):
                dash_candidates.append(i)
    if dash_candidates:
        definition_like = [
            i
            for i in dash_candidates
            if line[i + 1 :].lstrip()[:1].isupper()
            or line[i + 1 :].lstrip().startswith("(")
        ]
        i = definition_like[0] if definition_like else dash_candidates[0]
        return line[:i].replace("\\-", "-").strip(), "-", line[i + 1 :].strip()
    return None


def split_saying_definitions(text):
    matches = list(SAYING_DEF_RE.finditer(text))
    if matches:
        return [
            {
                "number": match.group(1),
                "text": normalize_space(
                    text[
                        match.end() : matches[i + 1].start()
                        if i + 1 < len(matches)
                        else len(text)
                    ]
                ),
            }
            for i, match in enumerate(matches)
        ]
    return [
        {"number": None, "text": normalize_space(part)}
        for part in text.split(";")
        if normalize_space(part)
    ]


def parse_saying(line, line_number):
    split_at = split_saying_separator(line)
    if not split_at:
        return {
            "line": line_number,
            "raw": line,
            "parse_error": "missing saying separator",
            "article": line,
        }

    word, op, body = split_at
    body_without_sources = SOURCE_RE.sub(" ", body)
    is_link = op == "="
    link = LINK_RE.search(body)
    entry = {
        "line": line_number,
        "raw": line,
        "article": word,
        "is_link": is_link,
        "sources": SOURCE_RE.findall(body),
        "definitions": []
        if is_link
        else split_saying_definitions(body_without_sources),
    }
    if is_link and link:
        entry["link"] = link.group(1)
    elif is_link:
        entry["parse_error"] = "missing link target"
    return entry


def parse_head(head):
    be_notes = re.findall(r"\(([^()]*)\)", head)
    chunks = re.sub(r"\([^()]*\)", " ", head).split()
    tags = []
    while chunks and TAG_GROUP_RE.fullmatch(chunks[-1]):
        tags[:0] = TAG_RE.findall(chunks.pop())
    word = normalize_space(" ".join(chunks))
    gender = next(
        (tag.rstrip(".") for tag in tags if tag in {"м.", "ж.", "н.", "а."}), None
    )
    return {
        "word": word,
        "be_notes": [note.strip() for note in be_notes if note.strip()],
        "gender": gender,
        "is_plural": "мн." in tags,
        "is_proper": "ул." in tags,
    }


def parse_entry(line, line_number):
    match = ENTRY_RE.match(line)
    if not match:
        word = line.split("/", 1)[0].strip()
        return {
            "line": line_number,
            "raw": line,
            "parse_error": "missing article separator",
            "word": word,
        }

    body = match.group("body").strip()
    ru_without_sources = SOURCE_RE.sub(" ", body)
    is_link = match.group("op") == "="
    link = LINK_RE.search(body)
    _, ru_notes = pull_parentheses(ru_without_sources)
    if is_link:
        ru_notes = [note for note in ru_notes if not LINK_RE.search(note)]
    entry = {
        "line": line_number,
        "raw": line,
        **parse_head(match.group("head").strip()),
        "latin": match.group("latin").strip(),
        "is_link": is_link,
        "ru_notes": ru_notes,
        "sources": SOURCE_RE.findall(body),
        "definitions": [] if is_link else split_definitions(ru_without_sources),
    }
    if is_link and link:
        entry["link"] = link.group(1)
    elif is_link:
        entry["parse_error"] = "missing link target"
    return entry


def letter_for(entry):
    word = entry.get("word", "").strip()
    return word[:1].casefold() or "_"


def split(source, out_dir):
    lines = source.read_text(encoding="utf-8").splitlines()
    try:
        marker_index = lines.index(MARKER)
        sayings_index = lines.index(SAYINGS_MARKER)
    except ValueError as exc:
        raise SystemExit(f"{source}: missing section marker") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "preface.txt").write_text(
        "\n".join(lines[: marker_index + 1]) + "\n", encoding="utf-8"
    )
    sayings = [
        parse_saying(line, line_number)
        for line_number, line in enumerate(
            lines[sayings_index + 1 : marker_index], sayings_index + 2
        )
        if line.strip()
    ]
    (out_dir / "sayings.json").write_text(
        json.dumps(sayings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    by_letter = defaultdict(list)
    skipped_blank = 0
    for offset, line in enumerate(lines[marker_index + 1 :], marker_index + 2):
        if not line.strip():
            skipped_blank += 1
            continue
        entry = parse_entry(line, offset)
        by_letter[letter_for(entry)].append(entry)

    for letter, entries in sorted(by_letter.items()):
        (out_dir / f"{letter}.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return (
        sum(map(len, by_letter.values())),
        len(by_letter),
        skipped_blank,
        len(sayings),
    )


def self_check():
    entry = parse_entry(
        'абАбачак м. /ababačak/ = (гл. "абабак") [СН] (уменьшительное)', 1
    )
    assert entry["word"] == "абАбачак"
    assert entry["gender"] == "м"
    assert entry["is_link"] is True
    assert entry["link"] == "абабак"
    assert entry["sources"] == ["СН"]
    assert entry["definitions"] == []
    assert entry["ru_notes"] == ["уменьшительное"]

    entry = parse_entry("а /a/ - 1) а, о (безударное); 2) и, да [БН]", 2)
    assert entry["definitions"] == [
        {"number": "1", "text": "а, о", "ru_notes": ["безударное"]},
        {"number": "2", "text": "и, да", "ru_notes": []},
    ]
    assert entry["ru_notes"] == ["безударное"]

    saying = parse_saying(
        r"Век зжыць \- ня мех сшыць - Жизнь прожить - не поле перейти", 3
    )
    assert saying["article"] == "Век зжыць - ня мех сшыць"
    assert saying["definitions"] == [
        {"number": None, "text": "Жизнь прожить - не поле перейти"}
    ]

    saying = parse_saying('З камарову дзюбу (лытку) = (гл. "З жабіны прыгаршчы")', 4)
    assert saying["is_link"] is True
    assert saying["link"] == "З жабіны прыгаршчы"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="vbrs.txt")
    parser.add_argument("--out", default="json/articles")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        self_check()

    count, files, blanks, sayings = split(Path(args.source), Path(args.out))
    print(
        f"wrote {count} articles to {files} json files; "
        f"wrote {sayings} sayings; skipped {blanks} blank lines"
    )


if __name__ == "__main__":
    main()
