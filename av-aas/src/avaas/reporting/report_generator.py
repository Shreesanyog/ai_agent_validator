"""Assembles the final RunReport and renders a lightweight standalone HTML
view of it (Phase 4 output / "Web Dashboard/Reports" in the architecture).
"""
from __future__ import annotations

import html

from ..models.schemas import EvalResult, ReleaseGateStatus, RequirementItem, RunReport


def build_report(
    *,
    agent_id: str,
    agent_name: str,
    requirements: list[RequirementItem],
    results: list[EvalResult],
    is_baseline: bool,
) -> RunReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = round(passed / total, 4) if total else 0.0
    avg_score = round(sum(r.composite_score for r in results) / total, 2) if total else 0.0

    release_gate = ReleaseGateStatus.PASS if pass_rate >= 0.8 else ReleaseGateStatus.FAIL

    return RunReport(
        agent_id=agent_id,
        agent_name=agent_name,
        is_baseline=is_baseline,
        requirements=requirements,
        test_cases_count=total,
        results=results,
        pass_rate=pass_rate,
        avg_score=avg_score,
        release_gate=release_gate,
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
            f"<td>{r.llm_score if r.llm_score is not None else '-'}</td>"
            f"<td>{r.composite_score}</td>"
            f"<td style='color:{color};font-weight:bold'>{status}</td>"
            f"<td>{html.escape(r.trace.response_text[:160])}</td>"
            "</tr>"
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
<p><b>Agent:</b> {html.escape(report.agent_name)} ({html.escape(report.agent_id)})<br/>
<b>Run:</b> {html.escape(report.run_id)} {'(baseline)' if report.is_baseline else ''}<br/>
<b>Test cases:</b> {report.test_cases_count} | <b>Pass rate:</b> {report.pass_rate:.2%} | <b>Avg score:</b> {report.avg_score}</p>
<p><span class="badge" style="background:{gate_color}">RELEASE GATE: {report.release_gate.value}</span></p>
{regression_block}
<h2>Requirements ({len(report.requirements)})</h2>
<ul>
{''.join(f"<li>[{r.category.value}/{r.source.value}] {html.escape(r.text)}</li>" for r in report.requirements)}
</ul>
<h2>Test Results</h2>
<table>
<tr><th>Test Case</th><th>Type</th><th>Rule Score</th><th>LLM Score</th><th>Composite</th><th>Status</th><th>Response (truncated)</th></tr>
{''.join(rows)}
</table>
</body></html>"""
