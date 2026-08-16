"""Catalog an extracted OpenShift must-gather. Names and paths only.

Do not classify findings, match Data Quality Notice items, or write
tsr-investigation.yaml. Log file bodies are not read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

PLUGIN_KINDS: tuple[tuple[str, str], ...] = (
    ("pg-must-gather", "pg-must-gather"),
    ("pg-next-pg", "pg-must-gather"),
    ("container-native-virtualization", "cnv"),
    ("openshift-virtualization", "cnv"),
    ("cnv-must-gather", "cnv"),
    ("cluster-logging", "logging"),
    ("logging-must-gather", "logging"),
    ("openshift-release-dev", "ocp-default"),
    ("ose-must-gather", "ocp-default"),
)

PLUGIN_NAME_HINTS = (
    "must-gather",
    "quay-io-",
    "registry-redhat-io-",
)

PLUGIN_CONTENT_DIRS = (
    "namespaces",
    "cluster-scoped-resources",
    "metrics",
    "workload-scoped-resources",
)


def classify_plugin(dirname: str) -> str:
    lower = dirname.lower()
    for needle, kind in PLUGIN_KINDS:
        if needle in lower:
            return kind
    return "unknown"


def _is_plugin_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    name = path.name.lower()
    if any(hint in name for hint in PLUGIN_NAME_HINTS):
        return True
    return any((path / d).is_dir() for d in PLUGIN_CONTENT_DIRS)


def _child_dirs(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    names: list[str] = []
    for child in sorted(path.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            names.append(child.name)
    return names


def _child_files(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    names: list[str] = []
    for child in sorted(path.iterdir()):
        if child.is_file() and not child.name.startswith("."):
            names.append(child.name)
    return names


def _pod_log_counts(namespaces_dir: Path) -> dict[str, int]:
    """Count current.log files under namespaces/<ns>/pods/. Do not read bodies."""
    counts: dict[str, int] = {}
    if not namespaces_dir.is_dir():
        return counts
    for ns in sorted(namespaces_dir.iterdir()):
        if not ns.is_dir():
            continue
        pods = ns / "pods"
        if not pods.is_dir():
            continue
        n = sum(1 for p in pods.rglob("current.log") if p.is_file())
        if n:
            counts[ns.name] = n
    return counts


def _scan_plugin(plugin: Path) -> dict:
    namespaces_dir = plugin / "namespaces"
    cluster_dir = plugin / "cluster-scoped-resources"
    metrics_dir = plugin / "metrics"
    nodes_dir = plugin / "nodes"
    extra_trees: list[str] = []
    for child in sorted(plugin.iterdir()):
        if not child.is_dir() or child.name == "namespaces":
            continue
        nested = child / "namespaces"
        if nested.is_dir():
            extra_trees.append(f"{child.name}/namespaces")

    log_counts = _pod_log_counts(namespaces_dir)
    record: dict = {
        "dirname": plugin.name,
        "kind": classify_plugin(plugin.name),
        "path": str(plugin.resolve()),
        "top_level": _child_dirs(plugin),
        "namespaces": _child_dirs(namespaces_dir),
        "cluster_scoped": _child_dirs(cluster_dir),
        "pod_logs": {
            "total_current_log_files": sum(log_counts.values()),
            "namespaces": log_counts,
        },
    }
    if extra_trees:
        record["extra_namespace_trees"] = extra_trees
    if metrics_dir.is_dir():
        record["metrics_dirs"] = _child_dirs(metrics_dir)
    if nodes_dir.is_dir():
        record["nodes"] = _child_dirs(nodes_dir)
        files = _child_files(nodes_dir)
        if files:
            record["nodes_files"] = files
    return record


def discover_plugins(must_gather: Path) -> list[Path]:
    if not must_gather.is_dir():
        raise FileNotFoundError(f"must-gather not found: {must_gather}")
    plugins = [p for p in sorted(must_gather.iterdir()) if _is_plugin_dir(p)]
    return plugins


def build_inventory(
    must_gather: Path,
    *,
    data_quality_notice: str | None = None,
) -> dict:
    must_gather = must_gather.expanduser().resolve()
    plugins = [_scan_plugin(p) for p in discover_plugins(must_gather)]
    namespace_index: dict[str, list[str]] = {}
    for plugin in plugins:
        kind = plugin.get("kind") or "unknown"
        label = kind if kind != "unknown" else plugin["dirname"]
        for ns in plugin["namespaces"]:
            names = namespace_index.setdefault(ns, [])
            if label not in names:
                names.append(label)
    data: dict = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "must_gather_root": str(must_gather),
        "data_quality_notice": data_quality_notice,
        "plugins": plugins,
        "namespace_index": dict(sorted(namespace_index.items())),
    }
    return data


def inventory_summary_lines(data: dict) -> list[str]:
    lines: list[str] = []
    plugins = data.get("plugins") or []
    lines.append(f"plugins: {len(plugins)}")
    for plugin in plugins:
        kind = plugin.get("kind") or "unknown"
        n_ns = len(plugin.get("namespaces") or [])
        n_logs = (plugin.get("pod_logs") or {}).get("total_current_log_files") or 0
        extra = f"{n_ns} namespaces, {n_logs} current.log"
        metrics = plugin.get("metrics_dirs")
        if metrics:
            extra += f", metrics: {', '.join(metrics)}"
        lines.append(f"  - {kind} ({plugin.get('dirname')}): {extra}")
    n_index = len(data.get("namespace_index") or {})
    lines.append(f"namespace_index: {n_index} names")
    notice = data.get("data_quality_notice")
    if notice:
        lines.append("data_quality_notice: copied from investigation YAML (not matched to plugins)")
    return lines
