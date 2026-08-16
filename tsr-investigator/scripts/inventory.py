#!/usr/bin/env python3
"""Catalog an extracted must-gather into tsr-inventory.yaml.

Writes plugin names, namespaces, cluster-scoped dirs, whether pod logs
exist (counts only), and metrics/ top-level dirs. Does not classify
findings or modify tsr-investigation.yaml.

  python3 inventory.py
  python3 inventory.py --root /path/to/project
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import dump_yaml, load_config, load_investigation, project_root
from mg_inventory import build_inventory, inventory_summary_lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Project root")
    parser.add_argument("--must-gather", help="Override must-gather path")
    parser.add_argument("--dest", help="Override inventory YAML path")
    args = parser.parse_args()

    root = project_root(args.root)
    cfg = load_config(root) or {}
    paths = cfg.get("paths") or {}

    if args.must_gather:
        mg = Path(args.must_gather).expanduser()
    else:
        raw = paths.get("must_gather")
        mg = Path(raw).expanduser() if raw else None
    if not mg or not mg.is_dir():
        raise SystemExit(
            f"must-gather not found: {mg}. Run setup.py write first or pass --must-gather."
        )

    if args.dest:
        dest = Path(args.dest).expanduser()
    else:
        dest = Path(paths.get("inventory") or root / "tsr-inventory.yaml")

    notice = None
    inv_path = Path(paths.get("investigation") or root / "tsr-investigation.yaml")
    investigation = load_investigation(inv_path)
    if investigation:
        meta = investigation.get("meta") or {}
        notice = meta.get("data_quality_notice")

    data = build_inventory(mg, data_quality_notice=notice)
    dump_yaml(data, dest)
    print(f"wrote {dest}", file=sys.stderr)
    for line in inventory_summary_lines(data):
        print(line, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
