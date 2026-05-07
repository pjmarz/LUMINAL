#!/usr/bin/env python3
"""
Inline midnight/_shared.py into each tool template; emit to midnight/dist/.

Every midnight/midnight_*.py template carries a single line:

    # {{INLINE_SHARED}}

That marker is replaced with the body of midnight/_shared.py (minus its
module docstring and `from difflib import SequenceMatcher` — see below)
to produce midnight/dist/midnight_*.py — which is what gets uploaded to
OpenWebUI's Workspace.

Why this exists: OpenWebUI uploads each tool as a standalone .py file via
the Workspace UI. Cross-file imports between tools are not part of that
workflow. Without this build step, helpers like fuzzy_match would be
duplicated 4-7 times across the tools and drift over time. Source-of-truth
lives in _shared.py; this script keeps the distributed copies in lockstep.

Determinism: re-running with no source changes produces byte-identical
output. The self-test verifies this.

Run: python3 midnight/build_tools.py
"""

import sys
from pathlib import Path

MIDNIGHT = Path(__file__).resolve().parent
DIST = MIDNIGHT / "dist"
SHARED = MIDNIGHT / "_shared.py"
MARKER = "# {{INLINE_SHARED}}"

TOOL_FILES = sorted(MIDNIGHT.glob("midnight_*.py"))


def extract_shared_body(shared_path: Path) -> str:
    """
    Return the part of _shared.py that should be inlined into each tool:
    the imports needed and the public function defs. Skip the module docstring
    (purely meta) and the leading shebang/encoding lines if any.
    """
    text = shared_path.read_text()
    lines = text.splitlines(keepends=True)

    # Strip leading triple-quoted module docstring if present.
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith(('"""', "'''")):
        quote = lines[i].lstrip()[:3]
        # Single-line docstring case
        if lines[i].count(quote) >= 2:
            i += 1
        else:
            i += 1
            while i < len(lines) and quote not in lines[i]:
                i += 1
            i += 1  # consume the closing line
    # Strip blank lines after docstring
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    body = "".join(lines[i:]).rstrip() + "\n"
    return body


def build_one(template_path: Path, shared_body: str) -> tuple[Path, str]:
    """Render one tool template into its dist/ output. Returns (path, content)."""
    template = template_path.read_text()
    if MARKER not in template:
        raise SystemExit(
            f"ERROR: {template_path.name} has no '{MARKER}' marker. "
            f"Add the marker (a line of its own) where the shared block belongs."
        )

    inlined_block = (
        "# === BEGIN inlined from midnight/_shared.py — DO NOT EDIT, regenerate via build_tools.py ===\n"
        + shared_body
        + "# === END inlined from midnight/_shared.py ===\n"
    )

    # Replace ONLY the first occurrence of the marker.
    rendered = template.replace(MARKER, inlined_block, 1)

    out_path = DIST / template_path.name
    return out_path, rendered


def main() -> int:
    if not SHARED.exists():
        print(f"ERROR: {SHARED} not found", file=sys.stderr)
        return 2
    if not TOOL_FILES:
        print(f"ERROR: no midnight_*.py templates found in {MIDNIGHT}", file=sys.stderr)
        return 2

    DIST.mkdir(exist_ok=True)
    shared_body = extract_shared_body(SHARED)

    written = 0
    skipped = 0
    for tpl in TOOL_FILES:
        out_path, content = build_one(tpl, shared_body)
        existing = out_path.read_text() if out_path.exists() else None
        if existing == content:
            skipped += 1
        else:
            out_path.write_text(content)
            written += 1
        print(f"  {'skip' if existing == content else 'wrote'} {out_path.relative_to(MIDNIGHT.parent)}")

    print(f"\nBuild complete: {written} written, {skipped} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
