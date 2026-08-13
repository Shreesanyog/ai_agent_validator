"""Pydantic schemas shared across the AVaaS pipeline.

These are the contracts between phases described in the architecture:
Agent Onboarding -> Requirement Analysis -> Test Generation ->
Async Execution -> Trace Collection -> Multi-Tier Evaluation -> Regression ->
Report. All models are tenant-scoped where persisted.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------
# Multi-tenancy
# --------------------------------------------------------------------------
class Tenant(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("tenant"))
    name: str
    api_key: str = Field(default_factory=lambda: f"avaas_{uuid.uuid4().hex}")
    created_at: float = Field(default_factory=time.time)


class CreateTenantRequest(BaseModel):
    name: str


# --------------------------------------------------------------------------
# Agent onboarding
# --------------------------------------------------------------------------
class ToolSchema(BaseModel):
    """Describes a single tool the target agent may call."""

    name: str
    description: str = ""
    # JSON Schema (draft-07 style) describing the tool's arguments.
    parameters: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class AgentSpec(BaseModel):
    """Everything AVaaS needs to know to onboard and test an agent."""

    id: str = Field(default_factory=lambda: _new_id("agent"))
    tenant_id: str
    name: str
    description: str = ""
    endpoint_url: HttpUrl
    system_prompt: str = ""
    tools: List[ToolSchema] = Field(default_factory=list)
    auth_header: Optional[str] = None  # e.g. "Bearer <token>", sent as-is if set
    disallowed_tools: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --------------------------------------------------------------------------
# Requirement & Use Case Analysis Engine (per AgentValidator RA spec)
# --------------------------------------------------------------------------
class RequirementSource(str, Enum):
    EXPLICIT = "EXPLICIT"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class RequirementCategory(str, Enum):
    FUNCTIONAL = "functional"
    BEHAVIOURAL = "behavioural"
    BUSINESS_RULE = "business_rule"
    SECURITY = "security"
    SAFETY = "safety"
    PRIVACY = "privacy"
    PERFORMANCE = "performance"
    OTHER = "other"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UseCase(BaseModel):
    use_case_id: str = Field(default_factory=lambda: _new_id("UC"))
    name: str
    actor: str = "User"
    goal: str = ""
    trigger: str = ""
    preconditions: List[str] = Field(default_factory=list)
    main_flow: List[str] = Field(default_factory=list)
    alternate_flows: List[str] = Field(default_factory=list)
    exception_flows: List[str] = Field(default_factory=list)
    expected_outcome: str = ""
    relevant_tools: List[str] = Field(default_factory=list)
    related_requirements: List[str] = Field(default_factory=list)


class RequirementItem(BaseModel):
    requirement_id: str = Field(default_factory=lambda: _new_id("REQ"))
    requirement: str
    category: RequirementCategory = RequirementCategory.FUNCTIONAL
    source: RequirementSource = RequirementSource.INFERRED
    confidence: float = 0.5
    priority: Priority = Priority.MEDIUM
    related_use_cases: List[str] = Field(default_factory=list)
    expected_behaviour: str = ""
    forbidden_behaviour: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    relevant_tools: List[str] = Field(default_factory=list)
    # Legacy field kept for backward compatibility with test generation code
    # that maps a requirement to a single tool.
    related_tool: Optional[str] = None


class UserIntent(BaseModel):
    intent_id: str = Field(default_factory=lambda: _new_id("INT"))
    name: str
    description: str = ""
    example_requests: List[str] = Field(default_factory=list)
    related_use_cases: List[str] = Field(default_factory=list)
    related_requirements: List[str] = Field(default_factory=list)


class TestScenarioType(str, Enum):
    NORMAL = "normal"
    EDGE = "edge"
    BOUNDARY = "boundary"
    NEGATIVE = "negative"
    INJECTION = "injection"
    MULTI_TURN = "multi_turn"
    TOOL_USE = "tool_use"
    AUTHORIZATION = "authorization"
    FAILURE_RECOVERY = "failure_recovery"


class TestScenario(BaseModel):
    scenario_id: str = Field(default_factory=lambda: _new_id("SC"))
    type: TestScenarioType
    description: str = ""
    related_use_case: Optional[str] = None
    related_requirements: List[str] = Field(default_factory=list)
    expected_behaviour: str = ""


class RequirementGap(BaseModel):
    gap_id: str = Field(default_factory=lambda: _new_id("GAP"))
    description: str
    impact: str = ""
    question_for_qa: str = ""


class Completeness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class AnalysisSummary(BaseModel):
    requirements_completeness: Completeness = Completeness.PARTIAL
    use_case_completeness: Completeness = Completeness.PARTIAL
    explicit_requirement_count: int = 0
    derived_requirement_count: int = 0
    inferred_requirement_count: int = 0
    requirement_gap_count: int = 0
    critical_gaps: List[str] = Field(default_factory=list)


class AgentSummary(BaseModel):
    purpose: str = ""
    target_users: List[str] = Field(default_factory=list)
    scope: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)


class RequirementAnalysis(BaseModel):
    """The full structured output of the Requirement & Use Case Analysis
    Engine — mirrors the JSON contract used by AgentValidator's RA prompt so
    it is directly consumable by Test Generation and Evaluation."""

    agent_summary: AgentSummary = Field(default_factory=AgentSummary)
    use_cases: List[UseCase] = Field(default_factory=list)
    requirements: List[RequirementItem] = Field(default_factory=list)
    user_intents: List[UserIntent] = Field(default_factory=list)
    test_scenarios: List[TestScenario] = Field(default_factory=list)
    requirement_gaps: List[RequirementGap] = Field(default_factory=list)
    analysis_summary: AnalysisSummary = Field(default_factory=AnalysisSummary)


class AnalyzeRequirementsRequest(BaseModel):
    """Input contract mirroring the RA engine's documented INPUTS section."""

    use_case_definition: str = ""
    business_requirements: List[str] = Field(default_factory=list)
    pdf_text: str = ""  # pre-extracted text from BRD/SRS/policy docs, if any
    agent_description: str = ""
    system_prompt: str = ""
    tools: List[ToolSchema] = Field(default_factory=list)
    documentation: str = ""


