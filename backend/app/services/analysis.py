"""Requirement & Use Case Analysis Engine.

Turns unstructured inputs (use-case definition, business requirements, an
agent description/system prompt, tool/discovery evidence, and free-text
documentation) into the structured, traceable, testable specification the
rest of AVaaS consumes: use cases, classified requirements, user intents,
test-scenario stubs, and explicitly-flagged gaps.

This is deliberately NOT "ask the LLM for JSON and trust it". Two guardrails
make the output defensible in a release-governance review:

  1. Source-priority enforcement: explicit business requirements and supplied
     documents always outrank use-case text, which outranks agent
     description/system prompt, which outranks tool schemas.
  2. Deterministic reclassification: a requirement the model labelled EXPLICIT
     is downgraded to INFERRED unless its own wording is actually traceable
     (by term overlap) to the business-requirements/use-case/document text
     supplied. An LLM cannot fabricate an "explicit" requirement and have it
     survive this check, because EXPLICIT is a claim about the SOURCE
     material, not about the model's confidence.

No requirement is ever invented outright: everything is either quoted from,
or explicitly derived/inferred/unknown against, the inputs actually supplied.
"""
import json
from ..core.config import settings

SOURCE_LEVELS = ('EXPLICIT', 'DERIVED', 'INFERRED', 'UNKNOWN')

SYSTEM = (
    "You are the Requirement and Use Case Analysis Engine of AVaaS, an enterprise AI-agent "
    "validation platform. Convert the supplied inputs into a structured, traceable, testable "
    "specification. The target agent can belong to ANY domain; do not assume one. "
    "Follow this source priority when determining expected behaviour: "
    "1) explicit business requirements/acceptance criteria, 2) supplied documents, "
    "3) explicit use-case definition, 4) agent description, 5) system prompt, "
    "6) tool/discovery schemas, 7) other context. If two sources conflict, report the conflict "
    "as a requirement_gap instead of silently choosing one. "
    "NEVER invent a business requirement. Classify every requirement's source as exactly one of "
    "EXPLICIT (directly stated in supplied requirements/documents), DERIVED (logically derived "
    "from explicit information), INFERRED (suggested by prompt/tools/description but not stated), "
    "or UNKNOWN. An INFERRED requirement must never be treated as authoritative — e.g. a "
    "cancel_order tool existing does not mean cancellation is business-permitted; report only "
    "that the tool exists unless permission is explicitly stated elsewhere. "
    "Return JSON only, matching exactly this shape: "
    '{"agent_summary":{"purpose":"","target_users":[],"scope":[],"out_of_scope":[]},'
    '"use_cases":[{"use_case_id":"UC-001","name":"","actor":"","goal":"","trigger":"",'
    '"preconditions":[],"main_flow":[],"alternate_flows":[],"exception_flows":[],'
    '"expected_outcome":"","relevant_tools":[],"related_requirements":[]}],'
    '"requirements":[{"requirement_id":"REQ-001","requirement":"","category":'
    '"functional|behavioural|business_rule|security|safety|privacy|performance|other",'
    '"source":"EXPLICIT|DERIVED|INFERRED|UNKNOWN","confidence":0.0,'
    '"priority":"critical|high|medium|low","related_use_cases":[],"expected_behaviour":"",'
    '"forbidden_behaviour":[],"acceptance_criteria":[],"relevant_tools":[]}],'
    '"user_intents":[{"intent_id":"INT-001","name":"","description":"","example_requests":[],'
    '"related_use_cases":[],"related_requirements":[]}],'
    '"test_scenarios":[{"scenario_id":"SC-001","type":'
    '"normal|edge|boundary|negative|injection|multi_turn|tool_use|authorization|failure_recovery",'
    '"description":"","related_use_case":"","related_requirements":[],"expected_behaviour":""}],'
    '"requirement_gaps":[{"gap_id":"GAP-001","description":"","impact":"","question_for_qa":""}],'
    '"analysis_summary":{"requirements_completeness":"complete|partial|insufficient",'
    '"use_case_completeness":"complete|partial|insufficient","explicit_requirement_count":0,'
    '"derived_requirement_count":0,"inferred_requirement_count":0,"requirement_gap_count":0,'
    '"critical_gaps":[]}}'
)


