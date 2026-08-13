from avaas.models.schemas import AgentSpec, AnalyzeRequirementsRequest, RequirementSource, ToolSchema
from avaas.requirements_analysis.extractor import analyze_requirements


def _agent(**overrides) -> AgentSpec:
    defaults = dict(
        tenant_id="tenant_test",
        name="Test Agent",
        endpoint_url="http://localhost:9000/invoke",
        system_prompt="You are helpful.",
        tools=[
            ToolSchema(
                name="get_order_status",
                description="Look up order status",
                parameters={"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
            )
        ],
    )
    defaults.update(overrides)
    return AgentSpec(**defaults)


def test_explicit_business_requirements_are_tagged_explicit():
    req = AnalyzeRequirementsRequest(business_requirements=["Must never lie.", "Must be polite."])
    analysis = analyze_requirements(req, agent=_agent())
    explicit = [r for r in analysis.requirements if r.source == RequirementSource.EXPLICIT]
    assert len(explicit) == 2
    assert explicit[0].requirement == "Must never lie."
    assert explicit[0].acceptance_criteria == ["Must never lie."]


def test_no_explicit_requirements_yields_a_gap():
    req = AnalyzeRequirementsRequest()
    analysis = analyze_requirements(req, agent=_agent())
    assert analysis.analysis_summary.requirements_completeness.value == "insufficient"
    assert any("no explicit business requirements" in g.description.lower() for g in analysis.requirement_gaps)


def test_inferred_requirements_never_authoritative_but_reported():
    agent = _agent()
    req = AnalyzeRequirementsRequest()
    analysis = analyze_requirements(req, agent=agent)
    tool_reqs = [r for r in analysis.requirements if r.related_tool == "get_order_status"]
    assert tool_reqs
    assert all(r.source == RequirementSource.INFERRED for r in tool_reqs)
    # Per the critical rule: an inferred "tool exists" requirement must not
    # assert the tool is authorized to be called.
    assert "authoriz" not in tool_reqs[0].requirement.lower()


def test_disallowed_tools_generate_a_derived_safety_requirement():
    agent = _agent(disallowed_tools=["delete_account"])
    analysis = analyze_requirements(AnalyzeRequirementsRequest(), agent=agent)
    matches = [r for r in analysis.requirements if "delete_account" in r.requirement]
    assert matches
    assert matches[0].source == RequirementSource.DERIVED


def test_use_case_definition_produces_a_use_case_and_scenarios():
    agent = _agent()
    req = AnalyzeRequirementsRequest(
        use_case_definition="Customer wants to check an order's status.",
        business_requirements=["The agent must always confirm the order id before answering."],
    )
    analysis = analyze_requirements(req, agent=agent)
    assert len(analysis.use_cases) == 1
    assert analysis.test_scenarios  # normal/edge/boundary/etc all present
    scenario_types = {s.type.value for s in analysis.test_scenarios}
    assert {"normal", "edge", "boundary", "negative", "injection", "multi_turn"}.issubset(scenario_types)


def test_pdf_text_is_split_into_explicit_requirements():
    req = AnalyzeRequirementsRequest(pdf_text="Refunds over $500 require manager approval.\nOrders must be verified before cancellation.")
    analysis = analyze_requirements(req, agent=_agent())
    explicit = [r for r in analysis.requirements if r.source == RequirementSource.EXPLICIT]
    assert len(explicit) == 2
