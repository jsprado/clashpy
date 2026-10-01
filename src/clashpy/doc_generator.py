"""
Project documentation and visual poster generator.
Supports dual-language generation (--language de | en), emitting files
with locale suffixes (e.g. poster_de.html, poster_de.pdf, poster_de.png).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
DOCS_DIR = PROJECT_ROOT / "docs"

Language = Literal["de", "en"]


def _find_chrome() -> str | None:
    """Discovers installed Chrome or Chromium binaries across platforms."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


def _get_translations(lang: Language) -> dict[str, str]:
    if lang == "en":
        return {
            "html_lang": "en",
            "title": "clashpy – End-to-End Data Pipeline, LLM Integration & Formal Reasoning",
            "badge": "LLM Orchestration & Formal Reasoning",
            "header_h1": "clashpy ⚡",
            "header_sub": "From raw news streams to mathematically sound argumentation frameworks",
            "tag_dung": "Dung 1995 Semantics",
            "pipeline_title": "⚡ End-to-End Data Pipeline & LLM Caching Architecture",
            "step1_title": "News Ingestion",
            "step1_desc": "RSS / Atom feeds or search APIs retrieved via decoupled NewsSource adapters with topic pre-filtering.",
            "step2_title": "AI Extraction",
            "step2_desc": "Pydantic-AI Agent extracts claims & attacks into typed Pydantic models. Strictly forbids URL hallucination.",
            "step3_title": "Formal Inference",
            "step3_desc": "Mathematical evaluation of Preferred Extensions according to Dung (1995) via backtracking or SAT solvers.",
            "step4_title": "Topology & Metrics",
            "step4_desc": "Graph-theoretic scores (acceptance rate), dilemma axes (A ↔ B), and in/out degrees.",
            "step4_pill": "In-Memory (Pure Functions)",
            "step5_title": "AI Synthesis & Export",
            "step5_desc": "Second Pydantic-AI Agent synthesizes perspectives into concise theses. Automated timestamped export.",
            "scenario_title": "📰 Real-World Pipeline Scenario: “4-Day Work Week (8 Arguments Analyzed)”",
            "sc_col1_title": "1. EXTRACTED ARGUMENTS (A)",
            "sc_a1": "<strong>A1 (Health & Focus):</strong> Cuts burnout and sick leave; raises hourly cognitive productivity.",
            "sc_a2": "<strong>A2 (Cost Shock & Inflation):</strong> Equal pay spikes unit labor costs, threatening business viability.",
            "sc_a3": "<strong>A3 (AI & Efficiency):</strong> AI automation and streamlined workflows fully offset 20% fewer hours.",
            "sc_a4": "<strong>A4 (Talent Magnet):</strong> Attracts top talent, lowers employee turnover and costly hiring cycles.",
            "sc_a5": "<strong>A5 (Sector Inequity):</strong> Unfeasible for shift/care work, creating an unfair two-tier divide.",
            "sc_a6": "<strong>A6 (Carbon Reduction):</strong> Cutting one commute day reduces office energy and transport emissions.",
            "sc_a7": "<strong>A7 (Rebound Emissions):</strong> Extra leisure triggers carbon-heavy travel and recreational spending.",
            "sc_a8": "<strong>A8 (Legal Reform):</strong> Labor laws must be modernized to enable flexible, outcome-based work.",
            "sc_col2_title": "2. ARGUMENT GRAPH & ATTACKS (R)",
            "sc_graph_caption": "A2 attacks A1 & A6 | A3 & A4 attack A2 | A2 ↔ A3 Dilemma | A5 attacks A4 | A3 attacks A5 | A7 attacks A6 | A1 attacks A7 | A8 Core",
            "node_a1_title": "A1: Health & Focus",
            "node_a1_sub": "Contested (0.50)",
            "node_a2_title": "A2: Cost Shock",
            "node_a2_sub": "Contested (0.50)",
            "node_a3_title": "A3: AI & Efficiency",
            "node_a3_sub": "Contested (0.50)",
            "node_a4_title": "A4: Talent Magnet",
            "node_a4_sub": "Contested (0.50)",
            "node_a5_title": "A5: Sector Inequity",
            "node_a5_sub": "Contested (0.50)",
            "node_a6_title": "A6: Carbon Reduction",
            "node_a6_sub": "Contested (0.50)",
            "node_a7_title": "A7: Rebound Effect",
            "node_a7_sub": "Contested (0.50)",
            "node_a8_title": "A8: Legal Reform",
            "node_a8_sub": "Core (1.00)",
            "sc_col3_title": "3. COMPUTED PERSPECTIVES",
            "sc_p1_title": "Perspective 1 (Pro-Transformation & Climate): {A1, A3, A4, A6, A8}",
            "sc_p1_thesis": "<em>AI Thesis:</em> AI efficiency (A3) and talent retention (A4) offset reduced hours and burnout costs (A1), while commute cuts (A6) lower emissions under modernized laws (A8).",
            "sc_p2_title": "Perspective 2 (Cost Realism & Inequity): {A2, A5, A7, A8}",
            "sc_p2_thesis": "<em>AI Thesis:</em> Cost shocks (A2) and shift limits (A5) risk market inequality, while leisure rebounds (A7) diminish climate gains. Legal reforms (A8) must allow sector flexibility.",
            "sc_core_box": "<strong>Core Consensus:</strong> {A8} (Score: 1.00) – Modernized labor law is accepted across all perspectives.",
            "sc_dilemma_box": "<strong>Dilemma Axis:</strong> A2 ↔ A3 – Automation capacity vs. physical frontline limits.",
            "bottom_col1_title": "🤖 Dual-Stage LLM Integration",
            "bottom_col1_desc": "<strong>Pydantic-AI Powered:</strong> Stage 1 extracts unstructured news into typed <code>ArgumentationFramework</code> graphs. Stage 2 takes mathematically proven extensions and generates natural-language meta-theses.",
            "bottom_col2_title": "🏷️ Structural Roles",
            "bottom_col2_desc": "Mathematical classification by acceptance score across computed extensions:",
            "pill_green": "Core Consensus (Score = 1.0)",
            "pill_amber": "Contested (0 < Score < 1)",
            "pill_red": "Excluded / Rejected (Score = 0)",
            "bottom_col3_title": "🔒 Zero-Leakage Secrets",
            "bottom_col3_desc": "Fully automated API key resolution without hardcoding:<br>1. <code>os.environ</code><br>2. Local <code>.env</code> file<br>3. Encrypted OS Keyring (<code>db.syst.datahub</code>)",
            "footer_left": "<strong>clashpy</strong> • Data Engineering, LLM Extraction & Automated Formal Reasoning",
            "footer_right": "Specification: <code>spec/system_specification.md</code> • Generated: September 2026",
        }

    # German default
    return {
        "html_lang": "de",
        "title": "clashpy – End-to-End Datenpipeline, KI-Integration & Architektur",
        "badge": "KI-Orchestrierung & Formale Inferenz",
        "header_h1": "clashpy ⚡",
        "header_sub": "Vom heterogenen News-Datenstrom zum beweisbar konsistenten Argumentationsgraphen",
        "tag_dung": "Dung 1995 Semantik",
        "pipeline_title": "⚡ End-to-End Datenpipeline & KI-Caching-Architektur",
        "step1_title": "News Ingestion",
        "step1_desc": "RSS / Atom Feeds oder Web-APIs werden per NewsSource-Adapter abgerufen und thematisch vorgefiltert.",
        "step2_title": "KI-Graph-Extraktion",
        "step2_desc": "Pydantic-AI Agent zerlegt Text in Argumente (Claims) & Angriffsrelationen (Attacks). Kein Halluzinieren von URLs.",
        "step3_title": "Formale Inferenz",
        "step3_desc": "Mathematische Berechnung der Preferred Extensions nach Dung (1995) via Backtracking oder SAT-Solver.",
        "step4_title": "Topologie & Metriken",
        "step4_desc": "Graphentheoretische Scores (Akzeptanzrate), Streitachsen (A ↔ B) und Knotengrade (In/Out-Degrees).",
        "step4_pill": "In-Memory (Pure Functions)",
        "step5_title": "KI-Synthese & Export",
        "step5_desc": "Zweiter Pydantic-AI Agent formuliert Perspektiventhesen. Automatischer Export mit Datumsstempel nach output/.",
        "scenario_title": "📰 Konkretes Pipeline-Szenario: „4-Tage-Woche (8 Argumente im Diskurs)“",
        "sc_col1_title": "1. EXTRAHIERTE ARGUMENTE (A)",
        "sc_a1": "<strong>A1 (Gesundheit & Fokus):</strong> Senkt Burnout und Krankheitsausfälle; steigert kognitive Produktivität.",
        "sc_a2": "<strong>A2 (Lohnkosten & Inflation):</strong> Voller Lohnausgleich treibt Stückkosten und gefährdet Betriebe.",
        "sc_a3": "<strong>A3 (KI & Effizienz):</strong> KI-Prozessoptimierung und Meeting-Reduktion kompensieren 20 % Zeitverlust.",
        "sc_a4": "<strong>A4 (Employer Branding):</strong> Zieht Spitzen-Talente an, senkt Fluktuation und Recruiting-Kosten.",
        "sc_a5": "<strong>A5 (Branchenspaltung):</strong> In Pflege/Handwerk unmöglich; führt zu ungleicher Zwei-Klassen-Welt.",
        "sc_a6": "<strong>A6 (Klimaschutz & Pendeln):</strong> Ein freier Tag senkt Pendlerverkehr, Büro-Energie und CO2 nachhaltig.",
        "sc_a7": "<strong>A7 (Rebound-Effekt):</strong> Mehr Freizeit induziert emissionsintensive Reisen und Konsumausgaben.",
        "sc_a8": "<strong>A8 (Gesetzesreform):</strong> Starres Arbeitszeitrecht muss für flexible Modelle modernisiert werden.",
        "sc_col2_title": "2. GRAPH-RELATIONEN (R)",
        "sc_graph_caption": "A2 greift A1 & A6 an | A3 & A4 greifen A2 an | A2 ↔ A3 Streitachse | A5 greift A4 an | A3 greift A5 an | A7 greift A6 an | A1 greift A7 an | A8 Core",
        "node_a1_title": "A1: Gesundheit & Fokus",
        "node_a1_sub": "Umstritten (0.50)",
        "node_a2_title": "A2: Lohnkosten & Druck",
        "node_a2_sub": "Umstritten (0.50)",
        "node_a3_title": "A3: KI & Effizienz",
        "node_a3_sub": "Umstritten (0.50)",
        "node_a4_title": "A4: Employer Branding",
        "node_a4_sub": "Umstritten (0.50)",
        "node_a5_title": "A5: Branchenspaltung",
        "node_a5_sub": "Umstritten (0.50)",
        "node_a6_title": "A6: Klimaschutz",
        "node_a6_sub": "Umstritten (0.50)",
        "node_a7_title": "A7: Rebound-Effekt",
        "node_a7_sub": "Umstritten (0.50)",
        "node_a8_title": "A8: Gesetzesreform",
        "node_a8_sub": "Basis-Konsens (1.00)",
        "sc_col3_title": "3. SYNTHETISIERTE PERSPEKTIVEN",
        "sc_p1_title": "Perspektive 1 (Pro-Transformation & Klima): {A1, A3, A4, A6, A8}",
        "sc_p1_thesis": "<em>KI-These:</em> KI-Effizienz (A3) und Mitarbeiterbindung (A4) kompensieren Zeitverluste und Burnout-Kosten (A1), während Pendelreduktion (A6) das Klima schont unter neuem Recht (A8).",
        "sc_p2_title": "Perspektive 2 (Kostenrealismus & Ungleichheit): {A2, A5, A7, A8}",
        "sc_p2_thesis": "<em>KI-These:</em> Lohnkosten (A2) und Schichtgrenzen (A5) spalten den Arbeitsmarkt; Freizeit-Rebounds (A7) dämpfen Klimavorteile. Reformen (A8) müssen Branchenfreiheit wahren.",
        "sc_core_box": "<strong>Basis-Konsens:</strong> {A8} (Score: 1.00) – Reform des Arbeitszeitrechts wird von allen Perspektiven gestützt.",
        "sc_dilemma_box": "<strong>Streitachse:</strong> A2 ↔ A3 – Automatisierungspotenzial vs. physische Kapazitätsgrenzen.",
        "bottom_col1_title": "🤖 Zweistufige KI-Verdrahtung",
        "bottom_col1_desc": "<strong>Pydantic-AI Nativ:</strong> Stufe 1 wandelt Freitext in streng typisierte <code>ArgumentationFramework</code>-Objekte. Stufe 2 verdichtet berechnete mathematische Extensions in verständliche Meta-Thesen.",
        "bottom_col2_title": "🏷️ Strukturelle Rollen",
        "bottom_col2_desc": "Mathematische Klassifikation nach Akzeptanz-Score über alle Extensions:",
        "pill_green": "Basis-Konsens (Score = 1.0)",
        "pill_amber": "Umstritten (0 < Score < 1)",
        "pill_red": "Isoliert / Verworfen (Score = 0)",
        "bottom_col3_title": "🔒 Zero-Leakage Secrets",
        "bottom_col3_desc": "Vollautomatische Auflösung von API-Keys ohne Hardcoding:<br>1. <code>os.environ</code><br>2. Lokale <code>.env</code> Datei<br>3. Verschlüsselter OS Keyring (<code>db.syst.datahub</code>)",
        "footer_left": "<strong>clashpy</strong> • Data Engineering, KI-Extraktion & Formale Inferenz",
        "footer_right": "Spezifikation: <code>spec/system_specification.md</code> • Generiert: September 2026",
    }