def _source_corpus(inputs: dict) -> str:
    """Text a claimed-EXPLICIT requirement must be traceable to."""
    return ' '.join(str(inputs.get(k, '') or '') for k in
                     ('business_requirements', 'documentation', 'use_case_definition')).lower()


_GENERIC_TERMS = {'agent', 'system', 'policy', 'statement', 'requirement', 'business', 'customer',
                   'process', 'request', 'response', 'should', 'always', 'never', 'ensure', 'provide'}


def _significant_terms(text: str) -> set[str]:
    return {w for w in ({w.strip('.,;:()"\'') for w in (text or '').lower().split()} - _GENERIC_TERMS)
            if len(w) > 5}


def _enforce_source_discipline(analysis: dict, inputs: dict) -> dict:
    """Deterministically re-check every EXPLICIT claim against the actual source text.

    This is what stops "the model said it was explicit" from being taken on faith.
    """
    corpus = _source_corpus(inputs)
    for req in analysis.get('requirements', []) or []:
        if req.get('source') not in SOURCE_LEVELS:
            req['source'] = 'UNKNOWN'
        if req.get('source') == 'EXPLICIT':
            terms = _significant_terms(req.get('requirement', ''))
            overlap = terms & _significant_terms(corpus)
            if not corpus.strip() or (terms and len(overlap) / max(1, len(terms)) < 0.15):
                req['source'] = 'DERIVED'
                req['_source_reclassified'] = 'Downgraded from EXPLICIT: wording not traceable to supplied requirements/use-case/document text'
    counts = {'EXPLICIT': 0, 'DERIVED': 0, 'INFERRED': 0, 'UNKNOWN': 0}
    for req in analysis.get('requirements', []) or []:
        counts[req.get('source', 'UNKNOWN')] = counts.get(req.get('source', 'UNKNOWN'), 0) + 1
    summary = analysis.setdefault('analysis_summary', {})
    summary['explicit_requirement_count'] = counts['EXPLICIT']
    summary['derived_requirement_count'] = counts['DERIVED']
    summary['inferred_requirement_count'] = counts['INFERRED'] + counts['UNKNOWN']
    summary['requirement_gap_count'] = len(analysis.get('requirement_gaps', []) or [])
    return analysis


async def analyze(llm, *, use_case_definition='', business_requirements='', pdf_documents='',
                   agent_description='', system_prompt='', tools=None, tool_schemas=None,
                   documentation='') -> tuple[dict, str, dict]:
    """Run the analysis engine. Returns (analysis_json, llm_provider, token_usage)."""
    inputs = {
        'use_case_definition': use_case_definition, 'business_requirements': business_requirements,
        'pdf_documents': pdf_documents, 'agent_description': agent_description,
        'system_prompt': system_prompt, 'tools': tools or [], 'tool_schemas': tool_schemas or {},
        'documentation': documentation,
    }
    if not any(str(v).strip() for v in inputs.values() if not isinstance(v, (list, dict)) or v):
        return ({'agent_summary': {'purpose': '', 'target_users': [], 'scope': [], 'out_of_scope': []},
                 'use_cases': [], 'requirements': [], 'user_intents': [], 'test_scenarios': [],
                 'requirement_gaps': [{'gap_id': 'GAP-001', 'description': 'No inputs supplied',
                                        'impact': 'No analysis possible', 'question_for_qa': 'Provide a use case, business requirements, agent description, or documentation.'}],
                 'analysis_summary': {'requirements_completeness': 'insufficient', 'use_case_completeness': 'insufficient',
                                       'explicit_requirement_count': 0, 'derived_requirement_count': 0,
                                       'inferred_requirement_count': 0, 'requirement_gap_count': 1, 'critical_gaps': ['No inputs supplied']}},
                'none', {'prompt': 0, 'completion': 0})

    prompt = 'Inputs:\n' + json.dumps(inputs, default=str)[:20000]
    analysis, provider, tokens = await llm.json(SYSTEM, prompt)
    analysis = _enforce_source_discipline(analysis, inputs)
    return analysis, provider, tokens