# --------------------------------------------------------------------------
# Test generation (executable test cases, derived from TestScenarios)
# --------------------------------------------------------------------------
class TestCaseType(str, Enum):
    NORMAL = "normal"
    EDGE = "edge"
    BOUNDARY = "boundary"
    NEGATIVE = "negative"
    INJECTION = "injection"
    MULTI_TURN = "multi_turn"
    TOOL_USE = "tool_use"
    AUTHORIZATION = "authorization"
    FAILURE_RECOVERY = "failure_recovery"


class ConversationTurn(BaseModel):
    role: str = "user"
    content: str


class TestCase(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("tc"))
    type: TestCaseType
    turns: List[ConversationTurn]
    requirement_ids: List[str] = Field(default_factory=list)
    scenario_id: Optional[str] = None
    related_tool: Optional[str] = None
    # Deterministic expectations used by the rule-based judge.
    must_contain: List[str] = Field(default_factory=list)
    must_not_contain: List[str] = Field(default_factory=list)
    allowed_tools: Optional[List[str]] = None  # None => no restriction beyond agent.disallowed_tools
    expect_tool_call: bool = False
    description: str = ""
    # Business acceptance criteria this test case is meant to verify
    # (feeds the business/MVP LLM judge as its rubric).
    acceptance_criteria: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Execution / tracing
# --------------------------------------------------------------------------
class ToolCallRecord(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    schema_valid: Optional[bool] = None
    schema_errors: List[str] = Field(default_factory=list)


class TraceRecord(BaseModel):
    test_case_id: str
    request_payload: Dict[str, Any]
    response_text: str = ""
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    latency_ms: float = 0.0
    tokens_estimated: int = 0
    error: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None  # id assigned by the tracing backend, if any
    trace_backend: Optional[str] = None  # "langfuse" | "otel" | "langsmith" | "console"


# --------------------------------------------------------------------------
# Evaluation (multi-tier: rule-based, LLM safety/hallucination, LLM business)
# --------------------------------------------------------------------------
class RuleCheck(BaseModel):
    name: str
    passed: bool
    detail: str = ""
    critical: bool = False


class EvalResult(BaseModel):
    test_case_id: str
    test_case_type: TestCaseType
    rule_score: float
    rule_checks: List[RuleCheck]
    safety_score: Optional[float] = None
    safety_rationale: str = ""
    business_score: Optional[float] = None
    business_rationale: str = ""
    deepeval_score: Optional[float] = None
    deepeval_metric: Optional[str] = None
    composite_score: float
    passed: bool
    requirement_ids: List[str] = Field(default_factory=list)
    violated_requirement_ids: List[str] = Field(default_factory=list)
    trace: TraceRecord


# --------------------------------------------------------------------------
# Regression
# --------------------------------------------------------------------------
class RegressionReport(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    baseline_pass_rate: float
    candidate_pass_rate: float
    baseline_avg_score: float
    candidate_avg_score: float
    pass_rate_delta: float
    avg_score_delta: float
    regressed: bool
    regressed_test_case_types: List[str] = Field(default_factory=list)
    newly_failed_test_cases: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Run report (top-level artifact)
# --------------------------------------------------------------------------
class ReleaseGateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class RunReport(BaseModel):
    run_id: str = Field(default_factory=lambda: _new_id("run"))
    tenant_id: str
    agent_id: str
    agent_name: str
    created_at: float = Field(default_factory=time.time)
    is_baseline: bool = False
    requirement_analysis: RequirementAnalysis
    test_cases_count: int
    results: List[EvalResult]
    pass_rate: float
    avg_score: float
    release_gate: ReleaseGateStatus
    regression: Optional[RegressionReport] = None
    requirement_coverage: Dict[str, str] = Field(default_factory=dict)  # requirement_id -> PASS/FAIL/UNTESTED


class CreateAgentRequest(BaseModel):
    name: str
    description: str = ""
    endpoint_url: HttpUrl
    system_prompt: str = ""
    tools: List[ToolSchema] = Field(default_factory=list)
    auth_header: Optional[str] = None
    disallowed_tools: List[str] = Field(default_factory=list)


class CreateRunRequest(BaseModel):
    agent_id: str
    use_case_definition: str = ""
    business_requirements: List[str] = Field(default_factory=list)
    pdf_text: str = ""
    is_baseline: bool = False
    max_test_cases: Optional[int] = None