def generate_html_poster(output_path: Path, lang: Language) -> None:
    """Generates the comprehensive HTML poster with native SVG/CSS for the given language."""
    t = _get_translations(lang)

    html_content = f"""<!DOCTYPE html>
<html lang="{t['html_lang']}">
<head>
  <meta charset="UTF-8">
  <title>{t['title']}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: rgba(22, 30, 49, 0.95);
      --card-border: rgba(255, 255, 255, 0.08);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent-blue: #38bdf8;
      --accent-purple: #818cf8;
      --accent-emerald: #34d399;
      --accent-amber: #fbbf24;
      --accent-rose: #f43f5e;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    @page {{
      size: 1600px 1200px;
      margin: 0;
    }}

    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      width: 1600px;
      min-height: 1200px;
      padding: 40px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}

    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 24px;
    }}

    .badge {{
      display: inline-block;
      padding: 6px 14px;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--accent-blue);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}

    h1 {{
      font-size: 2.8rem;
      font-weight: 900;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #ffffff 40%, var(--accent-blue) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .header-p {{
      font-size: 1.15rem;
      color: var(--text-muted);
    }}

    .tags {{
      display: flex;
      gap: 10px;
    }}

    .tag {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 8px 16px;
      border-radius: 10px;
      font-family: 'Fira Code', monospace;
      font-size: 0.9rem;
      color: var(--accent-purple);
    }}

    .pipeline-section {{
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    .section-title {{
      font-size: 1.3rem;
      font-weight: 800;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .pipeline-steps {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 14px;
    }}

    .step-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .step-num {{
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: rgba(56, 189, 248, 0.2);
      color: var(--accent-blue);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 0.8rem;
    }}

    .step-header {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .step-header h3 {{
      font-size: 1.05rem;
      color: #fff;
    }}

    .step-card p {{
      font-size: 0.85rem;
      color: var(--text-muted);
      line-height: 1.45;
    }}

    .code-pill {{
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 6px;
      padding: 8px;
      font-family: 'Fira Code', monospace;
      font-size: 0.75rem;
      color: var(--accent-blue);
      margin-top: auto;
    }}

    .scenario-container {{
      background: linear-gradient(180deg, rgba(22, 30, 49, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
      border: 1px solid rgba(56, 189, 248, 0.25);
      border-radius: 20px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}

    .scenario-grid {{
      display: grid;
      grid-template-columns: 1.2fr 1.3fr 1.2fr;
      gap: 20px;
    }}

    .sc-box {{
      background: rgba(0, 0, 0, 0.25);
      border-left: 3px solid var(--accent-blue);
      padding: 5px 10px;
      border-radius: 6px;
      font-size: 0.74rem;
      line-height: 1.3;
      margin-bottom: 5px;
    }}

    .sc-box:last-child {{
      margin-bottom: 0;
    }}

    .graph-visual {{
      background: rgba(11, 15, 25, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 250px;
    }}

    .bottom-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
    }}

    .info-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .info-card h3 {{
      font-size: 1.1rem;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .pill-group {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }}

    .pill {{
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
    }}

    .pill-green {{ background: rgba(52, 211, 153, 0.12); color: var(--accent-emerald); border: 1px solid rgba(52, 211, 153, 0.3); }}
    .pill-amber {{ background: rgba(251, 191, 36, 0.12); color: var(--accent-amber); border: 1px solid rgba(251, 191, 36, 0.3); }}
    .pill-red {{ background: rgba(244, 63, 94, 0.12); color: var(--accent-rose); border: 1px solid rgba(244, 63, 94, 0.3); }}

    .footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid var(--card-border);
      padding-top: 18px;
      font-size: 0.85rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>

  <!-- HEADER -->
  <header class="header">
    <div>
      <div class="badge">{t['badge']}</div>
      <h1>{t['header_h1']}</h1>
      <p class="header-p">{t['header_sub']}</p>
    </div>
    <div class="tags">
      <div class="tag">uv stack</div>
      <div class="tag">Pydantic v2</div>
      <div class="tag">DuckDB Cache</div>
      <div class="tag">{t['tag_dung']}</div>
    </div>
  </header>

  <!-- PIPELINE PHASES -->
  <section class="pipeline-section">
    <div class="section-title">{t['pipeline_title']}</div>
    <div class="pipeline-steps">
      
      <div class="step-card">
        <div class="step-header">
          <div class="step-num">1</div>
          <h3>{t['step1_title']}</h3>
        </div>
        <p>{t['step1_desc']}</p>
        <div class="code-pill">DuckDB: news:rss [TTL]</div>
      </div>

      <div class="step-card">
        <div class="step-header">
          <div class="step-num">2</div>
          <h3>{t['step2_title']}</h3>
        </div>
        <p>{t['step2_desc']}</p>
        <div class="code-pill">DuckDB: framework:key</div>
      </div>

      <div class="step-card">
        <div class="step-header">
          <div class="step-num">3</div>
          <h3>{t['step3_title']}</h3>
        </div>
        <p>{t['step3_desc']}</p>
        <div class="code-pill">DuckDB: extensions:naive</div>
      </div>

      <div class="step-card">
        <div class="step-header">
          <div class="step-num">4</div>
          <h3>{t['step4_title']}</h3>
        </div>
        <p>{t['step4_desc']}</p>
        <div class="code-pill">{t['step4_pill']}</div>
      </div>

      <div class="step-card">
        <div class="step-header">
          <div class="step-num">5</div>
          <h3>{t['step5_title']}</h3>
        </div>
        <p>{t['step5_desc']}</p>
        <div class="code-pill">output/YYYYMMDD_*.md</div>
      </div>

    </div>
  </section>

  <!-- SCENARIO SHOWCASE -->
  <section class="scenario-container">
    <div class="section-title">{t['scenario_title']}</div>
    <div class="scenario-grid">
      
      <div>
        <h4 style="color: var(--accent-blue); margin-bottom: 6px; font-size: 0.88rem;">{t['sc_col1_title']}</h4>
        <div class="sc-box">{t['sc_a1']}</div>
        <div class="sc-box">{t['sc_a2']}</div>
        <div class="sc-box">{t['sc_a3']}</div>
        <div class="sc-box">{t['sc_a4']}</div>
        <div class="sc-box">{t['sc_a5']}</div>
        <div class="sc-box">{t['sc_a6']}</div>
        <div class="sc-box">{t['sc_a7']}</div>
        <div class="sc-box" style="border-left-color: var(--accent-emerald);">{t['sc_a8']}</div>
      </div>

      <div>
        <h4 style="color: var(--accent-blue); margin-bottom: 6px; font-size: 0.88rem; text-align: center;">{t['sc_col2_title']}</h4>
        <div class="graph-visual">
          <svg width="460" height="248" viewBox="0 0 460 248">
            <defs>
              <marker id="arrow-red" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#f43f5e"/>
              </marker>
              <marker id="arrow-blue" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8"/>
              </marker>
            </defs>

            <!-- Attack A2 -> A1 -->
            <line x1="185" y1="24" x2="267" y2="24" stroke="#f43f5e" stroke-width="1.8" marker-end="url(#arrow-red)"/>

            <!-- Attack A3 -> A2 -->
            <line x1="75" y1="68" x2="75" y2="44" stroke="#38bdf8" stroke-width="1.8" marker-end="url(#arrow-blue)"/>
            
            <!-- Attack A2 -> A3 (Dilemma) -->
            <line x1="95" y1="38" x2="95" y2="62" stroke="#f43f5e" stroke-width="1.8" stroke-dasharray="3" marker-end="url(#arrow-red)"/>

            <!-- Attack A4 -> A2 -->
            <path d="M 275 74 L 189 34" stroke="#38bdf8" stroke-width="1.8" marker-end="url(#arrow-blue)"/>

            <!-- Attack A5 -> A4 -->
            <path d="M 185 137 L 271 94" stroke="#f43f5e" stroke-width="1.8" marker-end="url(#arrow-red)"/>

            <!-- Attack A3 -> A5 -->
            <line x1="75" y1="98" x2="75" y2="122" stroke="#38bdf8" stroke-width="1.8" marker-end="url(#arrow-blue)"/>

            <!-- Attack A7 -> A6 -->
            <path d="M 185 197 L 271 154" stroke="#f43f5e" stroke-width="1.8" marker-end="url(#arrow-red)"/>

            <!-- Attack A1 -> A7 -->
            <path d="M 275 32 L 189 191" stroke="#38bdf8" stroke-width="1.8" marker-end="url(#arrow-blue)"/>

            <!-- Attack A2 -> A6 -->
            <path d="M 185 34 L 271 137" stroke="#f43f5e" stroke-width="1.8" marker-end="url(#arrow-red)"/>

            <!-- Node A2 -->
            <rect x="15" y="8" width="170" height="30" rx="6" fill="#1e293b" stroke="#f43f5e" stroke-width="1.6"/>
            <text x="100" y="21" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a2_title']}</text>
            <text x="100" y="32" fill="#fbbf24" font-size="8" font-family="sans-serif" text-anchor="middle">{t['node_a2_sub']}</text>

            <!-- Node A1 -->
            <rect x="275" y="8" width="170" height="30" rx="6" fill="#1e293b" stroke="#fbbf24" stroke-width="1.6"/>
            <text x="360" y="21" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a1_title']}</text>
            <text x="360" y="32" fill="#fbbf24" font-size="8" font-family="sans-serif" text-anchor="middle">{t['node_a1_sub']}</text>

            <!-- Node A3 -->
            <rect x="15" y="68" width="170" height="30" rx="6" fill="#1e293b" stroke="#38bdf8" stroke-width="1.6"/>
            <text x="100" y="81" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a3_title']}</text>
            <text x="100" y="92" fill="#fbbf24" font-size="8" font-family="sans-serif" text-anchor="middle">{t['node_a3_sub']}</text>

            <!-- Node A4 -->
            <rect x="275" y="68" width="170" height="30" rx="6" fill="#1e293b" stroke="#fbbf24" stroke-width="1.6"/>
            <text x="360" y="81" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a4_title']}</text>
            <text x="360" y="92" fill="#fbbf24" font-size="8" font-family="sans-serif" text-anchor="middle">{t['node_a4_sub']}</text>

            <!-- Node A5 -->
            <rect x="15" y="128" width="170" height="30" rx="6" fill="#1e293b" stroke="#f43f5e" stroke-width="1.6"/>
            <text x="100" y="141" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a5_title']}</text>
            <text x="100" y="152" fill="#fbbf24" font-size="8" font-family="sans-serif" text-anchor="middle">{t['node_a5_sub']}</text>

            <!-- Node A6 -->
            <rect x="275" y="128" width="170" height="30" rx="6" fill="#1e293b" stroke="#fbbf24" stroke-width="1.6"/>
            <text x="360" y="141" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a6_title']}</text>
            <text x="360" y="152" fill="#fbbf24" font-size="8" font-family="sans-serif" text-anchor="middle">{t['node_a6_sub']}</text>

            <!-- Node A7 -->
            <rect x="15" y="188" width="170" height="30" rx="6" fill="#1e293b" stroke="#f43f5e" stroke-width="1.6"/>
            <text x="100" y="201" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a7_title']}</text>
            <text x="100" y="212" fill="#fbbf24" font-size="8" font-family="sans-serif" text-anchor="middle">{t['node_a7_sub']}</text>

            <!-- Node A8 (Core Consensus) -->
            <rect x="275" y="188" width="170" height="30" rx="6" fill="#1e293b" stroke="#34d399" stroke-width="2"/>
            <text x="360" y="201" fill="#fff" font-size="10" font-family="sans-serif" text-anchor="middle" font-weight="bold">{t['node_a8_title']}</text>
            <text x="360" y="212" fill="#34d399" font-size="8" font-family="sans-serif" text-anchor="middle" font-weight="600">{t['node_a8_sub']}</text>
          </svg>
          <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px; text-align: center;">
            {t['sc_graph_caption']}
          </div>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; justify-content: space-between;">
        <h4 style="color: var(--accent-blue); margin-bottom: 6px; font-size: 0.88rem;">{t['sc_col3_title']}</h4>
        <div class="sc-box" style="border-left-color: var(--accent-emerald); margin-bottom: 6px;">
          <strong style="color: var(--accent-emerald); font-size: 0.8rem;">{t['sc_p1_title']}</strong><br>
          <span style="font-size: 0.74rem;">{t['sc_p1_thesis']}</span>
        </div>
        <div class="sc-box" style="border-left-color: var(--accent-amber); margin-bottom: 6px;">
          <strong style="color: var(--accent-amber); font-size: 0.8rem;">{t['sc_p2_title']}</strong><br>
          <span style="font-size: 0.74rem;">{t['sc_p2_thesis']}</span>
        </div>
        <div class="sc-box" style="border-left-color: var(--accent-blue); font-size: 0.74rem; background: rgba(56, 189, 248, 0.08);">
          <div>{t['sc_core_box']}</div>
          <div style="margin-top: 3px; color: var(--accent-rose);">{t['sc_dilemma_box']}</div>
        </div>
      </div>

    </div>
  </section>

  <!-- ARCHITECTURE & METRICS -->
  <section class="bottom-grid">
    <div class="info-card">
      <h3>{t['bottom_col1_title']}</h3>
      <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.5;">
        {t['bottom_col1_desc']}
      </p>
      <div class="code-pill">uv run clashpy --solver naive</div>
    </div>

    <div class="info-card">
      <h3>{t['bottom_col2_title']}</h3>
      <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.5;">
        {t['bottom_col2_desc']}
      </p>
      <div class="pill-group">
        <span class="pill pill-green">{t['pill_green']}</span>
        <span class="pill pill-amber">{t['pill_amber']}</span>
        <span class="pill pill-red">{t['pill_red']}</span>
      </div>
    </div>

    <div class="info-card">
      <h3>{t['bottom_col3_title']}</h3>
      <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.5;">
        {t['bottom_col3_desc']}
      </p>
    </div>
  </section>

  <!-- FOOTER -->
  <footer class="footer">
    <div>{t['footer_left']}</div>
    <div>{t['footer_right']}</div>
  </footer>

</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"✓ HTML poster written: {output_path}")


def convert_html_to_pdf_and_png(html_path: Path, docs_dir: Path, lang: Language) -> None:
    """Renders HTML via Headless Chrome to PDF and PNG with language suffix."""
    chrome_bin = _find_chrome()
    if not chrome_bin:
        print("⚠️  No Google Chrome / Chromium found. Skipping PDF/PNG export.")
        return

    pdf_out = docs_dir / f"poster_{lang}.pdf"
    png_out = docs_dir / f"poster_{lang}.png"

    # PDF Export (exact canvas size)
    cmd_pdf = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_out.resolve()}",
        str(html_path.resolve()),
    ]
    res_pdf = subprocess.run(cmd_pdf, capture_output=True, text=True)
    if res_pdf.returncode == 0:
        print(f"✓ PDF poster written: {pdf_out}")
    else:
        print(f"⚠️ Error during PDF generation: {res_pdf.stderr}")

    # PNG Export (matching 1600x1200 viewport)
    cmd_png = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=1600,1200",
        f"--screenshot={png_out.resolve()}",
        str(html_path.resolve()),
    ]
    res_png = subprocess.run(cmd_png, capture_output=True, text=True)
    if res_png.returncode == 0:
        print(f"✓ PNG poster written: {png_out}")
    else:
        print(f"⚠️ Error during PNG generation: {res_png.stderr}")


class CodeChangeHandler(FileSystemEventHandler):
    """Watches source code changes and triggers automated documentation rebuilds."""

    def __init__(self, docs_dir: Path, lang: Language):
        self.docs_dir = docs_dir
        self.lang = lang
        self.last_trigger = 0.0

    def on_any_event(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith((".py", ".toml", ".md")):
            return

        now = time.time()
        # Debounce: minimum 2 seconds interval
        if now - self.last_trigger < 2.0:
            return
        self.last_trigger = now

        print(f"\n🔄 Change detected in: {event.src_path}")
        print(f"🚀 Rebuilding documentation & posters (language: {self.lang})...")
        build_docs_for_language(self.docs_dir, self.lang)
        print("✨ Documentation rebuild complete!\n")


def build_docs_for_language(docs_dir: Path, lang: Language) -> None:
    """Builds HTML, PDF, and PNG for a single target language."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    html_file = docs_dir / f"poster_{lang}.html"
    generate_html_poster(html_file, lang)
    convert_html_to_pdf_and_png(html_file, docs_dir, lang)


