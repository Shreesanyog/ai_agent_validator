"""End-to-end orchestration of the AVaaS pipeline described in the
architecture diagram:

  Agent Onboarding
    -> Requirement & Use Case Analysis   (requirements_analysis/extractor.py)
    -> Test Generation                    (test_generation/generator.py)
    -> Async Execution + Trace Collection (execution/async_runner.py)
    -> Multi-Tier Evaluation              (evaluation/*.py)
       - rule_based_judge   (deterministic)
       - llm_judge          (safety / hallucination)
       - business_judge     (business logic / MVP alignment)
       -> composite_scorer
    -> Requirement Coverage               (reporting/report_generator.py)
    -> Baseline vs Candidate Regression   (regression/baseline_comparator.py)
    -> Release Gate PASS/FAIL
    -> Report / Dashboard

This module is the single place that wires the individual phase modules
together, so the HTTP API and any future batch/CI entry point call
`run_validation()` and get identical behaviour.
"""
from __future__ import annotations

import logging

from .evaluation.business_judge import evaluate_business
from .evaluation.composite_scorer import composite_score, decide_pass
from .evaluation.llm_judge import evaluate_safety
from .evaluation.rule_based_judge import evaluate_rules, rule_score
from .execution.async_runner import run_test_cases
from .llm.client import LLMClient
from .models.schemas import AgentSpec, AnalyzeRequirementsRequest, EvalResult, RunReport
from .regression.baseline_comparator import compare_runs
from .reporting.report_generator import build_report, compute_requirement_coverage
from .requirements_analysis.extractor import analyze_requirements
from .test_generation.generator import generate_test_cases

logger = logging.getLogger(__name__)


async def run_validation(
    agent: AgentSpec,
    *,
    use_case_definition: str = "",
    business_requirements: list[str] | None = None,
    pdf_text: str = "",
    is_baseline: bool = False,
    max_test_cases: int | None = None,
    baseline_report: RunReport | None = None,
) -> RunReport:
    llm_client = LLMClient()

    # Requirement & Use Case Analysis --------------------------------------
    ra_request = AnalyzeRequirementsRequest(
        use_case_definition=use_case_definition,
        business_requirements=business_requirements or [],
        pdf_text=pdf_text,
        agent_description=agent.description,
        system_prompt=agent.system_prompt,
        tools=agent.tools,
    )
    analysis = analyze_requirements(ra_request, agent=agent)
    logger.info(
        "Requirement analysis: %d requirements, %d use cases, %d scenarios, %d gaps",
        len(analysis.requirements), len(analysis.use_cases), len(analysis.test_scenarios),
        len(analysis.requirement_gaps),
    )

    # Test Generation -------------------------------------------------------
    test_cases = await generate_test_cases(
        agent, analysis, llm_client=llm_client, max_test_cases=max_test_cases
    )
    logger.info("Phase 1 complete: %d test cases generated", len(test_cases))

    # Async Execution + Trace Collection ------------------------------------
    traces = await run_test_cases(agent, test_cases)
    traces_by_tc = {t.test_case_id: t for t in traces}
    logger.info("Phase 2 complete: %d traces collected", len(traces))

    # Multi-Tier Evaluation ---------------------------------------------------
    results: list[EvalResult] = []
    for tc in test_cases:
        trace = traces_by_tc[tc.id]

        rule_checks = evaluate_rules(agent, tc, trace)
        r_score = rule_score(rule_checks)

        safety_score, safety_rationale, deepeval_score, deepeval_metric = await evaluate_safety(
            llm_client, tc, trace
        )
        business_score, business_rationale = await evaluate_business(llm_client, tc, trace)

        composite = composite_score(r_score, safety_score, business_score)
        passed = decide_pass(composite, rule_checks)

        results.append(
            EvalResult(
                test_case_id=tc.id,
                test_case_type=tc.type,
                rule_score=r_score,
                rule_checks=rule_checks,
                safety_score=safety_score,
                safety_rationale=safety_rationale,
                business_score=business_score,
                business_rationale=business_rationale,
                deepeval_score=deepeval_score,
                deepeval_metric=deepeval_metric,
                composite_score=composite,
                passed=passed,
                requirement_ids=tc.requirement_ids,
                violated_requirement_ids=tc.requirement_ids if not passed else [],
                trace=trace,
            )
        )
    logger.info("Phase 3 complete: %d results evaluated", len(results))

    # Requirement Coverage + Report -------------------------------------------
    coverage = compute_requirement_coverage(analysis, results)
    report = build_report(
        tenant_id=agent.tenant_id,
        agent_id=agent.id,
        agent_name=agent.name,
        requirement_analysis=analysis,
        results=results,
        is_baseline=is_baseline,
        requirement_coverage=coverage,
    )

    # Baseline vs Candidate Regression + Release Gate --------------------------
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
