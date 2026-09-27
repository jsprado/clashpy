"""
Metrics computed over calculated argument extensions.

Decoupled from core/solver.py: these functions represent pure mathematical
operations on List[Set[str]], independent of whether extensions originated
from the naive backtracking solver or an external SAT solver.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from argument_inferencer.core.models import Attack


def compute_argument_scores(
    all_ids: List[str],
    extensions: List[Set[str]],
) -> Dict[str, float]:
    """
    Structural acceptance score: proportion of extensions containing the argument.
    1.0 = present in all extensions, 0.0 = present in none.
    Represents structural stability, not empirical truth or moral quality.
    """
    if not extensions:
        return {uid: 0.0 for uid in all_ids}

    n = len(extensions)

    return {
        uid: sum(uid in ext for ext in extensions) / n
        for uid in all_ids
    }


def classify_arguments(scores: Dict[str, float]) -> Dict[str, str]:
    """Classifies arguments into core (consensus), contested, or excluded."""
    return {
        uid: (
            "core"
            if score >= 0.999999
            else "excluded"
            if score <= 0.000001
            else "contested"
        )
        for uid, score in scores.items()
    }


def compute_attack_degrees(
    all_ids: List[str],
    attacks: List[Attack],
) -> Dict[str, Dict[str, int]]:
    """Calculates in-degree (vulnerability) and out-degree (offensive power)."""
    degrees = {uid: {"in_degree": 0, "out_degree": 0} for uid in all_ids}

    for attack in attacks:
        if attack.target_id in degrees:
            degrees[attack.target_id]["in_degree"] += 1
        if attack.attacker_id in degrees:
            degrees[attack.attacker_id]["out_degree"] += 1

    return degrees


def detect_dilemma_axes(
    attacks: List[Attack],
) -> List[Tuple[str, str, str, str]]:
    """Identifies mutual attacks (A <-> B) representing irreconcilable dilemma axes."""
    by_pair = {(a.attacker_id, a.target_id): a.reason for a in attacks}

    result = []
    seen: Set[frozenset] = set()

    for (x, y), reason_xy in by_pair.items():
        if (y, x) not in by_pair:
            continue

        pair = frozenset((x, y))
        if pair in seen:
            continue

        seen.add(pair)
        result.append((x, y, reason_xy, by_pair[(y, x)]))

    return result
