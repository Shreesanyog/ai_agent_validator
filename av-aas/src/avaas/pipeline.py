"""End-to-end orchestration of the 4-phase AVaaS pipeline described in the
architecture diagram:

  Phase 1: Requirement Analysis + Test Generation
  Phase 2: Async Execution (+ trace collection)
  Phase 3: Evaluation (Dual-Tier: rule-based + LLM-as-a-judge -> composite)
  Phase 4: Regression & Reporting

This module is the single place that wires the individual phase modules
together, so API routes and CLI scripts both call `run_validation()` and get
identical behaviour.
"""
from __future__ import annotations

import logging

from .evaluation.composite_scorer import composite_score, decide_pass
from .evaluation.llm_judge import evaluate_llm
from .evaluation.rule_based_judge import evaluate_rules, rule_score
from .execution.async_runner import run_test_cases
from .llm.client import LLMClient
from .models.schemas import AgentSpec, EvalResult, RunReport
from .regression.baseline_comparator import compare_runs
from .reporting.report_generator import build_report
from .requirements_analysis.extractor import extract_requirements
from .test_generation.generator import generate_test_cases

logger = logging.getLogger(__name__)


async def run_validation(
    agent: AgentSpec,
    *,
    explicit_requirements: list[str] | None = None,
    is_baseline: bool = False,
    max_test_cases: int | None = None,
    baseline_report: RunReport | None = None,
) -> RunReport:
    llm_client = LLMClient()

    # Phase 1 -----------------------------------------------------------
    requirements = extract_requirements(agent, explicit_requirements)
    test_cases = await generate_test_cases(
        agent, requirements, llm_client=llm_client, max_test_cases=max_test_cases
    )
    logger.info("Phase 1 complete: %d requirements, %d test cases", len(requirements), len(test_cases))

    # Phase 2 -----------------------------------------------------------
    traces = await run_test_cases(agent, test_cases)
    traces_by_tc = {t.test_case_id: t for t in traces}
    logger.info("Phase 2 complete: %d traces collected", len(traces))

    # Phase 3 -----------------------------------------------------------
    results: list[EvalResult] = []
    for tc in test_cases:
        trace = traces_by_tc[tc.id]
        checks = evaluate_rules(agent, tc, trace)
        r_score = rule_score(checks)
        llm_score, llm_rationale = await evaluate_llm(llm_client, tc, trace, requirements)
        composite = composite_score(r_score, llm_score)
        passed = decide_pass(composite, checks)

        violated = [rid for rid in tc.requirement_ids] if not passed else []

        results.append(
            EvalResult(
                test_case_id=tc.id,
                test_case_type=tc.type,
                rule_score=r_score,
                rule_checks=checks,
                llm_score=llm_score,
                llm_rationale=llm_rationale,
                composite_score=composite,
                passed=passed,
                violated_requirement_ids=violated,
                trace=trace,
            )
        )
    logger.info("Phase 3 complete: %d results evaluated", len(results))

    # Phase 4 -------------------------------------------------------------
    report = build_report(
        agent_id=agent.id,
        agent_name=agent.name,
        requirements=requirements,
        results=results,
        is_baseline=is_baseline,
    )

    if baseline_report is not None and not is_baseline:
        report.regression = compare_runs(baseline_report, report)
        if report.regression.regressed:
            report.release_gate = report.release_gate.__class__.FAIL

    logger.info(
        "Phase 4 complete: pass_rate=%.2f%% avg_score=%.2f gate=%s",
        report.pass_rate * 100,
        report.avg_score,
        report.release_gate.value,
    )
    return report
