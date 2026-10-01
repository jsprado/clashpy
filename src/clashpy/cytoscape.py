"""
Cytoscape.js integration for clashpy Argumentation Frameworks.

Provides functions to:
1. Transform ArgumentationFramework & metrics into Cytoscape.js JSON elements.
2. Enrich nodes with media source categories (international, national, tech, business, search).
3. Export Cytoscape.js compatible JSON.
4. Generate standalone, interactive HTML dashboards with Cytoscape.js visualization,
   crystal-clear readable argument claims, filtering by Dung preferred extensions,
   multi-perspective media source filters, layout switching, inspector panel, and PNG/JSON export.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import jinja2

from clashpy.adapters.news_sources.sources_config import categorize_source_url
from clashpy.core.metrics import (
    classify_arguments,
    compute_argument_scores,
    compute_attack_degrees,
    detect_dilemma_axes,
)
from clashpy.core.models import ArgumentationFramework, FullAnalysisResult


def build_cytoscape_elements(
    af: ArgumentationFramework,
    scores: dict[str, float] | None = None,
    classification: dict[str, str] | None = None,
    extensions: list[set[str]] | None = None,
    dilemma_axes: list[tuple[str, str, str, str]] | None = None,
    degrees: dict[str, dict[str, int]] | None = None,
) -> list[dict[str, Any]]:
    """Convert an ArgumentationFramework and analysis results into Cytoscape.js elements."""
    arg_ids = [arg.id for arg in af.arguments]

    # Fill default metrics if not provided
    if extensions is None:
        extensions = []
    if scores is None:
        scores = compute_argument_scores(arg_ids, extensions) if extensions else {a: 0.0 for a in arg_ids}
    if classification is None:
        classification = classify_arguments(scores) if extensions else {a: "unclassified" for a in arg_ids}
    if degrees is None:
        degrees = compute_attack_degrees(arg_ids, af.attacks)
    if dilemma_axes is None:
        dilemma_axes = detect_dilemma_axes(af.attacks)

    # Set of mutual attack pairs for quick lookup
    mutual_pairs = set()
    for left, right, _, _ in dilemma_axes:
        mutual_pairs.add((left, right))
        mutual_pairs.add((right, left))

    elements: list[dict[str, Any]] = []

    # 1. Nodes (Arguments)
    for arg in af.arguments:
        arg_score = scores.get(arg.id, 0.0)
        arg_cls = classification.get(arg.id, "unclassified")
        arg_deg = degrees.get(arg.id, {"in_degree": 0, "out_degree": 0})
        member_exts = [
            idx + 1 for idx, ext in enumerate(extensions) if arg.id in ext
        ]

        # Automatic media source category classification
        source_category = categorize_source_url(arg.source_url)

        # Readable card label: ID + Classification + Claim
        card_label = f"[{arg.id}] {arg_cls.upper()} ({arg_score:.2f})\n\n{arg.claim}"
        compact_label = f"[{arg.id}] {arg_score:.2f}"

        # Node height estimation based on claim length for optimal padding
        claim_len = len(arg.claim)
        node_height = max(80, min(140, 70 + (claim_len // 35) * 16))

        classes_list = [f"cls-{arg_cls}", f"src-{source_category}"]
        classes_list.extend(f"ext-{e}" for e in member_exts)

        elements.append(
            {
                "group": "nodes",
                "data": {
                    "id": arg.id,
                    "label": card_label,
                    "card_label": card_label,
                    "compact_label": compact_label,
                    "claim": arg.claim,
                    "source_url": arg.source_url,
                    "source_category": source_category,
                    "score": round(arg_score, 2),
                    "classification": arg_cls,
                    "in_degree": arg_deg.get("in_degree", 0),
                    "out_degree": arg_deg.get("out_degree", 0),
                    "extensions": member_exts,
                    "in_any_extension": len(member_exts) > 0,
                    "node_height": node_height,
                },
                "classes": " ".join(classes_list),
            }
        )

    # 2. Edges (Attacks)
    for attack in af.attacks:
        edge_id = f"{attack.attacker_id}->{attack.target_id}"
        is_mutual = (attack.attacker_id, attack.target_id) in mutual_pairs

        elements.append(
            {
                "group": "edges",
                "data": {
                    "id": edge_id,
                    "source": attack.attacker_id,
                    "target": attack.target_id,
                    "reason": attack.reason,
                    "label": attack.reason,
                    "is_mutual": is_mutual,
                },
                "classes": "mutual-attack" if is_mutual else "direct-attack",
            }
        )

    return elements


def build_cytoscape_data(
    af: ArgumentationFramework,
    extensions: list[set[str]] | None = None,
    scores: dict[str, float] | None = None,
    classification: dict[str, str] | None = None,
    dilemma_axes: list[tuple[str, str, str, str]] | None = None,
    degrees: dict[str, dict[str, int]] | None = None,
    synthesis: FullAnalysisResult | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Return a complete dictionary containing Cytoscape elements and analysis metadata."""
    elements = build_cytoscape_elements(
        af=af,
        scores=scores,
        classification=classification,
        extensions=extensions,
        dilemma_axes=dilemma_axes,
        degrees=degrees,
    )

    # Calculate source category stats
    nodes = [e["data"] for e in elements if e["group"] == "nodes"]
    source_stats: dict[str, int] = {}
    for n in nodes:
        cat = n.get("source_category", "general")
        source_stats[cat] = source_stats.get(cat, 0) + 1

    return {
        "format": "clashpy-cytoscape-v1",
        "topic": topic or af.topic,
        "generated_at": datetime.now(UTC).isoformat(),
        "stats": {
            "argument_count": len(af.arguments),
            "attack_count": len(af.attacks),
            "extension_count": len(extensions or []),
            "dilemma_axis_count": len(dilemma_axes or []),
            "source_categories": source_stats,
        },
        "elements": elements,
        "extensions": [sorted(ext) for ext in (extensions or [])],
        "dilemma_axes": [
            {
                "source": left,
                "target": right,
                "source_reason": left_reason,
                "target_reason": right_reason,
            }
            for left, right, left_reason, right_reason in (dilemma_axes or [])
        ],
        "synthesis": synthesis.model_dump() if synthesis else None,
    }


