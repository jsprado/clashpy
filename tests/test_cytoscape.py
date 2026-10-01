"""Unit tests for Cytoscape.js export and HTML dashboard generation."""

import json

from clashpy.core.models import (
    Argument,
    ArgumentationFramework,
    Attack,
    FullAnalysisResult,
    GroupThesis,
)
from clashpy.cytoscape import (
    build_cytoscape_data,
    build_cytoscape_elements,
    export_cytoscape_json,
    generate_cytoscape_html,
)


def _sample_af() -> ArgumentationFramework:
    return ArgumentationFramework(
        topic="Remote Work vs Office",
        arguments=[
            Argument(id="A1", claim="Remote work increases flexibility.", source_url="https://example.com/1"),
            Argument(id="A2", claim="In-person collaboration fosters spontaneous innovation.", source_url="https://example.com/2"),
            Argument(id="A3", claim="Modern async tooling replaces spontaneous chat.", source_url="KEINE_QUELLE"),
        ],
        attacks=[
            Attack(attacker_id="A2", target_id="A1", reason="Flexibility hurts direct communication"),
            Attack(attacker_id="A3", target_id="A2", reason="Async tooling resolves communication bottleneck"),
            Attack(attacker_id="A2", target_id="A3", reason="Tools cannot fully replace physical presence"),
        ],
    )


def test_build_cytoscape_elements():
    af = _sample_af()
    extensions = [{"A1", "A3"}, {"A2"}]
    scores = {"A1": 0.5, "A2": 0.5, "A3": 0.5}
    classification = {"A1": "contested", "A2": "contested", "A3": "contested"}
    dilemma_axes = [("A2", "A3", "A2->A3", "A3->A2")]
    degrees = {
        "A1": {"in_degree": 1, "out_degree": 0},
        "A2": {"in_degree": 1, "out_degree": 2},
        "A3": {"in_degree": 1, "out_degree": 1},
    }

    elements = build_cytoscape_elements(
        af=af,
        scores=scores,
        classification=classification,
        extensions=extensions,
        dilemma_axes=dilemma_axes,
        degrees=degrees,
    )

    nodes = [e for e in elements if e["group"] == "nodes"]
    edges = [e for e in elements if e["group"] == "edges"]

    assert len(nodes) == 3
    assert len(edges) == 3

    # Check node data
    a1_node = next(n for n in nodes if n["data"]["id"] == "A1")
    assert a1_node["data"]["claim"] == "Remote work increases flexibility."
    assert "Remote work increases flexibility." in a1_node["data"]["card_label"]
    assert a1_node["data"]["compact_label"] == "[A1] 0.50"
    assert a1_node["data"]["score"] == 0.5
    assert a1_node["data"]["classification"] == "contested"
    assert a1_node["data"]["extensions"] == [1]  # In Extension 1
    assert "cls-contested" in a1_node["classes"]
    assert "ext-1" in a1_node["classes"]

    # Check edge data (mutual vs direct)
    mutual_edge = next(e for e in edges if e["data"]["id"] == "A2->A3")
    assert mutual_edge["data"]["is_mutual"] is True
    assert mutual_edge["classes"] == "mutual-attack"

    direct_edge = next(e for e in edges if e["data"]["id"] == "A2->A1")
    assert direct_edge["data"]["is_mutual"] is False
    assert direct_edge["classes"] == "direct-attack"


def test_build_cytoscape_data():
    af = _sample_af()
    data = build_cytoscape_data(
        af=af,
        extensions=[{"A1", "A3"}, {"A2"}],
    )
    assert data["format"] == "clashpy-cytoscape-v1"
    assert data["stats"]["argument_count"] == 3
    assert data["stats"]["attack_count"] == 3
    assert len(data["elements"]) == 6  # 3 nodes + 3 edges


def test_export_cytoscape_json():
    af = _sample_af()
    synthesis = FullAnalysisResult(
        theses=[
            GroupThesis(group_id=1, title="Flexibility & Tooling", thesis="Async tools enable remote work."),
        ]
    )

    json_str = export_cytoscape_json(
        af=af,
        extensions=[{"A1", "A3"}],
        synthesis=synthesis,
    )

    parsed = json.loads(json_str)
    assert parsed["format"] == "clashpy-cytoscape-v1"
    assert parsed["topic"] == "Remote Work vs Office"
    assert parsed["stats"]["argument_count"] == 3
    assert parsed["stats"]["attack_count"] == 3
    assert parsed["synthesis"]["theses"][0]["title"] == "Flexibility & Tooling"


def test_generate_cytoscape_html():
    af = _sample_af()
    synthesis = FullAnalysisResult(
        theses=[
            GroupThesis(group_id=1, title="Thesis 1", thesis="Synthesis body text."),
        ]
    )

    html_content = generate_cytoscape_html(
        af=af,
        extensions=[{"A1", "A3"}],
        synthesis=synthesis,
        solver_name="pygarg",
        semantics_name="preferred",
    )

    assert "<!DOCTYPE html>" in html_content
    assert "cytoscape.min.js" in html_content
    assert "cytoscape-dagre" in html_content
    assert "Remote Work vs Office" in html_content
    assert "Thesis 1" in html_content
    assert "Synthesis body text." in html_content
    assert "btnExportPng" in html_content
    assert "btnExportJson" in html_content
