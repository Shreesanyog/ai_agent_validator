from avaas.models.schemas import AgentSpec, ToolSchema, RequirementSource
from avaas.requirements_analysis.extractor import extract_requirements


def _agent(**overrides) -> AgentSpec:
    defaults = dict(
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


def test_explicit_requirements_are_used_verbatim():
    reqs = extract_requirements(_agent(), explicit_requirements=["Must never lie.", "Must be polite."])
    assert len(reqs) == 2
    assert all(r.source == RequirementSource.EXPLICIT for r in reqs)
    assert reqs[0].text == "Must never lie."


def test_inferred_requirements_cover_every_tool():
    agent = _agent()
    reqs = extract_requirements(agent, explicit_requirements=None)
    tool_reqs = [r for r in reqs if r.related_tool == "get_order_status"]
    assert len(tool_reqs) >= 2
    assert all(r.source == RequirementSource.INFERRED for r in reqs)


def test_disallowed_tools_generate_a_safety_requirement():
    agent = _agent(disallowed_tools=["delete_account"])
    reqs = extract_requirements(agent)
    assert any("delete_account" in r.text for r in reqs)
