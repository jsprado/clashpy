"""
Wires NewsSource -> Extraction LLM -> Solver -> Metrics -> Synthesis LLM.

Only couples to protocols (Solver, NewsSource), not concrete implementations.
The caller (cli.py or downstream services) determines concrete adapters
via dependency injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from clashpy.adapters.news_sources.base import NewsSource
from clashpy.core.cache import DuckDBCache
from clashpy.core.hashing import stable_hash
from clashpy.core.metrics import (
    classify_arguments,
    compute_argument_scores,
    compute_attack_degrees,
    detect_dilemma_axes,
)
from clashpy.core.models import ArgumentationFramework, FullAnalysisResult
from clashpy.core.solver import Semantics, Solver
from clashpy.errors import NoNewsDataError, ProviderError
from clashpy.llm.agents import get_extraction_agent, get_synthesis_agent

PIPELINE_SCHEMA_VERSION = "pipeline-v1"


@dataclass
class PipelineResult:
    af: ArgumentationFramework
    extensions: List[Set[str]]
    scores: Dict[str, float]
    classification: Dict[str, str]
    degrees: Dict[str, Dict[str, int]]
    dilemma_axes: List[Tuple[str, str, str, str]]
    synthesis: Optional[FullAnalysisResult] = None


def _extract_framework(
    cache: DuckDBCache,
    raw_news: str,
    model_name: str,
    target_topic: str,
    force_refresh: bool,
) -> ArgumentationFramework:
    key = stable_hash(
        PIPELINE_SCHEMA_VERSION,
        "framework",
        model_name,
        raw_news,
        target_topic.strip().lower(),
    )

    if not force_refresh:
        cached = cache.get_json("framework", key)
        if cached is not None:
            print("→ Framework-Cache HIT – skipping extraction LLM call")
            return ArgumentationFramework.model_validate(cached)

    print("→ Framework-Cache MISS – invoking extraction LLM")
    prompt = (
        f"Das gewünschte Thema ist: {target_topic}\n\n"
        f"Hier sind die Nachrichten und Daten:\n\n{raw_news}"
        if target_topic
        else f"Hier sind die Nachrichten und Daten:\n\n{raw_news}"
    )
    try:
        result = get_extraction_agent(model_name).run_sync(prompt)
    except Exception as exc:
        raise ProviderError(
            f"LLM extraction failed for model '{model_name}': {exc}"
        ) from exc
    af = result.output

    if target_topic:
        af.topic = target_topic

    cache.set_json("framework", key, af.model_dump())
    return af


def _solve_extensions(
    cache: DuckDBCache,
    af: ArgumentationFramework,
    solver: Solver,
    semantics: Semantics,
    force_refresh: bool,
) -> List[Set[str]]:
    # Cache key includes solver name to prevent collisions between different solvers
    key = stable_hash(
        PIPELINE_SCHEMA_VERSION,
        "extensions",
        solver.name,
        semantics.value,
        af.model_dump(),
    )

    if not force_refresh:
        cached = cache.get_json(f"extensions:{solver.name}", key)
        if cached is not None:
            print(f"→ Extensions-Cache HIT ({solver.name}/{semantics.value})")
            return [set(ext) for ext in cached]

    print(f"→ Extensions-Cache MISS – solving with {solver.name} ({semantics.value})")
    extensions = solver.extensions(af, semantics=semantics)

    cache.set_json(
        f"extensions:{solver.name}",
        key,
        [sorted(ext) for ext in extensions],
    )
    return extensions


def _synthesize(
    cache: DuckDBCache,
    af: ArgumentationFramework,
    extensions: List[Set[str]],
    model_name: str,
    force_refresh: bool,
) -> FullAnalysisResult:
    groups_input = "\n".join(
        f"Gruppe {i + 1}: {', '.join(sorted(group))}"
        for i, group in enumerate(extensions, 1)
    )
    arguments_input = "\n".join(f"- {arg.id}: {arg.claim}" for arg in af.arguments)
    prompt = (
        f"Thema: {af.topic}\n\n"
        f"Argumente:\n{arguments_input}\n\n"
        f"Berechnete Perspektiven:\n{groups_input}"
    )

    key = stable_hash(PIPELINE_SCHEMA_VERSION, "synthesis", model_name, prompt)

    if not force_refresh:
        cached = cache.get_json("synthesis", key)
        if cached is not None:
            print("→ Synthesis-Cache HIT – skipping synthesis LLM call")
            return FullAnalysisResult.model_validate(cached)

    print("→ Synthesis-Cache MISS – invoking synthesis LLM")
    try:
        result = get_synthesis_agent(model_name).run_sync(prompt)
    except Exception as exc:
        raise ProviderError(
            f"LLM synthesis failed for model '{model_name}': {exc}"
        ) from exc
    synthesis = result.output

    for i, thesis in enumerate(synthesis.theses, 1):
        thesis.group_id = i

    cache.set_json("synthesis", key, synthesis.model_dump())
    return synthesis


def run_pipeline(
    topic: str,
    news_source: NewsSource,
    solver: Solver,
    cache_db: Path,
    model_name: str,
    semantics: Semantics = Semantics.PREFERRED,
    max_news_items: int = 30,
    news_ttl: timedelta = timedelta(minutes=15),
    force_refresh: bool = False,
    with_synthesis: bool = True,
    dense_filter: bool = True,
) -> PipelineResult:
    with DuckDBCache(cache_db) as cache:
        # -- 1. News Ingestion ----------------------------------------
        news_key = stable_hash(
            PIPELINE_SCHEMA_VERSION,
            "news",
            news_source.name,
            topic.strip().lower(),
            max_news_items,
        )

        raw_news = None
        if not force_refresh:
            raw_news = cache.get_json(
                f"news:{news_source.name}", news_key, ttl=news_ttl
            )

        if raw_news is None:
            print(f"→ News-Cache MISS/REFRESH ({news_source.name})")
            raw_news = news_source.fetch(topic, max_items=max_news_items)
            cache.set_json(f"news:{news_source.name}", news_key, raw_news)
        else:
            print(f"→ News-Cache HIT ({news_source.name})")

        if not raw_news.strip():
            raise NoNewsDataError(
                "No usable news data was retrieved. Check the topic and feed URLs."
            )

        # -- 2. Local Dense Pre-Filter (M4 Token Reduction) -----------
        if dense_filter:
            from clashpy.adapters.classifiers.dense_filter import prune_corpus
            news_payload = prune_corpus(raw_news, topic=topic)
        else:
            news_payload = raw_news

        # -- 3. Framework Extraction ----------------------------------
        af = _extract_framework(cache, news_payload, model_name, topic, force_refresh)

        # -- 4. Extension Solving -------------------------------------
        extensions = _solve_extensions(cache, af, solver, semantics, force_refresh)

        # -- 5. Metrics (pure functions, no cache needed) -------------
        all_ids = [arg.id for arg in af.arguments]
        scores = compute_argument_scores(all_ids, extensions)
        classification = classify_arguments(scores)
        degrees = compute_attack_degrees(all_ids, af.attacks)
        dilemma_axes = detect_dilemma_axes(af.attacks)

        # -- 6. Synthesis (optional) ----------------------------------
        synthesis = None
        if with_synthesis:
            synthesis = _synthesize(cache, af, extensions, model_name, force_refresh)

        return PipelineResult(
            af=af,
            extensions=extensions,
            scores=scores,
            classification=classification,
            degrees=degrees,
            dilemma_axes=dilemma_axes,
            synthesis=synthesis,
        )
