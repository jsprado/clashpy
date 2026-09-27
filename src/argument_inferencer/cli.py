"""
CLI entry point for argument_inferencer.

Demonstrates the core benefit of the decoupled architecture: the choice of solver
(naive vs. pygarg) and ingestion source is a pure runtime CLI option without
modifying any core pipeline code.

    python -m argument_inferencer.cli "AI Regulation" --solver naive
    python -m argument_inferencer.cli "AI Regulation" --solver pygarg
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

from argument_inferencer.adapters.news_sources.rss_source import RSSNewsSource
from argument_inferencer.core.solver import Semantics, Solver
from argument_inferencer.pipeline import run_pipeline

DEFAULT_RSS = "https://www.tagesschau.de/index~rss2.xml"
DEFAULT_MODEL = "google:gemini-3.5-flash"


def _build_solver(name: str) -> Solver:
    if name == "naive":
        from argument_inferencer.core.solver import NaiveBacktrackingSolver

        return NaiveBacktrackingSolver()

    if name == "pygarg":
        from argument_inferencer.adapters.solvers.pygarg_solver import PygargSolver

        return PygargSolver()

    raise ValueError(f"Unknown solver: {name!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Argumentation analysis pipeline (packaged version)")

    parser.add_argument("topic", nargs="?", default="")
    parser.add_argument("--topic", dest="topic_opt", default=None, help="Alternative flag for topic")
    parser.add_argument("--source", default=DEFAULT_RSS)
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
    parser.add_argument("--cache-db", default="af_cache.duckdb")
    parser.add_argument("--news-ttl-minutes", type=int, default=15)
    parser.add_argument("--max-articles", type=int, default=30)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-synthesis", action="store_true")
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--export-md", nargs="?", const="af_analyse.md", default=None, help="Export visual markdown report (.md)")
    parser.add_argument("--export-mmd", nargs="?", const="af_graph.mmd", default=None, help="Export Mermaid graph (.mmd)")

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


def main() -> None:
    import os
    os.environ["PYDANTIC_AI_NO_BANNER"] = "1"

    print(BANNER)

    args = parse_args()

    topic = (args.topic_opt or args.topic or "").strip()

    # Apply keyring secrets or .env values for API keys
    from argument_inferencer.core.hashing import apply_keyring_secrets
    apply_keyring_secrets(secret_keys=["GOOGLE_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"])

    try:
        solver = _build_solver(args.solver)
    except Exception as exc:
        print(f"→ Solver '{args.solver}' could not be initialized: {exc}")
        sys.exit(1)

    news_source = RSSNewsSource(feed_url=args.source)

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
        mmd_path = Path(args.export_mmd)
        if mmd_path.stem == "af_graph":
            mmd_path = output_dir / f"{now_str}_{mmd_path.name}"
        else:
            mmd_path = output_dir / f"{now_str}_{mmd_path.name}"
        mmd_content = _generate_mermaid(result.af)
        mmd_path.write_text(mmd_content, encoding="utf-8")
        print(f"Mermaid graph written to: {mmd_path}")

    if args.export_md:
        md_path = Path(args.export_md)
        if md_path.stem == "af_analyse":
            md_path = output_dir / f"{now_str}_{md_path.name}"
        else:
            md_path = output_dir / f"{now_str}_{md_path.name}"
        
        md_lines = [
            f"# Argumentation Analysis: {result.af.topic}",
            f"\n*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "## Summary",
            f"- **Solver:** {solver.name} ({args.semantics})",
            f"- **Arguments:** {len(result.af.arguments)}",
            f"- **Attacks:** {len(result.af.attacks)}",
            f"- **Preferred Extensions:** {len(result.extensions)}",
            f"- **Dilemma Axes:** {len(result.dilemma_axes)}",
            "\n## Argumentation Graph (Mermaid)\n",
            "```mermaid",
            _generate_mermaid(result.af),
            "```\n",
            "## Arguments & Classification\n",
        ]
        for arg in result.af.arguments:
            cls = result.classification.get(arg.id, "Unknown")
            score = result.scores.get(arg.id, 0.0)
            md_lines.append(f"- **{arg.id}**: {arg.claim} *(Class: {cls}, Score: {score:.2f})*")

        if result.synthesis:
            md_lines.append("\n## Perspectives & Synthesis\n")
            for thesis in result.synthesis.theses:
                md_lines.append(f"### Perspective {thesis.group_id}: {thesis.title}")
                md_lines.append(f"{thesis.thesis}\n")

        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"Markdown report written to: {md_path}")


if __name__ == "__main__":
    main()
