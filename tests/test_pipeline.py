"""End-to-end integration tests for the pipeline and CLI parsing."""

from pathlib import Path
from clashpy.core.solver import NaiveBacktrackingSolver, Semantics
from clashpy.pipeline import run_pipeline


class MockNewsSource:
    name = "mock"

    def fetch(self, topic: str, max_items: int = 10) -> str:
        return (
            "Title: Electric Cars vs Combustion\n"
            "Content: EV adoption reduces local emissions. However, battery production is resource-intensive.\n"
            "Source: https://example.com/ev\n"
            "Date: 2026-09-27\n"
        )


def test_pipeline_with_test_model(tmp_path: Path):
    cache_db = tmp_path / "test_cache.duckdb"
    solver = NaiveBacktrackingSolver()
    source = MockNewsSource()

    # Using pydantic-ai built-in 'test' model (zero network, deterministic)
    result = run_pipeline(
        topic="E-Mobility",
        news_source=source,
        solver=solver,
        cache_db=cache_db,
        model_name="test",
        extract_model="test",
        synthesis_model="test",
        semantics=Semantics.PREFERRED,
        with_synthesis=False,
    )

    assert result.af is not None
    assert result.af.topic == "E-Mobility"
    assert isinstance(result.extensions, list)
    assert isinstance(result.scores, dict)
    assert isinstance(result.classification, dict)