def export_cytoscape_json(
    af: ArgumentationFramework,
    extensions: list[set[str]] | None = None,
    scores: dict[str, float] | None = None,
    classification: dict[str, str] | None = None,
    dilemma_axes: list[tuple[str, str, str, str]] | None = None,
    degrees: dict[str, dict[str, int]] | None = None,
    synthesis: FullAnalysisResult | None = None,
    topic: str | None = None,
    indent: int = 2,
) -> str:
    """Generate a Cytoscape JSON string for the given ArgumentationFramework."""
    data = build_cytoscape_data(
        af=af,
        extensions=extensions,
        scores=scores,
        classification=classification,
        dilemma_axes=dilemma_axes,
        degrees=degrees,
        synthesis=synthesis,
        topic=topic,
    )
    return json.dumps(data, ensure_ascii=False, indent=indent)


HTML_TEMPLATE = jinja2.Template("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>clashpy ⚡ Cytoscape Graph – {{ topic | e }}</title>
  <!-- Cytoscape.js & Dagre Layout from CDN -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.4/cytoscape.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-main: #090d16;
      --bg-panel: rgba(15, 23, 42, 0.88);
      --bg-card: #1e293b;
      --bg-card-hover: #334155;
      --border-color: rgba(51, 65, 85, 0.7);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-core: #10b981;
      --accent-core-bg: #064e3b;
      --accent-contested: #f59e0b;
      --accent-contested-bg: #451a03;
      --accent-rejected: #ef4444;
      --accent-rejected-bg: #450a0a;
      --accent-blue: #38bdf8;
      --accent-purple: #a855f7;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'Fira Code', monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: var(--font-sans);
      background-color: var(--bg-main);
      color: var(--text-main);
      overflow: hidden;
      height: 100vh;
      width: 100vw;
      display: flex;
      flex-direction: column;
    }

    /* Top Navigation */
    header {
      background: var(--bg-panel);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--border-color);
      padding: 10px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 20;
    }

    .brand-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .logo-badge {
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      color: #0f172a;
      font-weight: 800;
      font-size: 13px;
      padding: 4px 10px;
      border-radius: 6px;
      letter-spacing: 0.5px;
    }

    h1 {
      font-size: 17px;
      font-weight: 700;
      color: var(--text-main);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 550px;
    }

    .meta-badges {
      display: flex;
      gap: 8px;
      align-items: center;
    }

    .meta-pill {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      font-size: 11px;
      padding: 3px 9px;
      border-radius: 20px;
      font-family: var(--font-mono);
    }

    .meta-pill strong {
      color: var(--text-main);
    }

    /* Workspace */
    .workspace {
      display: flex;
      flex: 1;
      position: relative;
      overflow: hidden;
    }

    /* Left Controls Panel */
    .controls-panel {
      width: 330px;
      background: var(--bg-panel);
      backdrop-filter: blur(16px);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      z-index: 10;
      overflow-y: auto;
      padding: 14px;
      gap: 12px;
    }

    .section-box {
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 12px;
    }

    .section-title {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .control-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    label {
      font-size: 12px;
      color: var(--text-muted);
    }

    select, input[type="text"] {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px 12px;
      border-radius: 6px;
      font-family: var(--font-sans);
      font-size: 13px;
      outline: none;
      transition: border-color 0.2s;
      width: 100%;
    }

    select:focus, input[type="text"]:focus {
      border-color: var(--accent-blue);
    }

    .checkbox-row {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--text-main);
      cursor: pointer;
      user-select: none;
      padding: 4px 0;
    }

    .checkbox-row input {
      accent-color: var(--accent-blue);
      cursor: pointer;
    }

    .btn-group {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
    }

    button {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 7px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
    }

    button:hover {
      background: var(--bg-card-hover);
      border-color: var(--accent-blue);
    }

    button.primary {
      background: linear-gradient(135deg, #0284c7, #2563eb);
      border: none;
      color: white;
    }

    button.primary:hover {
      background: linear-gradient(135deg, #0369a1, #1d4ed8);
    }

    /* Mode Switcher Toggle */
    .mode-switch {
      display: grid;
      grid-template-columns: 1fr 1fr;
      background: rgba(15, 23, 42, 0.9);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      padding: 2px;
      gap: 2px;
    }

    .mode-switch button {
      border: none;
      background: transparent;
      padding: 6px;
      font-size: 11px;
      border-radius: 4px;
      color: var(--text-muted);
    }

    .mode-switch button.active {
      background: var(--bg-card);
      color: var(--accent-blue);
      font-weight: 700;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    }

    /* Source & Extension Buttons */
    .filter-buttons {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .filter-btn {
      justify-content: space-between;
      text-align: left;
      padding: 7px 9px;
    }

    .filter-btn.active {
      border-color: var(--accent-blue);
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent-blue);
    }

    .badge-count {
      background: rgba(0, 0, 0, 0.3);
      padding: 2px 6px;
      border-radius: 10px;
      font-size: 11px;
      font-family: var(--font-mono);
    }

    /* Legend */
    .legend-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 11px;
      margin-bottom: 5px;
    }

    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
      flex-shrink: 0;
    }

    .dot-core { background: var(--accent-core); box-shadow: 0 0 6px var(--accent-core); }
    .dot-contested { background: var(--accent-contested); box-shadow: 0 0 6px var(--accent-contested); }
    .dot-rejected { background: var(--accent-rejected); box-shadow: 0 0 6px var(--accent-rejected); }
    .dot-attack { background: #ef4444; }
    .dot-mutual { background: #f43f5e; border: 2px dashed #fbbf24; }

    /* Graph Canvas */
    #cy {
      flex: 1;
      height: 100%;
      background: radial-gradient(circle at center, #111827 0%, #090d16 100%);
      position: relative;
    }

    .canvas-overlay {
      position: absolute;
      top: 14px;
      right: 14px;
      display: flex;
      gap: 8px;
      z-index: 10;
    }

    /* Right Inspector Panel */
    .inspector-panel {
      width: 370px;
      background: var(--bg-panel);
      backdrop-filter: blur(16px);
      border-left: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      z-index: 10;
      overflow-y: auto;
      padding: 14px;
      gap: 12px;
    }

    .empty-state {
      text-align: center;
      padding: 35px 15px;
      color: var(--text-muted);
      font-size: 13px;
      line-height: 1.5;
    }

    .inspector-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .node-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .node-id {
      font-family: var(--font-mono);
      font-size: 20px;
      font-weight: 700;
      color: var(--accent-blue);
    }

    .badge-group {
      display: flex;
      gap: 6px;
    }

    .cls-badge, .src-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .cls-core { background: rgba(16, 185, 129, 0.2); color: var(--accent-core); border: 1px solid var(--accent-core); }
    .cls-contested { background: rgba(245, 158, 11, 0.2); color: var(--accent-contested); border: 1px solid var(--accent-contested); }
    .cls-rejected { background: rgba(239, 68, 68, 0.2); color: var(--accent-rejected); border: 1px solid var(--accent-rejected); }
    .cls-unclassified { background: rgba(100, 116, 139, 0.2); color: #94a3b8; border: 1px solid #64748b; }

    .src-badge {
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent-blue);
      border: 1px solid rgba(56, 189, 248, 0.4);
    }

    .claim-box {
      background: rgba(15, 23, 42, 0.7);
      border-left: 3px solid var(--accent-blue);
      padding: 10px 12px;
      font-size: 13px;
      line-height: 1.5;
      border-radius: 0 6px 6px 0;
      color: var(--text-main);
      word-break: break-word;
    }

    .property-row {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      padding: 4px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .property-label {
      color: var(--text-muted);
    }

    .property-value {
      font-family: var(--font-mono);
      font-weight: 600;
    }

    .attack-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 12px;
    }

    .attack-item {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      padding: 8px 10px;
    }

    .attack-item-header {
      display: flex;
      justify-content: space-between;
      font-family: var(--font-mono);
      font-weight: 600;
      color: #f87171;
      margin-bottom: 4px;
    }

    .attack-reason {
      color: var(--text-muted);
      font-size: 11px;
      line-height: 1.4;
    }

    .source-link {
      color: var(--accent-blue);
      text-decoration: none;
      word-break: break-all;
      font-size: 11px;
      display: inline-block;
      margin-top: 4px;
    }

    .source-link:hover {
      text-decoration: underline;
    }

    .perspectives-box {
      margin-top: 6px;
    }

    .thesis-card {
      background: rgba(15, 23, 42, 0.7);
      border-left: 3px solid var(--accent-purple);
      border-radius: 0 6px 6px 0;
      padding: 8px 10px;
      margin-bottom: 8px;
      font-size: 12px;
    }

    .thesis-title {
      font-weight: 700;
      color: #c084fc;
      margin-bottom: 4px;
    }

    .thesis-body {
      color: var(--text-muted);
      line-height: 1.4;
    }

    /* Scrollbars */
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.1);
    }
    ::-webkit-scrollbar-thumb {
      background: var(--border-color);
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: var(--text-muted);
    }
  </style>
