#!/usr/bin/env python3
"""Build a persona-specific Context Sphere prompt from selector output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from context_sphere_v3.assembler import DEFAULT_MAX_FILE_CHARS
from context_sphere_v3.assembler import DEFAULT_MAX_NEIGHBORHOOD_FILES
from context_sphere_v3.assembler import assemble_context_sphere
from context_sphere_v3.assembler import load_selector_output
from context_sphere_v3.roles import ROLES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selector_output_json", help="Path to inference.py selector output JSON")
    parser.add_argument("repo_path", help="Local root directory of the codebase")
    parser.add_argument("target_persona", choices=[role.upper() for role in ROLES] + list(ROLES))
    parser.add_argument("--out", help="Path to write the final Markdown prompt. Defaults to stdout.")
    parser.add_argument("--json-out", help="Optional path to write assembly metadata plus Markdown.")
    parser.add_argument("--max-core-files", type=int, default=0, help="0 means use every selector file")
    parser.add_argument("--max-file-chars", type=int, default=DEFAULT_MAX_FILE_CHARS)
    parser.add_argument("--max-neighborhood-files", type=int, default=DEFAULT_MAX_NEIGHBORHOOD_FILES)
    args = parser.parse_args()

    selector_output = load_selector_output(args.selector_output_json)
    result = assemble_context_sphere(
        selector_output=selector_output,
        repo_path=args.repo_path,
        target_persona=args.target_persona,
        max_core_files=None if args.max_core_files <= 0 else args.max_core_files,
        max_file_chars=args.max_file_chars,
        max_neighborhood_files=args.max_neighborhood_files,
    )
    markdown = str(result["markdown"])
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    if args.json_out:
        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
