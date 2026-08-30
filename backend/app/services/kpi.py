"""Enterprise AI-Quality-Engineering KPIs."""
from statistics import mean

def run_kpis(results: list, run, baseline_run=None) -> dict:
    n = len(results) or 1
    hallucinated = sum(1 for r in results if r.evidence.get('hallucination_detected'))
    latencies = [r.evidence.get('latency_ms', 0) for r in results if r.evidence.get('latency_ms')]
    case_types = {r.case_type for r in results}
    coverage_target = {'normal', 'edge', 'injection', 'multi_turn'}
    kpis = {
        'hallucination_detection_rate': round(hallucinated / n, 3),
        'test_coverage': round(len(case_types & coverage_target) / len(coverage_target), 3),
        'avg_latency_ms': round(mean(latencies), 1) if latencies else None,
        'cost_per_validation_run': run.summary.get('estimated_cost', 0.0),
        'release_confidence': round(max(0.0, min(100.0, (run.score or 0) * 0.6 + (run.pass_rate or 0) * 100 * 0.4 - (run.risk_score or 0) * 0.3)), 1),
    }
    if baseline_run and baseline_run.score is not None and run.score is not None:
        drift = abs(run.score - baseline_run.score)
        kpis['regression_detection_accuracy'] = round(max(0.0, 100 - drift), 1)
        kpis['score_drift_vs_baseline'] = round(run.score - baseline_run.score, 1)
    return kpis

def tenant_kpis(runs: list) -> dict:
    """Portfolio-level rollup across all runs for the AgentOps / governance dashboard."""
    completed = [r for r in runs if r.status.value == 'completed']
    
    # Base ROI Metrics (Venkata Sir's Feedback Implementation)
    qa_hours_per_run = 2.5 # Estimated manual hours saved per automated run
    qa_hourly_rate = 45.0  # Estimated USD cost per QA hour
    
    if not completed:
        return {
            'total_runs': len(runs), 'completed_runs': 0, 'release_gate_pass_rate': None,
            'avg_composite_score': None, 'avg_hallucination_rate': None, 'avg_risk_score': None,
            'total_estimated_cost': 0.0, 'avg_release_confidence': None,
            'roi_qa_hours_saved': 0, 'roi_cost_savings': 0.0, 'defect_leakage_prevented': 0
        }
        
    scores = [r.score for r in completed if r.score is not None]
    hallucinations = [r.hallucination_rate for r in completed if r.hallucination_rate is not None]
    risks = [r.risk_score for r in completed if r.risk_score is not None]
    confidences = [r.release_confidence for r in completed if r.release_confidence is not None]
    costs = [r.summary.get('estimated_cost', 0.0) for r in completed]
    gates = [r.release_gate for r in completed if r.release_gate]
    
    total_completed = len(completed)
    roi_hours = total_completed * qa_hours_per_run
    
    return {
        'total_runs': len(runs),
        'completed_runs': total_completed,
        'release_gate_pass_rate': round(gates.count('PASS') / len(gates), 3) if gates else None,
        'avg_composite_score': round(mean(scores), 1) if scores else None,
        'avg_hallucination_rate': round(mean(hallucinations), 3) if hallucinations else None,
        'avg_risk_score': round(mean(risks), 1) if risks else None,
        'avg_release_confidence': round(mean(confidences), 1) if confidences else None,
        'total_estimated_cost': round(sum(costs), 5),
        
        # MENTOR FEEDBACK: Quantified Business ROI
        'roi_qa_hours_saved': round(roi_hours, 1),
        'roi_cost_savings': round(roi_hours * qa_hourly_rate, 2),
        'defect_leakage_prevented': int(total_completed * 1.5) # Assumes 1.5 critical edge cases caught per run
    }