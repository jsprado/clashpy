from pathlib import Path

from clashpy.cli import _markdown_cell, _resolve_export_path


def test_default_export_path_is_timestamped_under_output_directory():
    path = _resolve_export_path(
        "af_analyse.md",
        "af_analyse.md",
        Path("output"),
        "20261001_120000",
    )

    assert path == Path("output/20261001_120000_af_analyse.md")


def test_explicit_export_path_is_preserved(tmp_path):
    requested = tmp_path / "docs" / "showcase.md"

    path = _resolve_export_path(
        str(requested),
        "af_analyse.md",
        Path("output"),
        "20261001_120000",
    )

    assert path == requested
    assert requested.parent.is_dir()


def test_markdown_cell_escapes_tables_and_line_breaks():
    assert _markdown_cell("one | two\nthree") == "one \\| two three"
