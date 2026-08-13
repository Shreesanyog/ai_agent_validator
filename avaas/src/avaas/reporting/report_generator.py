"""Assembles the final RunReport and renders a lightweight standalone HTML
view of it (Phase 4 output / "Web Dashboard/Reports" in the architecture).

Also computes per-requirement coverage (PASS/FAIL/UNTESTED) by rolling up
every EvalResult onto the requirement ids its test case targeted — this is
the "Requirement Coverage" box in the architecture diagram, sitting between
Evaluation and Baseline-vs-Candidate comparison.
"""
from __future__ import annotations

import html

from ..models.schemas import EvalResult, ReleaseGateStatus, RequirementAnalysis, RunReport


def compute_requirement_coverage(analysis: RequirementAnalysis, results: list[EvalResult]) -> dict[str, str]:
    coverage: dict[str, str] = {r.requirement_id: "UNTESTED" for r in analysis.requirements}
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        for rid in result.requirement_ids:
            # A single FAIL for a requirement always wins over a PASS from
            # another test case that happened to also target it.
            if coverage.get(rid) == "FAIL":
                continue
            coverage[rid] = status
    return coverage


def build_report(
    *,
    tenant_id: str,
    agent_id: str,
    agent_name: str,
    requirement_analysis: RequirementAnalysis,
    results: list[EvalResult],
    is_baseline: bool,
    requirement_coverage: dict[str, str],
) -> RunReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = round(passed / total, 4) if total else 0.0
    avg_score = round(sum(r.composite_score for r in results) / total, 2) if total else 0.0

    release_gate = ReleaseGateStatus.PASS if pass_rate >= 0.8 else ReleaseGateStatus.FAIL

    return RunReport(
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_name=agent_name,
        is_baseline=is_baseline,
        requirement_analysis=requirement_analysis,
        test_cases_count=total,
        results=results,
        pass_rate=pass_rate,
        avg_score=avg_score,
        release_gate=release_gate,
        requirement_coverage=requirement_coverage,
    )


def to_html(report: RunReport) -> str:
    rows = []
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        color = "#1a7f37" if r.passed else "#c62828"
        rows.append(
            "<tr>"
            f"<td>{html.escape(r.test_case_id)}</td>"
            f"<td>{html.escape(r.test_case_type.value)}</td>"
            f"<td>{r.rule_score}</td>"
            f"<td>{r.safety_score if r.safety_score is not None else '-'}</td>"
            f"<td>{r.business_score if r.business_score is not None else '-'}</td>"
            f"<td>{r.composite_score}</td>"
            f"<td style='color:{color};font-weight:bold'>{status}</td>"
            f"<td>{html.escape(r.trace.response_text[:140])}</td>"
            "</tr>"
        )

    coverage_rows = []
    req_by_id = {r.requirement_id: r for r in report.requirement_analysis.requirements}
    for rid, status in report.requirement_coverage.items():
        req = req_by_id.get(rid)
        color = {"PASS": "#1a7f37", "FAIL": "#c62828", "UNTESTED": "#9c7c00"}.get(status, "#333")
        text = req.requirement if req else rid
        coverage_rows.append(
            f"<tr><td>{html.escape(rid)}</td><td>{html.escape(text)}</td>"
            f"<td style='color:{color};font-weight:bold'>{status}</td></tr>"
        )

    gate_color = "#1a7f37" if report.release_gate.value == "PASS" else "#c62828"
    regression_block = ""
    if report.regression:
        reg = report.regression
        regression_block = f"""
        <h2>Regression vs baseline {html.escape(reg.baseline_run_id)}</h2>
        <p>Pass rate: {reg.baseline_pass_rate:.2%} &rarr; {reg.candidate_pass_rate:.2%}
        ({reg.pass_rate_delta:+.2%}) | Avg score: {reg.baseline_avg_score} &rarr; {reg.candidate_avg_score}
        ({reg.avg_score_delta:+.2f})</p>
        <p style="font-weight:bold;color:{'#c62828' if reg.regressed else '#1a7f37'}">
        {'REGRESSION DETECTED' if reg.regressed else 'No regression detected'}</p>
        """

    gap_items = "".join(
        f"<li>[{html.escape(g.impact)}] {html.escape(g.description)} "
        f"<i>({html.escape(g.question_for_qa)})</i></li>"
        for g in report.requirement_analysis.requirement_gaps
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AVaaS Report - {html.escape(report.agent_name)}</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: #1a1a2e; background:#faf8f2;}}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; background:#fff;}}
th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 0.9rem; text-align:left;}}
th {{ background: #1a1a4e; color: white; }}
.badge {{ display:inline-block; padding: 4px 14px; border-radius: 999px; color:white; font-weight:bold;}}
</style></head><body>
<h1>AVaaS Validation Report</h1>
<p><b>Tenant:</b> {html.escape(report.tenant_id)}<br/>
<b>Agent:</b> {html.escape(report.agent_name)} ({html.escape(report.agent_id)})<br/>
<b>Run:</b> {html.escape(report.run_id)} {'(baseline)' if report.is_baseline else ''}<br/>
<b>Test cases:</b> {report.test_cases_count} | <b>Pass rate:</b> {report.pass_rate:.2%} | <b>Avg score:</b> {report.avg_score}</p>
<p><span class="badge" style="background:{gate_color}">RELEASE GATE: {report.release_gate.value}</span></p>
{regression_block}
<h2>Requirement Coverage</h2>
<table>
<tr><th>Requirement</th><th>Text</th><th>Status</th></tr>
{''.join(coverage_rows)}
</table>
<h2>Requirement Gaps ({len(report.requirement_analysis.requirement_gaps)})</h2>
<ul>{gap_items or '<li>None identified.</li>'}</ul>
<h2>Test Results (Rule / Safety / Business / Composite)</h2>
<table>
<tr><th>Test Case</th><th>Type</th><th>Rule</th><th>Safety</th><th>Business</th><th>Composite</th><th>Status</th><th>Response (truncated)</th></tr>
{''.join(rows)}
</table>
</body></html>"""
