"""Tests for the Requirement & Use Case Analysis Engine.

The central property under test is the source-discipline guardrail: a
requirement the LLM claims is EXPLICIT must actually be traceable to the
supplied source text, or it gets deterministically downgraded. This is what
prevents "the model said it was explicit" from being taken on faith.
"""
import asyncio
from app.services import analysis


class FakeLLM:
    """Returns a canned analysis payload without calling a real provider."""
    def __init__(self, payload):
        self.payload = payload

    async def json(self, system, prompt):
        return self.payload, 'fake', {'prompt': 10, 'completion': 20}


def test_no_inputs_returns_empty_analysis_with_gap():
    result, provider, tokens = asyncio.run(analysis.analyze(FakeLLM({})))
    assert provider == 'none'
    assert result['requirement_gaps'], 'must flag the absence of any input as a gap'
    assert result['analysis_summary']['requirements_completeness'] == 'insufficient'


def test_explicit_claim_traceable_to_source_survives():
    payload = {
        'requirements': [{
            'requirement_id': 'REQ-001',
            'requirement': 'Refunds must be issued within 14 days of a valid return request',
            'source': 'EXPLICIT',
        }],
        'use_cases': [], 'user_intents': [], 'test_scenarios': [], 'requirement_gaps': [],
        'analysis_summary': {},
    }
    result, _, _ = asyncio.run(analysis.analyze(
        FakeLLM(payload),
        business_requirements='Refunds must be issued within fourteen days of a valid return request being approved.'))
    assert result['requirements'][0]['source'] == 'EXPLICIT'
    assert result['analysis_summary']['explicit_requirement_count'] == 1


def test_fabricated_explicit_claim_is_downgraded():
    """The model claims EXPLICIT for something that never appears in any supplied source."""
    payload = {
        'requirements': [{
            'requirement_id': 'REQ-001',
            'requirement': 'Agent must automatically approve refunds above ten thousand dollars without manager review',
            'source': 'EXPLICIT',
        }],
        'use_cases': [], 'user_intents': [], 'test_scenarios': [], 'requirement_gaps': [],
        'analysis_summary': {},
    }
    result, _, _ = asyncio.run(analysis.analyze(
        FakeLLM(payload),
        business_requirements='Customer support agent handles order status questions.'))
    req = result['requirements'][0]
    assert req['source'] == 'DERIVED', 'a fabricated EXPLICIT claim must be deterministically downgraded'
    assert '_source_reclassified' in req


def test_inferred_tool_existence_is_not_promoted_to_permission():
    """A cancel_order tool existing must not itself become 'cancellation is permitted'."""
    payload = {
        'requirements': [{
            'requirement_id': 'REQ-001',
            'requirement': 'Agent is allowed to cancel orders because a cancel_order tool exists',
            'source': 'EXPLICIT',
        }],
        'use_cases': [], 'user_intents': [], 'test_scenarios': [], 'requirement_gaps': [],
        'analysis_summary': {},
    }
    result, _, _ = asyncio.run(analysis.analyze(
        FakeLLM(payload), tools=['cancel_order'], tool_schemas={'cancel_order': {}}))
    assert result['requirements'][0]['source'] != 'EXPLICIT'


def test_invalid_source_label_is_normalized_to_unknown():
    payload = {'requirements': [{'requirement_id': 'REQ-001', 'requirement': 'x', 'source': 'TOTALLY_MADE_UP'}],
               'use_cases': [], 'user_intents': [], 'test_scenarios': [], 'requirement_gaps': [], 'analysis_summary': {}}
    result, _, _ = asyncio.run(analysis.analyze(FakeLLM(payload), business_requirements='x'))
    assert result['requirements'][0]['source'] == 'UNKNOWN'


def test_summary_counts_reflect_reclassification():
    payload = {'requirements': [
        {'requirement_id': 'REQ-001', 'requirement': 'traceable statement about refund timing', 'source': 'EXPLICIT'},
        {'requirement_id': 'REQ-002', 'requirement': 'completely fabricated unrelated statement about spaceships', 'source': 'EXPLICIT'},
    ], 'use_cases': [], 'user_intents': [], 'test_scenarios': [], 'requirement_gaps': [], 'analysis_summary': {}}
    result, _, _ = asyncio.run(analysis.analyze(
        FakeLLM(payload), business_requirements='There is a traceable statement about refund timing in this policy.'))
    assert result['analysis_summary']['explicit_requirement_count'] == 1
    assert result['analysis_summary']['derived_requirement_count'] == 1
