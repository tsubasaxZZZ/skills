"""Shared helpers for the project-local tsr-investigator skill."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

STRUCTURAL_HEADINGS = {
    "about this report",
    "executive summary",
    "findings & recommendations",
    "findings and recommendations",
    "table of contents",
    "data quality notice",
}

HEADER_KEYS = (
    "Report ID",
    "Account",
    "Cluster",
    "Cluster ID",
    "OCP Version",
    "Data collected",
    "Must-gather",
)

NUMBERED = re.compile(r"^(\d+)\.\s+(.+)$")
PRIORITY_LINE = re.compile(
    r"^Priority:\s*(CRITICAL|HIGH|MEDIUM|LOW)\s*\|\s*Severity:\s*([0-9]+(?:\.\d+)?/10)\s*$",
    re.I,
)

STATUS_LABELS = {
    "not_started": "Not started",
    "in_progress": "In progress",
    "confirmed": "Confirmed",
    "partial": "Partially confirmed",
    "contradicted": "Contradicted",
    "inconclusive": "Inconclusive",
}

INVESTIGATION_FIELDS = (
    "status",
    "evidence",
    "interpretation",
    "refs",
    "next_actions",
    "investigated_on",
    "user_notes",
    "decision_brief",
)


def empty_decision_brief() -> dict:
    return {
        "scope": "",
        "if_ignored": "",
        "remediation_cost": "",
        "depends_on": [],
        "relieves": [],
        "decision_changes_if": "",
        "unconfirmed": "",
        "user_decision": "",
    }


def merge_decision_brief(prev: object) -> dict:
    out = empty_decision_brief()
    if not isinstance(prev, dict):
        return out
    for key in out:
        if key in prev and prev[key] is not None:
            out[key] = prev[key]
    return out


SKILL_SCRIPTS = Path(__file__).resolve().parent


def project_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "tsr-config.yaml").exists():
            return candidate
        if (candidate / ".cursor/skills/tsr-investigator").exists() and any(candidate.glob("must-gather.local.*")):
            return candidate
        if any(p.is_dir() for p in candidate.glob("must-gather.local.*")):
            return candidate
    return cwd


def detect_platform() -> str:
    plat = sys.platform
    if plat == "darwin":
        return "macos"
    if plat.startswith("win"):
        return "windows"
    return "linux"


def which(name: str) -> str | None:
    return shutil.which(name)


def config_path(root: Path) -> Path:
    return root / "tsr-config.yaml"


def default_paths(root: Path) -> dict:
    mg = None
    matches = sorted(root.glob("must-gather.local.*"))
    dirs = [p for p in matches if p.is_dir()]
    if dirs:
        mg = str(dirs[0])
    pdf = None
    uploads_root = Path.home() / ".cursor/projects"
    if uploads_root.is_dir():
        pdfs = sorted(uploads_root.glob("*/uploads/*.pdf"))
        if pdfs:
            pdf = str(pdfs[0])
    if not pdf:
        pdfs = sorted(root.glob("*.pdf"))
        if pdfs:
            pdf = str(pdfs[0])
    return {
        "must_gather": mg,
        "pdf": pdf,
        "investigation": str(root / "tsr-investigation.yaml"),
        "inventory": str(root / "tsr-inventory.yaml"),
        "export_dir": str(root),
    }


def load_config(root: Path) -> dict | None:
    path = config_path(root)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def is_briefing_done(cfg: dict | None) -> bool:
    return bool(cfg and cfg.get("briefing_done"))


def mark_briefing_done(root: Path) -> dict:
    existing = load_config(root)
    if not existing:
        raise SystemExit("tsr-config.yaml not found. Run setup.py write after the briefing and setup questions.")
    existing["briefing_done"] = True
    dump_yaml(existing, config_path(root))
    return existing


def dump_yaml(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data,
            fh,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def write_config(
    root: Path,
    *,
    omc: str,
    export_format: str,
    yq: str = "skip",
    after_each_finding: bool = False,
    briefing_done: bool = True,
) -> dict:
    if omc not in {"use", "skip"}:
        raise ValueError("omc must be use or skip")
    if export_format not in {"xlsx", "csv", "md", "none"}:
        raise ValueError("export format must be xlsx, csv, md, or none")
    existing = load_config(root) or {}
    paths = default_paths(root)
    for key, val in (existing.get("paths") or {}).items():
        if val:
            paths[key] = val
    cfg = {
        "schema_version": 1,
        "platform": detect_platform(),
        "briefing_done": briefing_done,
        "paths": paths,
        "tools": {
            "omc": omc,
            "yq": yq,
        },
        "export": {
            "on_request": True,
            "after_each_finding": after_each_finding,
            "format": export_format if export_format != "none" else "xlsx",
            "enabled": export_format != "none",
        },
    }
    dump_yaml(cfg, config_path(root))
    return cfg


def detect_tools() -> dict:
    return {
        "omc": which("omc"),
        "yq": which("yq"),
        "jq": which("jq"),
        "pdftotext": which("pdftotext"),
        "uv": which("uv"),
    }


def venv_dir(root: Path) -> Path:
    return root / ".venv"


def venv_python(root: Path) -> Path:
    if detect_platform() == "windows":
        return venv_dir(root) / "Scripts" / "python.exe"
    return venv_dir(root) / "bin" / "python"


def python_has_module(python: str | Path, module: str) -> bool:
    result = subprocess.run(
        [str(python), "-c", f"import {module}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def xlsx_env_plan(root: Path) -> dict:
    """How to install openpyxl: uv if present, otherwise stdlib venv. Never pip --user."""
    uv = which("uv")
    py = venv_python(root)
    env = venv_dir(root)
    if uv:
        method = "uv"
        commands = [
            f'uv venv "{env}"',
            f'uv pip install --python "{py}" openpyxl',
        ]
    else:
        method = "venv"
        commands = [
            f'"{sys.executable}" -m venv "{env}"',
            f'"{py}" -m pip install openpyxl',
        ]
    return {
        "method": method,
        "uv": uv,
        "venv_dir": str(env),
        "venv_python": str(py),
        "venv_exists": env.is_dir(),
        "openpyxl_in_current": python_has_module(sys.executable, "openpyxl"),
        "openpyxl_in_venv": py.is_file() and python_has_module(py, "openpyxl"),
        "commands": commands,
    }


def ensure_xlsx_env(root: Path) -> dict:
    """Create project .venv and install openpyxl. Prefer uv over python -m venv."""
    env = venv_dir(root)
    py = venv_python(root)
    uv = which("uv")
    if uv:
        subprocess.run([uv, "venv", str(env)], check=True)
        subprocess.run([uv, "pip", "install", "--python", str(py), "openpyxl"], check=True)
    else:
        if not py.is_file():
            subprocess.run([sys.executable, "-m", "venv", str(env)], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "openpyxl"], check=True)
    if not python_has_module(py, "openpyxl"):
        raise SystemExit(f"openpyxl is still missing in {py}")
    return xlsx_env_plan(root)


def detect_payload(root: Path) -> dict:
    tools = detect_tools()
    return {
        "root": str(root),
        "platform": detect_platform(),
        "config_exists": config_path(root).exists(),
        "config_path": str(config_path(root)),
        "briefing_done": is_briefing_done(load_config(root)),
        "paths": default_paths(root),
        "tools_on_path": {k: v is not None for k, v in tools.items()},
        "tool_paths": tools,
        "xlsx_env": xlsx_env_plan(root),
        "omc_install": {
            "supported": detect_platform() in {"linux", "macos"},
            "note": "Run from a directory in $PATH. Windows native is skip or Git Bash/WSL.",
            "commands": [
                'curl -sL "https://github.com/gmeghnag/omc/releases/latest/download/omc_$(uname)_$(uname -m).tar.gz" | tar xzf - omc && chmod +x ./omc',
                "omc -h",
            ],
        },
    }


def pdftotext(pdf: Path) -> str:
    exe = which("pdftotext")
    if not exe:
        raise SystemExit("pdftotext not found. Install poppler-utils (Linux), brew poppler (macOS), or Poppler for Windows.")
    result = subprocess.run([exe, str(pdf), "-"], check=False, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        result = subprocess.run(
            [exe, "-layout", str(pdf), "-"],
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        raise SystemExit(f"pdftotext failed: {result.stderr.strip()}")
    return result.stdout


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return text


def strip_running_chrome(text: str) -> str:
    text = re.sub(r"(?m)^Confidential Information\s*$", "", text)
    text = re.sub(r"(?m)^AI-GENERATED\s*$", "", text)
    text = re.sub(r"(?m)^Report ID - .+$", "", text)
    text = re.sub(r"(?m)^Cluster ID - .+$", "", text)
    text = re.sub(r"(?m)^-- \d+ of \d+ --\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def is_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.startswith("Report ID") or s.startswith("Cluster ID"):
        return True
    if s.startswith("Confidential") or s == "AI-GENERATED":
        return True
    if re.fullmatch(r"\d+", s):
        return True
    if re.fullmatch(r"[.|•\-]+", s):
        return True
    return False


def is_structural(line: str) -> bool:
    return line.strip().lower() in STRUCTURAL_HEADINGS


def header_value(text: str, key: str) -> str | None:
    match = re.search(rf"{re.escape(key)}\s+(.+)", text)
    if not match:
        return None
    value = match.group(1).strip()
    value = re.split(r"\n{2,}", value, maxsplit=1)[0]
    return " ".join(value.split())


def parse_metadata(text: str) -> dict:
    meta = {key: header_value(text, key) for key in HEADER_KEYS}
    notice = None
    m = re.search(
        r"Data Quality Notice\n(.+?)(?:\nExecutive Summary|\nFindings)",
        text,
        re.S,
    )
    if m:
        notice = " ".join(m.group(1).split())
    return {
        "report_id": meta.get("Report ID"),
        "account": meta.get("Account"),
        "cluster": meta.get("Cluster"),
        "cluster_id": meta.get("Cluster ID"),
        "ocp_version": meta.get("OCP Version"),
        "data_collected": meta.get("Data collected"),
        "must_gather_label": meta.get("Must-gather"),
        "data_quality_notice": notice,
    }


def toc_region(text: str) -> str:
    start = text.find("Table of Contents")
    if start < 0:
        start = text.find("Findings & Recommendations")
    if start < 0:
        return ""
    end_markers = (
        "\nThis report presents",
        "\nData Quality Notice\n",
        "\nAbout this Report\nThis report",
    )
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start + 10)
        if idx != -1:
            end = min(end, idx)
    body_hit = re.search(r"(?m)^\d+\.\s+.+\nPriority:", text[start:end])
    if body_hit:
        end = start + body_hit.start()
    return text[start:end]


def parse_toc_findings(text: str) -> tuple[list[str], list[dict]]:
    """Discover categories from TOC structure. Do not use a hardcoded category list."""
    region = toc_region(text)
    lines = [ln.strip() for ln in region.splitlines()]
    categories: list[str] = []
    findings: list[dict] = []
    current: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if is_noise(line) or is_structural(line):
            continue
        numbered = NUMBERED.match(line)
        if numbered and current:
            findings.append(
                {
                    "section": current,
                    "index": int(numbered.group(1)),
                    "title": numbered.group(2).strip(),
                    "id": f"{current}#{numbered.group(1)}",
                }
            )
            continue
        if numbered and not current:
            continue
        j = i
        while j < len(lines) and (is_noise(lines[j]) or is_structural(lines[j])):
            j += 1
        if j < len(lines) and NUMBERED.match(lines[j]):
            current = line
            if current not in categories:
                categories.append(current)
    return categories, findings


def extract_section(rest: str, name: str) -> str | None:
    sm = re.search(
        rf"{name}\n(.+?)(?=\n(?:Issue|Impact|Recommended actions|For further details)|\Z)",
        rest,
        re.S | re.I,
    )
    if not sm:
        return None
    return " ".join(sm.group(1).split())


def is_finding_header(lines: list[str], idx: int) -> bool:
    if idx >= len(lines) or not NUMBERED.match(lines[idx].strip()):
        return False
    seen = 0
    for j in range(idx + 1, min(len(lines), idx + 8)):
        s = lines[j].strip()
        if is_noise(s):
            continue
        if PRIORITY_LINE.match(s):
            return True
        if NUMBERED.match(s):
            return False
        seen += 1
        if seen >= 3:
            return False
    return False


def parse_body_findings(text: str) -> list[dict]:
    cleaned = strip_running_chrome(text)
    hits = [m.start() for m in re.finditer(r"Findings & Recommendations", cleaned)]
    start = hits[-1] if hits else 0
    lines = cleaned[start:].splitlines()
    out: list[dict] = []
    i = 0
    while i < len(lines):
        if not is_finding_header(lines, i):
            i += 1
            continue
        header = NUMBERED.match(lines[i].strip())
        assert header
        index = int(header.group(1))
        title_parts = [header.group(2).strip()]
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if is_noise(s):
                j += 1
                continue
            if PRIORITY_LINE.match(s):
                break
            title_parts.append(s)
            j += 1
            if len(title_parts) >= 3:
                break
        if j >= len(lines) or not PRIORITY_LINE.match(lines[j].strip()):
            i += 1
            continue
        pri = PRIORITY_LINE.match(lines[j].strip())
        assert pri
        k = j + 1
        body_lines: list[str] = []
        while k < len(lines) and not is_finding_header(lines, k):
            body_lines.append(lines[k])
            k += 1
        rest = "\n".join(body_lines)
        out.append(
            {
                "index": index,
                "title": " ".join(title_parts),
                "priority": pri.group(1).upper(),
                "severity": pri.group(2),
                "issue": extract_section(rest, "Issue"),
                "impact": extract_section(rest, "Impact"),
                "recommended_actions": extract_section(rest, "Recommended actions"),
            }
        )
        i = k
    return out


def norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def merge_findings(toc: list[dict], body: list[dict]) -> list[dict]:
    by_title: dict[str, dict] = {}
    for item in body:
        key = norm_title(item["title"])
        if key not in by_title:
            by_title[key] = item
    merged = []
    used = set()
    for row in toc:
        extra = by_title.get(norm_title(row["title"]))
        if extra is None:
            candidates = [
                (k, v)
                for k, v in by_title.items()
                if k not in used
                and (
                    k.startswith(norm_title(row["title"])[:40])
                    or norm_title(row["title"]).startswith(k[:40])
                )
            ]
            extra = candidates[0][1] if len(candidates) == 1 else None
        item = dict(row)
        if extra:
            used.add(norm_title(extra["title"]))
            item.update(
                {
                    "priority": extra.get("priority"),
                    "severity": extra.get("severity"),
                    "report_claim": extra.get("issue") or "",
                    "impact": extra.get("impact") or "",
                    "recommended_actions": extra.get("recommended_actions") or "",
                }
            )
        else:
            item.update(
                {
                    "priority": None,
                    "severity": None,
                    "report_claim": "",
                    "impact": "",
                    "recommended_actions": "",
                }
            )
        merged.append(item)
    return merged


def parse_pdf(pdf: Path) -> dict:
    text = normalize_text(pdftotext(pdf))
    categories, toc = parse_toc_findings(text)
    body = parse_body_findings(text)
    findings = merge_findings(toc, body)
    return {
        "meta": parse_metadata(text),
        "categories": categories,
        "findings": findings,
    }


def empty_investigation_fields() -> dict:
    return {
        "status": "not_started",
        "evidence": "",
        "interpretation": "",
        "refs": [],
        "next_actions": [],
        "investigated_on": None,
        "user_notes": "",
        "decision_brief": empty_decision_brief(),
    }


def finding_record(src: dict) -> dict:
    rec = {
        "id": src["id"],
        "section": src["section"],
        "index": src["index"],
        "title": src["title"],
        "priority": src.get("priority"),
        "severity": src.get("severity"),
        "report_claim": src.get("report_claim") or "",
        "impact": src.get("impact") or "",
        "recommended_actions": src.get("recommended_actions") or "",
    }
    rec.update(empty_investigation_fields())
    return rec


def load_investigation(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def seed_investigation(pdf: Path, dest: Path, *, must_gather: str | None = None) -> dict:
    parsed = parse_pdf(pdf)
    existing = load_investigation(dest) or {}
    old_by_id = {}
    for row in existing.get("findings") or []:
        if row.get("id"):
            old_by_id[row["id"]] = row
    findings = []
    for src in parsed["findings"]:
        rec = finding_record(src)
        prev = old_by_id.get(rec["id"])
        if prev:
            for field in INVESTIGATION_FIELDS:
                if field == "decision_brief":
                    rec[field] = merge_decision_brief(prev.get("decision_brief"))
                elif field in prev:
                    rec[field] = prev[field]
        findings.append(rec)
    meta = dict(parsed["meta"])
    meta["pdf"] = str(pdf)
    old_meta = existing.get("meta") or {}
    if must_gather:
        meta["must_gather_root"] = must_gather
    elif old_meta.get("must_gather_root"):
        meta["must_gather_root"] = old_meta["must_gather_root"]
    if old_meta.get("environment"):
        meta["environment"] = old_meta["environment"]
    data = {
        "schema_version": 1,
        "meta": meta,
        "categories": parsed["categories"],
        "findings": findings,
    }
    dump_yaml(data, dest)
    return data
