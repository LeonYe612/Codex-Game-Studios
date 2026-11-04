#!/usr/bin/env python3
"""Check discovery metadata for bundled skills.

This is a repository maintenance gate, not an official Codex limit. It keeps
the name/description surface small and discriminating; full instructions stay
in each SKILL.md body and are loaded only after selection.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_DESCRIPTION_CHARS = 160
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
NAME_LINE = re.compile(r"^name:\s*(.*)$", re.MULTILINE)
DESC_LINE = re.compile(r"^description:\s*(.*)$", re.MULTILINE)


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    return value


def check(root: Path, limit: int) -> list[dict]:
    rows = []
    for path in sorted(root.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        row = {"skill": path.parent.name, "path": str(path), "errors": []}
        if not match:
            row["errors"].append("missing or unterminated frontmatter")
            rows.append(row)
            continue
        frontmatter = match.group(1)
        name_match = NAME_LINE.search(frontmatter)
        desc_match = DESC_LINE.search(frontmatter)
        if not name_match:
            row["errors"].append("missing name")
        elif scalar(name_match.group(1)) != path.parent.name:
            row["errors"].append("name must match its directory")
        if not desc_match:
            row["errors"].append("missing description")
            rows.append(row)
            continue
        description = scalar(desc_match.group(1))
        row["chars"] = len(description)
        row["description"] = description
        if not description:
            row["errors"].append("empty description")
        if "\n" in description:
            row["errors"].append("description must be a single line")
        if len(description) > limit:
            row["errors"].append(f"description exceeds {limit} characters")
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SKILL.md discovery metadata")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "skills",
        help="directory containing <skill>/SKILL.md folders",
    )
    parser.add_argument("--max-chars", type=int, default=MAX_DESCRIPTION_CHARS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = check(args.root, args.max_chars)
    failed = [row for row in rows if row["errors"]]
    report = {
        "root": str(args.root),
        "skills": len(rows),
        "failed": len(failed),
        "total_chars": sum(row.get("chars", 0) for row in rows),
        "max_chars": max((row.get("chars", 0) for row in rows), default=0),
        "limit": args.max_chars,
        "errors": failed,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"skills={report['skills']} failed={report['failed']} "
            f"total_chars={report['total_chars']} max_chars={report['max_chars']} "
            f"limit={report['limit']}"
        )
        for row in failed:
            for error in row["errors"]:
                print(f"{row['skill']}: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
