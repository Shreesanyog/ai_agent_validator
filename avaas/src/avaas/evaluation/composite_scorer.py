"""Combines the three evaluation tiers (rule-based, LLM safety/hallucination,
LLM business/MVP) into one composite score and a pass/fail decision.

If the business tier didn't apply to a given test case (no explicit/derived
acceptance criteria were relevant — see `business_judge.py`), its weight is
redistributed proportionally across the remaining tiers rather than
silently counting as a zero or being dropped, so a test case is never
unfairly penalized just for not having a business-specific rubric.
"""
from __future__ import annotations

from ..config import get_settings
from ..models.schemas import RuleCheck
from .rule_based_judge import has_critical_failure


def composite_score(rule_score: float, safety_score: float | None, business_score: float | None) -> float:
    settings = get_settings()
    weights = {"rule": settings.composite_rule_weight, "safety": settings.composite_safety_weight}
    scores = {"rule": rule_score}

    if safety_score is not None:
        scores["safety"] = safety_score
    if business_score is not None:
        weights["business"] = settings.composite_business_weight
        scores["business"] = business_score

    total_weight = sum(weights[k] for k in scores)
    if total_weight <= 0:
        return round(rule_score, 2)

    weighted = sum(scores[k] * weights[k] for k in scores) / total_weight
    return round(weighted, 2)


def decide_pass(composite: float, rule_checks: list[RuleCheck]) -> bool:
    settings = get_settings()
    if has_critical_failure(rule_checks):
        return False
    return composite >= settings.pass_score_threshold
