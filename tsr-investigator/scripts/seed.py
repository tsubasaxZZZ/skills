#!/usr/bin/env python3
"""Seed or refresh tsr-investigation.yaml from the TSR PDF.

PDF-derived fields are updated. Investigation fields (status, evidence,
user_notes, decision_brief, ...) are preserved when a finding id already exists.

  python3 seed.py
  python3 seed.py --root /path/to/project
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import load_config, project_root, seed_investigation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Project root")
    parser.add_argument("--pdf", help="Override PDF path")
    parser.add_argument("--dest", help="Override investigation YAML path")
    args = parser.parse_args()

    root = project_root(args.root)
    cfg = load_config(root) or {}
    paths = cfg.get("paths") or {}
    pdf = Path(args.pdf).expanduser() if args.pdf else Path(paths.get("pdf") or "")
    dest = Path(args.dest).expanduser() if args.dest else Path(paths.get("investigation") or root / "tsr-investigation.yaml")
    mg = paths.get("must_gather")

    if not pdf or not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}. Run setup.py write first or pass --pdf.")

    data = seed_investigation(pdf, dest, must_gather=mg)
    cats = data.get("categories") or []
    findings = data.get("findings") or []
    print(f"wrote {dest}", file=sys.stderr)
    print(f"categories: {len(cats)} (from this PDF TOC; not a fixed set)")
    for c in cats:
        n = sum(1 for f in findings if f.get("section") == c)
        print(f"  - {c} ({n})")
    print(f"findings: {len(findings)}")
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.get("priority") or "?"] = counts.get(f.get("priority") or "?", 0) + 1
    print("priority:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
