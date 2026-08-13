"""Pydantic schemas shared across the AVaaS pipeline.

These are the contracts between phases described in the architecture:
Agent Onboarding -> Requirement Analysis -> Test Generation ->
Async Execution -> Trace Collection -> Evaluation -> Regression -> Report.
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
    name: str
    description: str = ""
    endpoint_url: HttpUrl
    system_prompt: str = ""
    tools: List[ToolSchema] = Field(default_factory=list)
    auth_header: Optional[str] = None  # e.g. "Bearer <token>", sent as-is if set
    disallowed_tools: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --------------------------------------------------------------------------
# Requirement analysis
# --------------------------------------------------------------------------
class RequirementSource(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class RequirementCategory(str, Enum):
    FUNCTIONAL = "functional"
    SAFETY = "safety"
    PERFORMANCE = "performance"
    SECURITY = "security"


class RequirementItem(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("req"))
    text: str
    category: RequirementCategory = RequirementCategory.FUNCTIONAL
    source: RequirementSource = RequirementSource.INFERRED
    related_tool: Optional[str] = None


# --------------------------------------------------------------------------
# Test generation
# --------------------------------------------------------------------------
class TestCaseType(str, Enum):
    NORMAL = "normal"
    EDGE = "edge"
    BOUNDARY = "boundary"
    INJECTION = "injection"
    MULTI_TURN = "multi_turn"


class ConversationTurn(BaseModel):
    role: str = "user"
    content: str


class TestCase(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("tc"))
    type: TestCaseType
    turns: List[ConversationTurn]
    requirement_ids: List[str] = Field(default_factory=list)
    related_tool: Optional[str] = None
    # Deterministic expectations used by the rule-based judge.
    must_contain: List[str] = Field(default_factory=list)
    must_not_contain: List[str] = Field(default_factory=list)
    allowed_tools: Optional[List[str]] = None  # None => no restriction beyond agent.disallowed_tools
    expect_tool_call: bool = False
    description: str = ""


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


# --------------------------------------------------------------------------
# Evaluation
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
    llm_score: Optional[float] = None
    llm_rationale: str = ""
    composite_score: float
    passed: bool
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
    agent_id: str
    agent_name: str
    created_at: float = Field(default_factory=time.time)
    is_baseline: bool = False
    requirements: List[RequirementItem]
    test_cases_count: int
    results: List[EvalResult]
    pass_rate: float
    avg_score: float
    release_gate: ReleaseGateStatus
    regression: Optional[RegressionReport] = None


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
    explicit_requirements: List[str] = Field(default_factory=list)
    is_baseline: bool = False
    # Optionally cap how many generated test cases to execute (useful for demos).
    max_test_cases: Optional[int] = None
