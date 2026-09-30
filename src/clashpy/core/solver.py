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
    ) -> List[Set[str]]:
        ...


class UnsupportedSemanticsError(NotImplementedError):
    """Raised when a solver cannot evaluate the requested semantics."""


class NaiveBacktrackingSolver:
    """
    Exact backtracking enumeration for smaller argumentation frameworks.
    (Preferred semantics = inclusion-maximal admissible sets).
    """

    name = "naive"

    def extensions(
        self,
        af: ArgumentationFramework,
        semantics: Semantics = Semantics.PREFERRED,
    ) -> List[Set[str]]:
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
            return not any(
                x in current and y in current for x, y in valid_attacks
            )

        def defended(current: Set[str], member: str) -> bool:
            for attacker in attackers_of[member]:
                if not any(
                    (defender, attacker) in valid_attacks
                    for defender in current
                ):
                    return False
            return True

        def admissible(current: Set[str]) -> bool:
            if not conflict_free(current):
                return False
            return all(defended(current, member) for member in current)

        admissible_sets: List[Set[str]] = []

        def backtrack(index: int, current: Set[str]) -> None:
            if index == len(all_ids):
                if admissible(current):
                    admissible_sets.append(set(current))
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

        admissible_sets.sort(key=lambda x: (-len(x), tuple(sorted(x))))

        preferred: List[Set[str]] = []
        seen = set()

        for candidate in admissible_sets:
            key = tuple(sorted(candidate))

            if not key or key in seen:
                continue

            if any(candidate < other for other in admissible_sets):
                continue

            seen.add(key)
            preferred.append(candidate)

        return preferred
