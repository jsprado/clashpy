"""Unit tests for Pygarg SAT-based solver integration."""

import pytest

from clashpy.adapters.solvers.pygarg_solver import PygargSolver, _parse_extensions, _to_apx
from clashpy.core.models import Argument, ArgumentationFramework, Attack
from clashpy.core.solver import Semantics


def _sample_af() -> ArgumentationFramework:
    return ArgumentationFramework(
        topic="Pygarg Test",
        arguments=[
            Argument(id="A1", claim="Claim 1", source_url="k"),
            Argument(id="A2", claim="Claim 2", source_url="k"),
            Argument(id="A3", claim="Claim 3", source_url="k"),
        ],
        attacks=[
            Attack(attacker_id="A1", target_id="A2", reason="Conflict"),
            Attack(attacker_id="A2", target_id="A1", reason="Conflict"),
            Attack(attacker_id="A3", target_id="A2", reason="Conflict"),
        ],
    )


def test_to_apx_format():
    af = _sample_af()
    apx_text, mapping = _to_apx(af)

    assert "arg(A1)." in apx_text
    assert "arg(A2)." in apx_text
    assert "arg(A3)." in apx_text
    assert "att(A1,A2)." in apx_text


def test_parse_extensions_iccma_format():
    raw_iccma = "w A1 A3 \nw A2 \n"
    mapping = {"A1": "A1", "A2": "A2", "A3": "A3"}
    exts = _parse_extensions(raw_iccma, mapping)

    assert len(exts) == 2
    assert {"A1", "A3"} in exts
    assert {"A2"} in exts


def test_pygarg_solver_extensions():
    af = _sample_af()
    solver = PygargSolver()
    exts = solver.extensions(af, semantics=Semantics.PREFERRED)

    assert len(exts) == 1
    # A3 is unattacked and attacks A2, defending A1. So {A1, A3} is the unique preferred extension.
    assert exts == [{"A1", "A3"}]
