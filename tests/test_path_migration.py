# tests/test_path_migration.py
"""
Regression test: ensure migrated core modules use paths.py, not Path(__file__).
Catches both Path(__file__).parent and Path(__file__).parent.parent forms.
"""
import ast
import pathlib

MIGRATED_FILES = [
    "core/bank_detector.py",
    "core/loader.py",
    "core/exporter.py",
    "core/mapping_memory.py",
    "core/override_manager.py",
]

ROOT = pathlib.Path(__file__).parent.parent


def _is_path_file_call(node) -> bool:
    """Return True if node is Path(__file__)."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Path"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "__file__"
    )


def _contains_file_path_construction(source: str) -> bool:
    """Return True if source contains Path(__file__).parent[.parent...] usage.

    ast.walk() descends into all nodes including function bodies, so inline
    path constructions inside functions (like loader.py's load_config()) are
    correctly detected.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        # node is an Attribute(.parent) access
        if not (isinstance(node, ast.Attribute) and node.attr == "parent"):
            continue
        # Walk the chain to see if it terminates at Path(__file__)
        inner = node.value
        while isinstance(inner, ast.Attribute) and inner.attr == "parent":
            inner = inner.value
        if _is_path_file_call(inner):
            return True
    return False


def test_no_file_relative_paths_in_migrated_modules():
    """None of the migrated files should construct paths from Path(__file__)."""
    for rel_path in MIGRATED_FILES:
        source = (ROOT / rel_path).read_text(encoding="utf-8")
        assert not _contains_file_path_construction(source), (
            f"{rel_path} still contains Path(__file__).parent — "
            "migrate to paths.py imports"
        )
