"""
CLI entry point for clashpy.

Demonstrates the core benefit of the decoupled architecture: the choice of solver
(naive vs. pygarg) and ingestion source is a pure runtime CLI option without
modifying any core pipeline code.

    uv run clashpy "AI Regulation" --solver naive
    uv run clashpy "AI Regulation" --solver pygarg
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

from clashpy.adapters.news_sources.base import NewsSource
from clashpy.adapters.news_sources.composite_source import CompositeNewsSource
from clashpy.adapters.news_sources.rss_source import RSSNewsSource
from clashpy.adapters.news_sources.search_source import GoogleNewsSearchSource
from clashpy.core.solver import Semantics, Solver
from clashpy.errors import ClashpyError
from clashpy.pipeline import run_pipeline

DEFAULT_RSS = "https://www.tagesschau.de/index~rss2.xml,https://www.heise.de/rss/heise-atom.xml,https://www.zeit.de/news/index"
DEFAULT_MODEL = "google:gemini-3.5-flash"
DEFAULT_SOURCES_YAML = "sources.yaml"


def _resolve_export_path(
    requested_path: str,
    default_name: str,
    output_dir: Path,
    timestamp: str,
) -> Path:
    path = Path(requested_path)
    if path.name == default_name:
        path = output_dir / f"{timestamp}_{default_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _build_solver(name: str, naive_max_arguments: int = 20) -> Solver:
    if name == "naive":
        from clashpy.core.solver import NaiveBacktrackingSolver

        return NaiveBacktrackingSolver(max_arguments=naive_max_arguments)

    if name == "pygarg":
        from clashpy.adapters.solvers.pygarg_solver import PygargSolver

        return PygargSolver()

    raise ValueError(f"Unknown solver: {name!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Argumentation analysis pipeline (packaged version)"
    )

    parser.add_argument("topic", nargs="?", default="")
    parser.add_argument(
        "--topic", dest="topic_opt", default=None, help="Alternative flag for topic"
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Single feed URL or comma-separated list of RSS feeds (e.g., Tagesschau, Heise, Zeit)",
    )
    parser.add_argument(
        "--source-yaml",
        default=DEFAULT_SOURCES_YAML,
        help="Path to YAML sources configuration (default: sources.yaml)",
    )
    parser.add_argument(
        "--search",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable deep topic-targeted search across Google News (default: True)",
    )
    parser.add_argument(
        "--search-time",
        default="30d",
        help="Search time horizon, e.g. '7d', '14d', '30d' (default: 30d)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--solver",
        choices=["naive", "pygarg"],
        default="naive",
        help=(
            "'naive' = built-in backtracking, exponential. "
            "'pygarg' = SAT-based solver, scales better, requires "
            "'pip install pygarg' (binary in PATH)."
        ),
    )
    parser.add_argument(
        "--semantics",
        choices=[s.value for s in Semantics],
        default=Semantics.PREFERRED.value,
    )
    parser.add_argument(
        "--naive-max-arguments",
        type=int,
        default=20,
        help="Maximum framework size accepted by the exponential naive solver (default: 20).",
    )
    parser.add_argument("--cache-db", default="af_cache.duckdb")
    parser.add_argument("--news-ttl-minutes", type=int, default=15)
    parser.add_argument("--max-articles", type=int, default=30)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-synthesis", action="store_true")
    parser.add_argument("--output-json", default=None)
    parser.add_argument(
        "--export-md",
        nargs="?",
        const="af_analyse.md",
        default=None,
        help="Export visual markdown report (.md)",
    )
    parser.add_argument(
        "--export-mmd",
        nargs="?",
        const="af_graph.mmd",
        default=None,
        help="Export Mermaid graph (.mmd)",
    )
    parser.add_argument(
        "--export-html",
        nargs="?",
        const="af_graph.html",
        default=None,
        help="Export interactive Cytoscape.js HTML visualization (.html)",
    )
    parser.add_argument(
        "--export-cytoscape",
        nargs="?",
        const="af_cytoscape.json",
        default=None,
        help="Export Cytoscape.js graph JSON (.json)",
    )

    return parser.parse_args()


BANNER = r"""
       _           _                  
      | |         | |                 
   ___| | __ _ ___| |__  _ __  _   _  
  / __| |/ _` / __| '_ \| '_ \| | | | 
 | (__| | (_| \__ \ | | | |_) | |_| | 
  \___|_|\__,_|___/_| |_| .__/ \__, | 
                        | |     __/ | 
                        |_|    |___/  
 Automated Argumentation Reasoning Engine ⚡
"""


def _run() -> None:
    import os

    os.environ["PYDANTIC_AI_NO_BANNER"] = "1"

    print(BANNER)

    args = parse_args()

    topic = (args.topic_opt or args.topic or "").strip()

    # Apply keyring secrets or .env values for API keys
    from clashpy.core.hashing import apply_keyring_secrets

    apply_keyring_secrets(
        secret_keys=[
            "GOOGLE_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "DEEPINFRA_API_KEY",
            "OPENROUTER_API_KEY",
            "DASHSCOPE_API_KEY",
            "TOGETHER_API_KEY",
            "ANTHROPIC_API_KEY",
            "MISTRAL_API_KEY",
        ]
    )

    try:
        solver = _build_solver(args.solver, args.naive_max_arguments)
    except Exception as exc:
        print(f"→ Solver '{args.solver}' could not be initialized: {exc}")
        sys.exit(1)

    # Determine news ingestion source
    news_source: NewsSource
    if args.source:
        # User specified an explicit RSS feed URL or list
        news_source = RSSNewsSource(feed_url=args.source)
    else:
        # Use CompositeNewsSource with YAML sources + Deep Topic Search
        news_source = CompositeNewsSource(
            config_path=Path(args.source_yaml) if args.source_yaml else None,
            enable_search=args.search,
            search_time_window=args.search_time,
        )

    source_desc = f"{news_source.name} (yaml={args.source_yaml}, search={args.search})" if not args.source else args.source

    result = run_pipeline(
        topic=topic,
        news_source=news_source,
        solver=solver,
        cache_db=Path(args.cache_db),
        model_name=args.model,
        semantics=Semantics(args.semantics),
        max_news_items=args.max_articles,
        news_ttl=timedelta(minutes=args.news_ttl_minutes),
        force_refresh=args.refresh,
        with_synthesis=not args.no_synthesis,
    )

    print()
    print("=" * 70)
    print("ANALYSIS RESULTS")
    print("=" * 70)
    print(f"Topic:         {result.af.topic}")
    print(f"Solver:        {solver.name} ({args.semantics})")
    print(f"Arguments:     {len(result.af.arguments)}")
    print(f"Attacks:       {len(result.af.attacks)}")
    print(f"Extensions:    {len(result.extensions)}")
    print(f"Dilemma Axes:  {len(result.dilemma_axes)}")
    print("=" * 70)

    if args.output_json:
        payload = {
            "topic": result.af.topic,
            "solver": solver.name,
            "semantics": args.semantics,
            "arguments": [a.model_dump() for a in result.af.arguments],
            "attacks": [a.model_dump() for a in result.af.attacks],
            "extensions": [sorted(ext) for ext in result.extensions],
            "scores": result.scores,
            "classification": result.classification,
            "degrees": result.degrees,
            "synthesis": result.synthesis.model_dump() if result.synthesis else None,
        }
        Path(args.output_json).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON written to: {args.output_json}")

    from datetime import datetime

    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_mermaid(af) -> str:
        lines = ["graph TD"]
        for arg in af.arguments:
            claim_escaped = arg.claim.replace('"', "'")
            lines.append(f'    {arg.id}["{arg.id}: {claim_escaped}"]')
        for att in af.attacks:
            lines.append(f"    {att.attacker_id} --> {att.target_id}")
        return "\n".join(lines)

    if args.export_mmd:
        mmd_path = _resolve_export_path(
            args.export_mmd, "af_graph.mmd", output_dir, now_str
        )
        mmd_content = _generate_mermaid(result.af)
        mmd_path.write_text(mmd_content, encoding="utf-8")
        print(f"Mermaid graph written to: {mmd_path}")

    if args.export_html:
        from clashpy.cytoscape import generate_cytoscape_html

        html_path = _resolve_export_path(
            args.export_html, "af_graph.html", output_dir, now_str
        )
        html_content = generate_cytoscape_html(
            af=result.af,
            extensions=result.extensions,
            scores=result.scores,
            classification=result.classification,
            dilemma_axes=result.dilemma_axes,
            degrees=result.degrees,
            synthesis=result.synthesis,
            solver_name=solver.name,
            semantics_name=args.semantics,
            model_name=args.model,
            source_name=args.source,
        )
        html_path.write_text(html_content, encoding="utf-8")
        print(f"Interactive Cytoscape.js HTML written to: {html_path}")

    if args.export_cytoscape:
        from clashpy.cytoscape import export_cytoscape_json

        cyto_path = _resolve_export_path(
            args.export_cytoscape, "af_cytoscape.json", output_dir, now_str
        )
        cyto_content = export_cytoscape_json(
            af=result.af,
            extensions=result.extensions,
            scores=result.scores,
            classification=result.classification,
            dilemma_axes=result.dilemma_axes,
            degrees=result.degrees,
            synthesis=result.synthesis,
            topic=result.af.topic,
        )
        cyto_path.write_text(cyto_content, encoding="utf-8")
        print(f"Cytoscape.js JSON written to: {cyto_path}")

    if args.export_md:
        md_path = _resolve_export_path(
            args.export_md, "af_analyse.md", output_dir, now_str
        )

        md_lines = [
            f"# Argumentation Analysis: {result.af.topic}",
            f"\n*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "## Summary",
            f"- **Solver:** {solver.name} ({args.semantics})",
            f"- **Model:** `{args.model}`",
            f"- **News source:** `{source_desc}`",
            f"- **Arguments:** {len(result.af.arguments)}",
            f"- **Attacks:** {len(result.af.attacks)}",
            f"- **Preferred Extensions:** {len(result.extensions)}",
            f"- **Dilemma Axes:** {len(result.dilemma_axes)}",
            "\n## Argumentation Graph (Mermaid)\n",
            "```mermaid",
            _generate_mermaid(result.af),
            "```\n",
            "## Arguments & Classification\n",
            "| ID | Classification | Score | Claim | Source |",
            "| :--- | :--- | ---: | :--- | :--- |",
        ]
        for arg in result.af.arguments:
            cls = result.classification.get(arg.id, "Unknown")
            score = result.scores.get(arg.id, 0.0)
            md_lines.append(
                f"| {_markdown_cell(arg.id)} | {cls} | {score:.2f} | "
                f"{_markdown_cell(arg.claim)} | {_markdown_cell(arg.source_url)} |"
            )

        md_lines.append("\n## Attack Relations\n")
        if result.af.attacks:
            for attack in result.af.attacks:
                md_lines.append(
                    f"- `{attack.attacker_id}` → `{attack.target_id}`: "
                    f"{attack.reason}"
                )
        else:
            md_lines.append("No attacks were extracted.")

        md_lines.append("\n## Preferred Extensions\n")
        for index, extension in enumerate(result.extensions, 1):
            members = ", ".join(sorted(extension)) or "∅"
            md_lines.append(f"- **Extension {index}:** `{{{members}}}`")

        md_lines.append("\n## Dilemma Axes\n")
        if result.dilemma_axes:
            for left, right, left_reason, right_reason in result.dilemma_axes:
                md_lines.append(
                    f"- **`{left} ↔ {right}`:** {left_reason} / {right_reason}"
                )
        else:
            md_lines.append("No mutual attacks were detected.")

        if result.synthesis:
            md_lines.append("\n## Perspectives & Synthesis\n")
            for thesis in result.synthesis.theses:
                md_lines.append(f"### Perspective {thesis.group_id}: {thesis.title}")
                md_lines.append(f"{thesis.thesis}\n")

        md_lines.extend(
            [
                "\n## Provenance and Limitations\n",
                "This report was generated by the `clashpy` CLI. News selection and "
                "LLM extraction may be incomplete or incorrect; formal results are "
                "reproducible only for the argument graph shown above.",
            ]
        )

        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"Markdown report written to: {md_path}")


def main() -> None:
    try:
        _run()
    except (ClashpyError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Solver or provider error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
