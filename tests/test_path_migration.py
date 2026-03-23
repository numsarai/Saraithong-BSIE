# tests/test_path_migration.py
"""
Regression test: ensure migrated core modules use paths.py, not Path(__file__).
Catches any Path(__file__) usage in any form.
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
    """Return True if source contains any Path(__file__) call.

    Catches all forms: Path(__file__).parent, Path(__file__).resolve().parent,
    bare Path(__file__), etc.  ast.walk() descends into all nodes including
    function bodies, so inline path constructions inside functions are detected.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(_is_path_file_call(node) for node in ast.walk(tree))


def test_no_file_relative_paths_in_migrated_modules():
    """None of the migrated files should construct paths from Path(__file__)."""
    for rel_path in MIGRATED_FILES:
        source = (ROOT / rel_path).read_text(encoding="utf-8")
        assert not _contains_file_path_construction(source), (
            f"{rel_path} still contains Path(__file__).parent — "
            "migrate to paths.py imports"
        )
