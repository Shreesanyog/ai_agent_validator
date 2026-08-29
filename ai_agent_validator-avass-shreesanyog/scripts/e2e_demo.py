"""End-to-end demo against a running AVaaS backend + mock agent.

Walks the full chain the platform exists to prove:
  register -> project -> requirement -> analysis -> target -> run -> results
  -> traceability -> regression/release gate

Usage (with backend on :8000 and mock-agent on :9100):
    python scripts/e2e_demo.py
"""
import json
import sys
import time
import urllib.request

API = "http://localhost:8000/api/v1"
MOCK = "http://localhost:9100"


def call(path, method="GET", body=None, token=None):
    req = urllib.request.Request(API + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data) as r:
        return json.loads(r.read() or "{}")


def main():
    stamp = str(int(time.time()))
    print("1. Registering tenant...")
    auth = call("/auth/register", "POST", {
        "organization": f"Demo {stamp}", "slug": f"demo-{stamp}",
        "email": f"demo{stamp}@example.com", "password": "CorrectHorse123!"})
    token = auth["access_token"]

    print("2. Creating project...")
    pid = call("/projects", "POST", {"name": "E2E Demo"}, token=token)["id"]

    print("3. Adding a business requirement...")
    call(f"/projects/{pid}/requirements", "POST", {
        "source": "user", "authoritative": True,
        "text": "Agent must create a ticket when a customer reports a defect",
        "acceptance": ["A ticket exists in the downstream system"]}, token=token)

    print("4. Running the Requirement & Use Case Analysis Engine...")
    analysis = call(f"/projects/{pid}/analysis", "POST", {
        "business_requirements": "Agent must create a ticket when a customer reports a defect.",
        "agent_description": "Customer support agent for an e-commerce store."}, token=token)
    print(f"   analysis v{analysis['version_no']}, "
          f"{analysis['analysis'].get('analysis_summary', {}).get('explicit_requirement_count', 0)} explicit requirement(s)")

    print("5. Registering the mock agent as a target...")
    tid = call(f"/projects/{pid}/targets", "POST", {
        "name": "Mock Agent", "base_url": MOCK, "mode": "rest",
        "config": {"path": "/chat", "prompt_field": "message",
                   "response_path": "response", "session_field": "session_id"}},
        token=token)["id"]

    print("6. Starting a validation run (needs Ollama or GEMINI_API_KEY)...")
    run = call(f"/targets/{tid}/runs", "POST", {"max_cases": 4}, token=token)
    rid = run["id"]

    for _ in range(60):
        time.sleep(2)
        detail = call(f"/runs/{rid}", token=token)
        if detail["run"]["status"] in ("completed", "failed"):
            break
    detail = call(f"/runs/{rid}", token=token)
    r = detail["run"]
    print(f"   status={r['status']} gate={r.get('release_gate')} "
          f"score={r.get('score')} risk={r.get('risk_score')}")

    if r["status"] != "completed":
        print("   Run did not complete — check that an LLM provider is configured.")
        print("   ", r.get("summary"))
        return 1

    print("7. Traceability chain:")
    trace = call(f"/runs/{rid}/traceability", token=token)
    print(f"   {trace['requirements_traced']} requirement(s) traced, "
          f"{trace['untraced_result_count']} untraced result(s)")

    print("8. Regression / release gate:")
    gate = call(f"/runs/{rid}/regression", token=token)
    print(f"   decision={gate['decision']} — {gate['summary']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as e:
        print(f"Could not reach the API/mock agent: {e}")
        print("Start them first (see README 'Complete end-to-end example').")
        sys.exit(1)
