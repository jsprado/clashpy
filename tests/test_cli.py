from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clashpy.cli import (
    _markdown_cell,
    _resolve_export_path,
    _suppress_cpython314_http_response_bug,
)


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


def test_resolve_export_path_for_html_and_cytoscape():
    html_path = _resolve_export_path(
        "af_graph.html",
        "af_graph.html",
        Path("output"),
        "20261001_120000",
    )
    assert html_path == Path("output/20261001_120000_af_graph.html")

    cyto_path = _resolve_export_path(
        "af_cytoscape.json",
        "af_cytoscape.json",
        Path("output"),
        "20261001_120000",
    )
    assert cyto_path == Path("output/20261001_120000_af_cytoscape.json")


def test_suppress_cpython314_http_response_bug():
    # Matching unraisable warning should be silently dropped
    matching_unraisable = SimpleNamespace(
        exc_type=ValueError,
        exc_value=ValueError("I/O operation on closed file."),
        object="<http.client.HTTPResponse object at 0x123>",
    )
    with patch("sys.__unraisablehook__") as mock_default:
        _suppress_cpython314_http_response_bug(matching_unraisable)
        mock_default.assert_not_called()

    # Unrelated unraisable warning should be forwarded to default handler
    other_unraisable = SimpleNamespace(
        exc_type=RuntimeError,
        exc_value=RuntimeError("Some other runtime issue"),
        object="<CustomObject>",
    )
    with patch("sys.__unraisablehook__") as mock_default:
        _suppress_cpython314_http_response_bug(other_unraisable)
        mock_default.assert_called_once_with(other_unraisable)