</head>
<body>

  <header>
    <div class="brand-title">
      <span class="logo-badge">clashpy ⚡</span>
      <h1 title="{{ topic | e }}">{{ topic | e }}</h1>
    </div>

    <div class="meta-badges">
      <span class="meta-pill">Solver: <strong>{{ solver_name | e }}</strong> ({{ semantics_name | e }})</span>
      <span class="meta-pill">Args: <strong>{{ argument_count }}</strong></span>
      <span class="meta-pill">Attacks: <strong>{{ attack_count }}</strong></span>
      <span class="meta-pill">Exts: <strong>{{ extension_count }}</strong></span>
      <span class="meta-pill">Dilemmas: <strong>{{ dilemma_count }}</strong></span>
    </div>
  </header>

  <div class="workspace">

    <div class="controls-panel">
      <!-- View Display Mode -->
      <div class="section-box">
        <div class="section-title">Card View & Readability</div>
        <div class="control-group">
          <div class="mode-switch">
            <button id="btnModeCards" class="active">🗂️ Full Claims</button>
            <button id="btnModeCompact">📌 Compact IDs</button>
          </div>
          <label class="checkbox-row">
            <input type="checkbox" id="chkShowEdgeLabels">
            <span>Show attack reasons on arrows</span>
          </label>
        </div>
      </div>

      <!-- Multi-Perspective Source Filter -->
      <div class="section-box">
        <div class="section-title">
          <span>Media Source Filter</span>
        </div>
        <div class="filter-buttons" id="srcBtnContainer">
          <button class="filter-btn active src-btn" data-src="all">
            <span>🌐 All Sources</span>
            <span class="badge-count">{{ argument_count }}</span>
          </button>
          <button class="filter-btn src-btn" data-src="international">
            <span>🌍 International Leitmedien</span>
            <span class="badge-count" id="count-international">0</span>
          </button>
          <button class="filter-btn src-btn" data-src="national">
            <span>🇩🇪 Nationale Leitmedien</span>
            <span class="badge-count" id="count-national">0</span>
          </button>
          <button class="filter-btn src-btn" data-src="tech">
            <span>💻 Tech & Fachpresse</span>
            <span class="badge-count" id="count-tech">0</span>
          </button>
          <button class="filter-btn src-btn" data-src="business">
            <span>📊 Wirtschaft & Policy</span>
            <span class="badge-count" id="count-business">0</span>
          </button>
          <button class="filter-btn src-btn" data-src="search">
            <span>🔍 Deep Search Articles</span>
            <span class="badge-count" id="count-search">0</span>
          </button>
        </div>
      </div>

      <!-- Search & Filter -->
      <div class="section-box">
        <div class="section-title">Search & Filter</div>
        <div class="control-group">
          <input type="text" id="searchInput" placeholder="Search ID, claim or URL..." autocomplete="off">
        </div>
      </div>

      <!-- Layout Controls -->
      <div class="section-box">
        <div class="section-title">Graph Layout</div>
        <div class="control-group">
          <select id="layoutSelect">
            <option value="dagre" selected>Directed Flow (Dagre)</option>
            <option value="cose">Force-Directed (Physics)</option>
            <option value="breadthfirst">Hierarchy Tree</option>
            <option value="concentric">Concentric (by Acceptance Score)</option>
            <option value="circle">Circle</option>
            <option value="grid">Grid</option>
          </select>
          <div class="btn-group">
            <button id="btnFit">🔍 Fit View</button>
            <button id="btnReset">↺ Reset</button>
          </div>
        </div>
      </div>

      <!-- Preferred Extensions Selector -->
      <div class="section-box">
        <div class="section-title">
          <span>Preferred Extensions</span>
          <span class="badge-count">{{ extension_count }}</span>
        </div>
        <div class="filter-buttons" id="extBtnContainer">
          <button class="filter-btn active ext-btn" data-ext="all">
            <span>Show All Extensions</span>
            <span class="badge-count">{{ argument_count }}</span>
          </button>
          {% for ext in extensions %}
          <button class="filter-btn ext-btn" data-ext="{{ loop.index }}">
            <span>Extension {{ loop.index }}</span>
            <span class="badge-count">{{ ext | length }} args</span>
          </button>
          {% endfor %}
        </div>
      </div>

      <!-- Legend -->
      <div class="section-box">
        <div class="section-title">Semantic Legend</div>
        <div class="legend-item">
          <span class="legend-dot dot-core"></span>
          <span><strong>Core (1.00):</strong> In all extensions</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-contested"></span>
          <span><strong>Contested:</strong> In some extensions</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-rejected"></span>
          <span><strong>Rejected (0.00):</strong> In no extension</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-attack"></span>
          <span><strong>Attack (R):</strong> Conflict relation</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-mutual"></span>
          <span><strong>Dilemma Axis:</strong> Mutual attack (A ↔ B)</span>
        </div>
      </div>

      <!-- Export Tools -->
      <div class="section-box">
        <div class="section-title">Export Options</div>
        <div class="control-group">
          <button class="primary" id="btnExportPng">📷 Export as High-Res PNG</button>
          <button id="btnExportJson">💾 Download Cytoscape JSON</button>
        </div>
      </div>
    </div>

    <div id="cy">
      <div class="canvas-overlay">
        <button id="btnCenter">Fit View</button>
      </div>
    </div>

    <div class="inspector-panel" id="inspectorPanel">
      <div class="section-title">Argument Inspector</div>
      <div id="inspectorContent">
        <div class="empty-state">
          👉 <strong>Klicken Sie auf ein Argument oder einen Pfeil</strong>, um vollständige Claims, Begründungen, Medienkategorien und Extension-Zugehörigkeiten einzusehen.
        </div>
      </div>

      {% if synthesis and synthesis.theses %}
      <div class="section-box perspectives-box">
        <div class="section-title">AI Synthesis Perspectives</div>
        {% for t in synthesis.theses %}
        <div class="thesis-card">
          <div class="thesis-title">Perspective {{ t.group_id }}: {{ t.title | e }}</div>
          <div class="thesis-body">{{ t.thesis | e }}</div>
        </div>
        {% endfor %}
      </div>
      {% endif %}

    </div>
  </div>

  <script>
    const graphData = {{ data_json | safe }};
    const elementsData = {{ elements_json | safe }};
    let currentMode = 'cards';
    let showEdgeLabels = false;
    let currentExtFilter = 'all';
    let currentSrcFilter = 'all';

    // Populate source category count badges
    if (graphData.stats && graphData.stats.source_categories) {
      const cats = graphData.stats.source_categories;
      for (const [cat, count] of Object.entries(cats)) {
        const el = document.getElementById(`count-${cat}`);
        if (el) el.textContent = count;
      }
    }

    const cy = cytoscape({
      container: document.getElementById('cy'),
      elements: elementsData,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        {
          selector: 'node',
          style: {
            'shape': 'roundrectangle',
            'width': '280px',
            'height': 'data(node_height)',
            'padding': '14px',
            'background-color': '#1e293b',
            'border-width': '2px',
            'border-color': '#475569',
            'label': 'data(label)',
            'color': '#f8fafc',
            'font-family': 'Inter, system-ui, sans-serif',
            'font-size': '11.5px',
            'font-weight': 500,
            'line-height': 1.35,
            'text-wrap': 'wrap',
            'text-max-width': '250px',
            'text-valign': 'center',
            'text-halign': 'center',
            'overlay-opacity': 0,
            'transition-property': 'background-color, border-color, opacity, border-width, width, height',
            'transition-duration': '0.25s'
          }
        },
        {
          selector: 'node.cls-core',
          style: {
            'border-color': '#10b981',
            'border-width': '3px',
            'background-color': '#064e3b',
            'color': '#f0fdf4'
          }
        },
        {
          selector: 'node.cls-contested',
          style: {
            'border-color': '#f59e0b',
            'border-width': '2.5px',
            'background-color': '#451a03',
            'color': '#fffbeb'
          }
        },
        {
          selector: 'node.cls-rejected',
          style: {
            'border-color': '#ef4444',
            'border-width': '2.5px',
            'background-color': '#450a0a',
            'color': '#fef2f2'
          }
        },
        {
          selector: 'node.compact-mode',
          style: {
            'width': '85px',
            'height': '40px',
            'padding': '6px',
            'font-size': '13px',
            'font-weight': 700,
            'text-max-width': '75px'
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#38bdf8',
            'border-width': '4px',
            'background-color': '#0369a1',
            'color': '#ffffff'
          }
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#38bdf8',
            'border-width': '3.5px'
          }
        },
        {
          selector: 'node.dimmed',
          style: {
            'opacity': 0.12
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2.5,
            'line-color': '#ef4444',
            'target-arrow-color': '#ef4444',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.25,
            'curve-style': 'bezier',
            'opacity': 0.85,
            'overlay-opacity': 0,
            'font-size': '10px',
            'color': '#fca5a5',
            'text-background-color': '#0f172a',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-wrap': 'wrap',
            'text-max-width': '180px',
            'edge-text-rotation': 'autorotate',
            'label': '',
            'transition-property': 'line-color, target-arrow-color, width, opacity',
            'transition-duration': '0.2s'
          }
        },
        {
          selector: 'edge.show-labels',
          style: {
            'label': 'data(label)'
          }
        },
        {
          selector: 'edge.mutual-attack',
          style: {
            'line-color': '#f43f5e',
            'target-arrow-color': '#f43f5e',
            'line-style': 'dashed',
            'width': 3
          }
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
            'width': 4.5,
            'opacity': 1
          }
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
            'width': 3.5,
            'opacity': 1
          }
        },
        {
          selector: 'edge.dimmed',
          style: {
            'opacity': 0.08
          }
        }
      ]
    });

    function applyLayout(name) {
      let options = { name: name, animate: true, animationDuration: 450 };
      if (name === 'dagre') {
        options.rankDir = 'TB';
        options.nodeSep = currentMode === 'cards' ? 70 : 45;
        options.rankSep = currentMode === 'cards' ? 100 : 70;
      } else if (name === 'cose') {
        options.nodeRepulsion = currentMode === 'cards' ? 950000 : 450000;
        options.idealEdgeLength = currentMode === 'cards' ? 180 : 100;
        options.gravity = 0.2;
      } else if (name === 'concentric') {
        options.concentric = function(node) {
          return (node.data('score') || 0) * 10;
        };
        options.levelWidth = function() { return 2; };
      }
      cy.layout(options).run();
    }

    applyLayout('dagre');

    function applyFilters() {
      cy.elements().removeClass('dimmed highlighted');

      const extNum = currentExtFilter === 'all' ? null : parseInt(currentExtFilter, 10);
      const srcCat = currentSrcFilter === 'all' ? null : currentSrcFilter;

      cy.nodes().forEach(node => {
        let matchExt = true;
        let matchSrc = true;

        if (extNum !== null) {
          const exts = node.data('extensions') || [];
          matchExt = exts.includes(extNum);
        }

        if (srcCat !== null) {
          const cat = node.data('source_category') || 'general';
          matchSrc = (cat === srcCat);
        }

        if (matchExt && matchSrc) {
          if (extNum !== null || srcCat !== null) {
            node.addClass('highlighted');
          }
        } else {
          node.addClass('dimmed');
        }
      });

      cy.edges().forEach(edge => {
        const src = edge.source();
        const tgt = edge.target();
        if (src.hasClass('highlighted') && tgt.hasClass('highlighted')) {
          edge.addClass('highlighted');
        } else if (src.hasClass('dimmed') || tgt.hasClass('dimmed')) {
          edge.addClass('dimmed');
        }
      });
    }

    function updateViewMode(mode) {
      currentMode = mode;
      if (mode === 'compact') {
        cy.nodes().addClass('compact-mode').forEach(node => {
          node.data('label', node.data('compact_label'));
        });
      } else {
        cy.nodes().removeClass('compact-mode').forEach(node => {
          node.data('label', node.data('card_label'));
        });
      }
      applyLayout(document.getElementById('layoutSelect').value);
    }

    document.getElementById('btnModeCards').addEventListener('click', function() {
      document.getElementById('btnModeCards').classList.add('active');
      document.getElementById('btnModeCompact').classList.remove('active');
      updateViewMode('cards');
    });

    document.getElementById('btnModeCompact').addEventListener('click', function() {
      document.getElementById('btnModeCompact').classList.add('active');
      document.getElementById('btnModeCards').classList.remove('active');
      updateViewMode('compact');
    });

    document.getElementById('chkShowEdgeLabels').addEventListener('change', function(e) {
      showEdgeLabels = e.target.checked;
      if (showEdgeLabels) {
        cy.edges().addClass('show-labels');
      } else {
        cy.edges().removeClass('show-labels');
      }
    });

    // Source Filter Buttons
    document.querySelectorAll('.src-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        document.querySelectorAll('.src-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        currentSrcFilter = this.getAttribute('data-src');
        applyFilters();
      });
    });

    // Extension Filter Buttons
    document.querySelectorAll('.ext-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        document.querySelectorAll('.ext-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        currentExtFilter = this.getAttribute('data-ext');
        applyFilters();
      });
    });

    const inspectorContent = document.getElementById('inspectorContent');

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function showNodeDetails(node) {
      const d = node.data();
      const incomingEdges = node.incomers('edge');
      const outgoingEdges = node.outgoers('edge');

      const incomingHtml = incomingEdges.map(edge => {
        const src = escapeHtml(edge.data('source'));
        const reason = escapeHtml(edge.data('reason') || 'Conflict');
        return `
          <div class="attack-item">
            <div class="attack-item-header">
              <span>⚡ ${src} attacks ${escapeHtml(d.id)}</span>
            </div>
            <div class="attack-reason">${reason}</div>
          </div>
        `;
      }).join('');

      const outgoingHtml = outgoingEdges.map(edge => {
        const tgt = escapeHtml(edge.data('target'));
        const reason = escapeHtml(edge.data('reason') || 'Conflict');
        return `
          <div class="attack-item">
            <div class="attack-item-header">
              <span>⚔️ ${escapeHtml(d.id)} attacks ${tgt}</span>
            </div>
            <div class="attack-reason">${reason}</div>
          </div>
        `;
      }).join('');

      const extPills = (d.extensions && d.extensions.length > 0)
        ? d.extensions.map(e => `Extension ${e}`).join(', ')
        : 'None (0.00)';

      const sourceDisplay = (d.source_url && d.source_url !== 'KEINE_QUELLE')
        ? `<a href="${escapeHtml(d.source_url)}" target="_blank" rel="noopener noreferrer" class="source-link">🔗 ${escapeHtml(d.source_url)}</a>`
        : `<span style="color:var(--text-muted);font-size:11px;">No external source</span>`;

      inspectorContent.innerHTML = `
        <div class="inspector-card">
          <div class="node-header">
            <span class="node-id">${escapeHtml(d.id)}</span>
            <div class="badge-group">
              <span class="src-badge">${escapeHtml(d.source_category || 'general')}</span>
              <span class="cls-badge cls-${escapeHtml(d.classification)}">${escapeHtml(d.classification)}</span>
            </div>
          </div>

          <div class="claim-box">
            <strong>Claim / Argumentation:</strong><br>${escapeHtml(d.claim)}
          </div>

          <div class="property-row">
            <span class="property-label">Dung Acceptance Score:</span>
            <span class="property-value">${(d.score || 0).toFixed(2)}</span>
          </div>
          <div class="property-row">
            <span class="property-label">Source Category:</span>
            <span class="property-value" style="text-transform:capitalize;color:var(--accent-blue);">${escapeHtml(d.source_category || 'general')}</span>
          </div>
          <div class="property-row">
            <span class="property-label">In-Degree (Attacked by):</span>
            <span class="property-value">${d.in_degree}</span>
          </div>
          <div class="property-row">
            <span class="property-label">Out-Degree (Attacks):</span>
            <span class="property-value">${d.out_degree}</span>
          </div>
          <div class="property-row">
            <span class="property-label">Accepted in Perspectives:</span>
            <span class="property-value">${extPills}</span>
          </div>

          <div style="margin-top:6px;">
            <div class="property-label" style="font-size:11px;margin-bottom:2px;">Source Reference:</div>
            ${sourceDisplay}
          </div>
        </div>

        ${incomingEdges.length > 0 ? `
          <div class="section-box" style="padding:10px;">
            <div class="section-title">Incoming Attacks (${incomingEdges.length})</div>
            <div class="attack-list">${incomingHtml}</div>
          </div>
        ` : '<div class="property-row" style="color:var(--accent-core);padding:6px;">🛡️ Not attacked by any argument (Unchallenged)</div>'}

        ${outgoingEdges.length > 0 ? `
          <div class="section-box" style="padding:10px;">
            <div class="section-title">Outgoing Attacks (${outgoingEdges.length})</div>
            <div class="attack-list">${outgoingHtml}</div>
          </div>
        ` : ''}
      `;
    }

    function showEdgeDetails(edge) {
      const d = edge.data();
      const srcNode = cy.getElementById(d.source);
      const tgtNode = cy.getElementById(d.target);

      inspectorContent.innerHTML = `
        <div class="inspector-card">
          <div class="node-header">
            <span class="node-id" style="font-size:16px;">Attack Relation</span>
            <span class="cls-badge ${d.is_mutual ? 'cls-contested' : 'cls-rejected'}">
              ${d.is_mutual ? 'Mutual Conflict (Dilemma)' : 'Direct Attack'}
            </span>
          </div>

          <div class="property-row">
            <span class="property-label">Attacker:</span>
            <span class="property-value" style="color:#ef4444;">${escapeHtml(d.source)}</span>
          </div>
          <div class="claim-box" style="font-size:12px;margin-bottom:6px;">
            ${srcNode ? escapeHtml(srcNode.data('claim')) : ''}
          </div>

          <div class="property-row">
            <span class="property-label">Target:</span>
            <span class="property-value" style="color:#38bdf8;">${escapeHtml(d.target)}</span>
          </div>
          <div class="claim-box" style="font-size:12px;margin-bottom:6px;">
            ${tgtNode ? escapeHtml(tgtNode.data('claim')) : ''}
          </div>

          <div class="section-title" style="margin-top:8px;">Attack Justification</div>
          <div class="attack-item">
            <div class="attack-reason" style="font-size:12px;color:var(--text-main);">
              ${escapeHtml(d.reason || 'Direct conflict identified by reasoning engine.')}
            </div>
          </div>
        </div>
      `;
    }

    cy.on('tap', 'node', function(evt) {
      const node = evt.target;
      showNodeDetails(node);

      cy.elements().removeClass('highlighted dimmed');
      const neighborhood = node.neighborhood().add(node);
      cy.elements().difference(neighborhood).addClass('dimmed');
      neighborhood.addClass('highlighted');
    });

    cy.on('tap', 'edge', function(evt) {
      const edge = evt.target;
      showEdgeDetails(edge);

      cy.elements().removeClass('highlighted dimmed');
      const neighborhood = edge.connectedNodes().add(edge);
      cy.elements().difference(neighborhood).addClass('dimmed');
      neighborhood.addClass('highlighted');
    });

    cy.on('tap', function(evt) {
      if (evt.target === cy) {
        applyFilters();
        inspectorContent.innerHTML = `
          <div class="empty-state">
            👉 <strong>Klicken Sie auf ein Argument oder einen Pfeil</strong>, um vollständige Claims, Begründungen, Medienkategorien und Extension-Zugehörigkeiten einzusehen.
          </div>
        `;
      }
    });

    document.getElementById('layoutSelect').addEventListener('change', function(e) {
      applyLayout(e.target.value);
    });

    document.getElementById('btnFit').addEventListener('click', () => cy.fit(undefined, 40));
    document.getElementById('btnCenter').addEventListener('click', () => cy.fit(undefined, 40));
    document.getElementById('btnReset').addEventListener('click', () => {
      document.getElementById('searchInput').value = '';
      currentExtFilter = 'all';
      currentSrcFilter = 'all';
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      const allExt = document.querySelector('.ext-btn[data-ext="all"]');
      if (allExt) allExt.classList.add('active');
      const allSrc = document.querySelector('.src-btn[data-src="all"]');
      if (allSrc) allSrc.classList.add('active');
      applyFilters();
      applyLayout(document.getElementById('layoutSelect').value);
    });

    document.getElementById('searchInput').addEventListener('input', function(e) {
      const q = e.target.value.trim().toLowerCase();
      if (!q) {
        applyFilters();
        return;
      }

      cy.nodes().forEach(node => {
        const id = (node.data('id') || '').toLowerCase();
        const claim = (node.data('claim') || '').toLowerCase();
        const url = (node.data('source_url') || '').toLowerCase();
        if (id.includes(q) || claim.includes(q) || url.includes(q)) {
          node.removeClass('dimmed').addClass('highlighted');
        } else {
          node.addClass('dimmed').removeClass('highlighted');
        }
      });
      cy.edges().addClass('dimmed');
    });

    document.getElementById('btnExportPng').addEventListener('click', function() {
      const pngData = cy.png({ full: true, scale: 2.5, bg: '#090d16' });
      const a = document.createElement('a');
      a.href = pngData;
      a.download = `af_cytoscape_${Date.now()}.png`;
      a.click();
    });

    document.getElementById('btnExportJson').addEventListener('click', function() {
      const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `af_cytoscape_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  </script>
</body>
</html>
""")


def generate_cytoscape_html(
    af: ArgumentationFramework,
    extensions: list[set[str]] | None = None,
    scores: dict[str, float] | None = None,
    classification: dict[str, str] | None = None,
    dilemma_axes: list[tuple[str, str, str, str]] | None = None,
    degrees: dict[str, dict[str, int]] | None = None,
    synthesis: FullAnalysisResult | None = None,
    solver_name: str = "naive",
    semantics_name: str = "preferred",
    model_name: str | None = None,
    source_name: str | None = None,
) -> str:
    """Generate a standalone interactive HTML page with Cytoscape.js graph visualization."""
    data = build_cytoscape_data(
        af=af,
        extensions=extensions,
        scores=scores,
        classification=classification,
        dilemma_axes=dilemma_axes,
        degrees=degrees,
        synthesis=synthesis,
        topic=af.topic,
    )

    elements_json = json.dumps(data["elements"], ensure_ascii=False)
    data_json = json.dumps(data, ensure_ascii=False)

    return HTML_TEMPLATE.render(
        topic=af.topic,
        solver_name=solver_name,
        semantics_name=semantics_name,
        argument_count=len(af.arguments),
        attack_count=len(af.attacks),
        extension_count=len(extensions or []),
        dilemma_count=len(dilemma_axes or []),
        extensions=[sorted(ext) for ext in (extensions or [])],
        synthesis=synthesis,
        data_json=data_json,
        elements_json=elements_json,
    )
