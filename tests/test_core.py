"""Unit tests for the clashpy core models and solver."""

import pytest
from clashpy.core.models import Argument, Attack, ArgumentationFramework
from clashpy.core.solver import NaiveBacktrackingSolver, Semantics
from clashpy.core.metrics import compute_argument_scores, classify_arguments, detect_dilemma_axes


def test_naive_solver_preferred_extensions():
    # Setup simple cycle: A attacks B, B attacks A
    af = ArgumentationFramework(
        topic="Test Framework",
        arguments=[
            Argument(id="A", claim="Claim A", source_url="KEINE_QUELLE"),
            Argument(id="B", claim="Claim B", source_url="KEINE_QUELLE"),
            Argument(id="C", claim="Claim C", source_url="KEINE_QUELLE"),
        ],
        attacks=[
            Attack(attacker_id="A", target_id="B", reason="Conflict"),
            Attack(attacker_id="B", target_id="A", reason="Conflict"),
        ],
    )

    solver = NaiveBacktrackingSolver()
    extensions = solver.extensions(af, semantics=Semantics.PREFERRED)

    # Preferred extensions should be {A, C} and {B, C}
    sets = [set(ext) for ext in extensions]
    assert {"A", "C"} in sets
    assert {"B", "C"} in sets
    assert len(sets) == 2


def test_metrics_computation():
    all_ids = ["A", "B", "C"]
    extensions = [{"A", "C"}, {"B", "C"}]

    scores = compute_argument_scores(all_ids, extensions)
    assert scores["C"] == 1.0
    assert scores["A"] == 0.5
    assert scores["B"] == 0.5

    classification = classify_arguments(scores)
    assert classification["C"] == "core"
    assert classification["A"] == "contested"
    assert classification["B"] == "contested"


def test_detect_dilemma_axes():
    attacks = [
        Attack(attacker_id="A", target_id="B", reason="Reason AB"),
        Attack(attacker_id="B", target_id="A", reason="Reason BA"),
        Attack(attacker_id="C", target_id="A", reason="One way"),
    ]

    axes = detect_dilemma_axes(attacks)
    assert len(axes) == 1
    pair = {axes[0][0], axes[0][1]}
    assert pair == {"A", "B"}
