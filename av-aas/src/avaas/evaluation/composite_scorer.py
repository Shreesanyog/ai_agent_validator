"""Combines the rule-based and LLM-judge scores into one composite score and
a pass/fail decision (Phase 3 output feeding into Phase 4 regression).
"""
from __future__ import annotations

from ..config import get_settings
from ..models.schemas import RuleCheck
from .rule_based_judge import has_critical_failure


def composite_score(rule_score: float, llm_score: float | None) -> float:
    settings = get_settings()
    if llm_score is None:
        return round(rule_score, 2)
    total_weight = settings.composite_rule_weight + settings.composite_llm_weight
    weighted = (rule_score * settings.composite_rule_weight + llm_score * settings.composite_llm_weight) / total_weight
    return round(weighted, 2)


def decide_pass(composite: float, rule_checks: list[RuleCheck]) -> bool:
    settings = get_settings()
    if has_critical_failure(rule_checks):
        return False
    return composite >= settings.pass_score_threshold
