"""
clashpy
=======

Automated argumentation reasoning engine: Raw text -> Dung Argumentation Framework -> Extensions.

Architecture:
    core/       Domain models, DuckDB cache, solver protocols, metrics (+ naive backtracking fallback)
    adapters/   Interchangeable protocol implementations (solvers/, news_sources/)
    llm/        Pydantic-AI agent factories (extraction / synthesis)
    pipeline.py End-to-end workflow orchestrator
    cli.py      Command-line entrypoint

Design Principle:
    Hexagonal architecture (ports & adapters). `core/` contains no concrete external
    dependencies. Adapters import core, never vice versa. New data sources or solvers
    can be integrated simply by adding an adapter file without modifying core or pipeline.
"""
