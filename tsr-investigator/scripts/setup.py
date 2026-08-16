#!/usr/bin/env python3
"""Detect platform/tools or write tsr-config.yaml after the user answers setup questions.

  python3 setup.py detect
  python3 setup.py write --omc skip --export-format xlsx
  python3 setup.py briefing-done
  python3 setup.py ensure-xlsx
  python3 setup.py write --omc use --export-format csv --root /path/to/project
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import detect_payload, ensure_xlsx_env, mark_briefing_done, project_root, write_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Project root (default: detect from cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("detect", help="Print detected platform, tools, and default paths as JSON")

    sub.add_parser(
        "ensure-xlsx",
        help="Create project .venv and install openpyxl (uv if available, else venv). Never pip --user.",
    )

    sub.add_parser(
        "briefing-done",
        help="Set briefing_done on an existing tsr-config.yaml after the first-session briefing",
    )

    w = sub.add_parser("write", help="Write tsr-config.yaml from answered setup questions")
    w.add_argument("--omc", required=True, choices=("use", "skip"))
    w.add_argument("--export-format", required=True, choices=("xlsx", "csv", "md", "none"))
    w.add_argument("--yq", default="skip", choices=("use", "skip"))
    w.add_argument(
        "--after-each-finding",
        action="store_true",
        help="Also export after every finding (default: on request only)",
    )
    w.add_argument(
        "--no-briefing-done",
        action="store_true",
        help="Write config without setting briefing_done (default: set it)",
    )

    args = parser.parse_args()
    root = project_root(args.root)

    if args.cmd == "detect":
        json.dump(detect_payload(root), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "ensure-xlsx":
        plan = ensure_xlsx_env(root)
        print(f"xlsx env ready via {plan['method']}: {plan['venv_python']}", file=sys.stderr)
        json.dump(plan, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "briefing-done":
        cfg = mark_briefing_done(root)
        print(f"briefing_done on {root / 'tsr-config.yaml'}", file=sys.stderr)
        json.dump(cfg, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    cfg = write_config(
        root,
        omc=args.omc,
        export_format=args.export_format,
        yq=args.yq,
        after_each_finding=args.after_each_finding,
        briefing_done=not args.no_briefing_done,
    )
    path = root / "tsr-config.yaml"
    print(f"wrote {path}", file=sys.stderr)
    json.dump(cfg, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
