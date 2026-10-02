"""
Solver Protocol: the core abstraction for Dung's abstract argumentation semantics.

Every solver accepts an ArgumentationFramework and a Semantics enum,
returning a list of extensions (sets of argument IDs). Whether this is
computed via backtracking, SAT, or ASP is irrelevant to pipeline.py.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Protocol, Set

from clashpy.core.models import ArgumentationFramework


class Semantics(str, Enum):
    """Standard ICCMA competition abbreviations for argumentation semantics."""

    CONFLICT_FREE = "CF"
    ADMISSIBLE = "AD"
    COMPLETE = "CO"
    PREFERRED = "PR"
    GROUNDED = "GR"
    STABLE = "ST"
    IDEAL = "ID"
    SEMI_STABLE = "SST"


class Solver(Protocol):
    """
    Minimal solver interface. `name` is part of the cache namespace
    to avoid cross-contamination between different solvers.
    """

    name: str

    def extensions(
        self,
        af: ArgumentationFramework,
        semantics: Semantics = Semantics.PREFERRED,
    ) -> List[Set[str]]: ...


class UnsupportedSemanticsError(NotImplementedError):
    """Raised when a solver cannot evaluate the requested semantics."""


class SolverCapacityError(RuntimeError):
    """Raised when a solver would exceed its configured safe input size."""


class NaiveBacktrackingSolver:
    """
    Exact backtracking enumeration for smaller argumentation frameworks.
    (Preferred semantics = inclusion-maximal admissible sets).
    """

    name = "naive"

    def __init__(self, max_arguments: int = 35) -> None:
        if max_arguments < 1:
            raise ValueError("max_arguments must be at least 1")
        self.max_arguments = max_arguments

    def extensions(
        self,
        af: ArgumentationFramework,
        semantics: Semantics = Semantics.PREFERRED,
    ) -> List[Set[str]]:
        argument_count = len(af.arguments)
        if argument_count > self.max_arguments:
            raise SolverCapacityError(
                f"Naive solver limit exceeded: {argument_count} arguments "
                f"(configured maximum: {self.max_arguments}). Use --solver pygarg "
                "or increase --naive-max-arguments deliberately."
            )

        if semantics != Semantics.PREFERRED:
            raise UnsupportedSemanticsError(
                f"{self.name} currently only supports PREFERRED semantics, "
                f"not {semantics}. Use PygargSolver for additional semantics."
            )

        return self._compute_preferred_extensions(af)

    @staticmethod
    def _compute_preferred_extensions(
        af: ArgumentationFramework,
    ) -> List[Set[str]]:
        all_ids = sorted({a.id for a in af.arguments})

        valid_attacks = {
            (a.attacker_id, a.target_id)
            for a in af.attacks
            if a.attacker_id in all_ids and a.target_id in all_ids
        }

        attackers_of = {uid: set() for uid in all_ids}

        for attacker, target in valid_attacks:
            attackers_of[target].add(attacker)

        def conflict_free(current: Set[str]) -> bool:
            return not any(x in current and y in current for x, y in valid_attacks)

        def defended(current: Set[str], member: str) -> bool:
            for attacker in attackers_of[member]:
                if not any(
                    (defender, attacker) in valid_attacks for defender in current
                ):
                    return False
            return True

        def admissible(current: Set[str]) -> bool:
            if not conflict_free(current):
                return False
            return all(defended(current, member) for member in current)

        preferred: List[Set[str]] = []

        def retain_if_maximal(candidate: Set[str]) -> None:
            if any(candidate <= existing for existing in preferred):
                return

            preferred[:] = [
                existing for existing in preferred if not existing < candidate
            ]
            preferred.append(set(candidate))

        def backtrack(index: int, current: Set[str]) -> None:
            if index == len(all_ids):
                if admissible(current):
                    retain_if_maximal(current)
                return

            candidate = all_ids[index]

            if all(
                (candidate, other) not in valid_attacks
                and (other, candidate) not in valid_attacks
                for other in current
            ):
                current.add(candidate)
                backtrack(index + 1, current)
                current.remove(candidate)

            backtrack(index + 1, current)

        backtrack(0, set())

        preferred.sort(
            key=lambda extension: (-len(extension), tuple(sorted(extension)))
        )
        return preferred