def build_docs(docs_dir: Path, language: str) -> None:
    """Performs doc builds for requested language ('de', 'en', or 'all')."""
    languages: list[Language] = ["de", "en"] if language == "all" else [language]  # type: ignore

    for lang in languages:
        print(f"🛠️  Generating assets for locale: _{lang}")
        build_docs_for_language(docs_dir, lang)


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated generation of documentation, posters, and assets.")
    parser.add_argument("--docs-dir", default=str(DOCS_DIR), help="Output directory for generated assets")
    parser.add_argument(
        "--language",
        choices=["de", "en", "all"],
        default="de",
        help="Target locale: 'de' (German), 'en' (English), or 'all' (default: de)",
    )
    parser.add_argument("--watch", action="store_true", help="Watches src/ for code changes and automatically rebuilds docs.")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    build_docs(docs_dir, args.language)

    if args.watch:
        target_lang = args.language
        print(f"\n👀 Watch mode active ({target_lang}): monitoring changes in {SRC_DIR} ... (Press Ctrl+C to terminate)")
        event_handler = CodeChangeHandler(docs_dir, target_lang if target_lang != "all" else "de")
        observer = Observer()
        observer.schedule(event_handler, path=str(SRC_DIR), recursive=True)
        observer.schedule(event_handler, path=str(PROJECT_ROOT / "pyproject.toml"), recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\n👋 Watcher terminated.")
        observer.join()


if __name__ == "__main__":
    main()
