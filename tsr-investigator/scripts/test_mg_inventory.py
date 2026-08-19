"""Tests for must-gather inventory cataloging."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mg_inventory import build_inventory, discover_plugins, inventory_summary_lines


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class DiscoverPluginsTests(unittest.TestCase):
    def test_wrapper_with_child_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = _mkdir(
                root / "quay-io-openshift-release-dev-ocp-v4.0-must-gather-sha256-abc"
            )
            _mkdir(child / "namespaces" / "default")
            other = _mkdir(root / "not-a-plugin")
            _mkdir(other / "random")

            found = discover_plugins(root)
            self.assertEqual([child], found)

    def test_plugin_root_is_cataloged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin = _mkdir(
                Path(tmp) / "quay-io-openshift-release-dev-ocp-v4.0-must-gather-sha256-abc"
            )
            _mkdir(plugin / "namespaces" / "openshift-etcd")

            found = discover_plugins(plugin)
            self.assertEqual([plugin], found)

            data = build_inventory(plugin)
            self.assertEqual(len(data["plugins"]), 1)
            self.assertEqual(data["plugins"][0]["path"], str(plugin.resolve()))
            self.assertEqual(data["plugins"][0]["namespaces"], ["openshift-etcd"])
            self.assertEqual(data["skipped_top_level"], [])
            self.assertNotIn(
                "no plugin directories found",
                " ".join(data["warnings"]),
            )

    def test_empty_wrapper_is_not_treated_as_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _mkdir(Path(tmp) / "must-gather.local.12345")
            (root / "timestamp").write_text("now", encoding="utf-8")
            _mkdir(root / "notes")

            found = discover_plugins(root)
            self.assertEqual([], found)
            data = build_inventory(root)
            self.assertEqual(data["plugins"], [])
            self.assertTrue(
                any("no plugin directories found" in w for w in data["warnings"])
            )


class NestedNamespaceTests(unittest.TestCase):
    def test_nested_inspect_tree_is_merged_into_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = _mkdir(
                root / "quay-io-openshift-release-dev-ocp-v4.0-must-gather-sha256-abc"
            )
            _mkdir(plugin / "namespaces" / "openshift-etcd")
            _mkdir(plugin / "namespaces" / "default")
            inspect = _mkdir(plugin / "inspect.local.111" / "namespaces")
            _mkdir(inspect / "openshift-cnv")
            _mkdir(inspect / "kubevirt")
            _touch(
                inspect
                / "openshift-cnv"
                / "pods"
                / "virt-operator-0"
                / "virt-operator"
                / "virt-operator"
                / "logs"
                / "current.log"
            )
            _touch(
                plugin
                / "namespaces"
                / "openshift-etcd"
                / "pods"
                / "etcd-master-0"
                / "etcd"
                / "etcd"
                / "logs"
                / "current.log"
            )

            data = build_inventory(root)
            rec = data["plugins"][0]
            self.assertEqual(
                rec["namespaces"],
                ["default", "kubevirt", "openshift-cnv", "openshift-etcd"],
            )
            self.assertEqual(
                rec["extra_namespace_trees"],
                ["inspect.local.111/namespaces"],
            )
            self.assertEqual(
                rec["namespaces_by_tree"]["namespaces"],
                ["default", "openshift-etcd"],
            )
            self.assertEqual(
                rec["namespaces_by_tree"]["inspect.local.111/namespaces"],
                ["kubevirt", "openshift-cnv"],
            )
            self.assertEqual(rec["pod_logs"]["total_current_log_files"], 2)
            self.assertEqual(rec["pod_logs"]["namespaces"]["openshift-etcd"], 1)
            self.assertEqual(rec["pod_logs"]["namespaces"]["openshift-cnv"], 1)
            self.assertIn("openshift-cnv", data["namespace_index"])
            self.assertIn("kubevirt", data["namespace_index"])
            self.assertIn("openshift-etcd", data["namespace_index"])
            self.assertEqual(data["namespace_index"]["openshift-cnv"], ["ocp-default"])
            summary = "\n".join(inventory_summary_lines(data))
            self.assertIn("extra trees: inspect.local.111/namespaces", summary)

    def test_nested_only_tree_without_top_level_namespaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = _mkdir(root / "registry-redhat-io-openshift-logging-must-gather-sha256-x")
            nested = _mkdir(plugin / "timestamp-inspect" / "namespaces" / "openshift-logging")
            _touch(
                nested
                / "pods"
                / "collector-0"
                / "collector"
                / "collector"
                / "logs"
                / "current.log"
            )

            data = build_inventory(root)
            rec = data["plugins"][0]
            self.assertEqual(rec["namespaces"], ["openshift-logging"])
            self.assertEqual(
                rec["extra_namespace_trees"],
                ["timestamp-inspect/namespaces"],
            )
            self.assertEqual(rec["pod_logs"]["total_current_log_files"], 1)
            self.assertEqual(
                data["namespace_index"]["openshift-logging"],
                ["logging"],
            )


if __name__ == "__main__":
    unittest.main()
