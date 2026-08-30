"""Standalone mock target agent for AVaaS end-to-end validation.

Runnable on its own (`uvicorn main:app --port 9100`) or via docker-compose,
this simulates a real REST agent so the whole AVaaS pipeline — ingestion,
async execution, trace collection, rule/LLM/business evaluation, regression
and release gating — can be exercised locally without any external LLM/API.

Every branch the AVaaS spec asks a mock agent to demonstrate is present and
selected deterministically by keywords in the incoming message, so tests are
reproducible:

  normal request .............. default reply
  invalid input ............... empty/blank message -> 422
  multi-turn conversation ..... session_id remembers turn count
  tool call ................... "order" -> emits a tool_calls trace
  business-rule violation ..... "refund 999999" -> approves over-limit refund
  malformed response .......... "malformed" -> returns broken JSON as text
  simulated latency ........... "slow" -> sleeps before replying
  downstream state change ..... "create ticket" -> mutates in-memory store
  trace metadata .............. every reply carries latency + span id
"""
import asyncio
import json
import time
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AVaaS Mock Agent", version="1.0.0")

# In-memory "downstream system" so state-change verification has something real
# to check against. Reset on process restart; never used for anything durable.
SESSIONS: dict[str, list[str]] = {}
TICKETS: dict[str, dict] = {}

REFUND_LIMIT = 1000  # business rule: refunds above this need manager approval


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: list[dict] = []
    latency_ms: float = 0.0
    span_id: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-agent"}


@app.get("/state/tickets")
def list_tickets():
    """State-verification endpoint: AVaaS can assert a ticket was really created."""
    return {"count": len(TICKETS), "tickets": list(TICKETS.values())}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    start = time.perf_counter()
    span_id = uuid.uuid4().hex[:16]
    sid = req.session_id or uuid.uuid4().hex

    # invalid input -> real validation failure
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")

    history = SESSIONS.setdefault(sid, [])
    history.append(req.message)
    text = req.message.lower()
    tool_calls: list[dict] = []

    # simulated latency
    if "slow" in text:
        await asyncio.sleep(1.2)

    # malformed response: deliberately return invalid JSON in a JSON-looking string
    if "malformed" in text:
        response = '{"status": "ok", "items": [1, 2,,]}'  # broken on purpose
    # business-rule violation: approve a refund above the limit without approval
    elif "refund" in text:
        amount = next((int(t) for t in text.replace("$", " ").split() if t.isdigit()), 0)
        if amount > REFUND_LIMIT:
            response = f"Approved your refund of ${amount} immediately, no manager approval needed."
        else:
            response = f"Refund of ${amount} is within policy and has been queued."
        tool_calls.append({"name": "process_refund", "arguments": {"amount": amount}})
    # downstream state change
    elif "create ticket" in text or "open ticket" in text:
        tid = uuid.uuid4().hex[:8]
        TICKETS[tid] = {"id": tid, "session": sid, "subject": req.message[:80], "status": "open"}
        tool_calls.append({"name": "create_ticket", "arguments": {"ticket_id": tid}})
        response = f"I've opened ticket {tid} for you."
    # tool call
    elif "order" in text:
        tool_calls.append({"name": "lookup_order", "arguments": {"query": req.message[:60]}})
        response = f"Your order (turn {len(history)}) is on its way."
    # normal / multi-turn default
    else:
        response = f"Reply {len(history)} to: {req.message[:120]}"

    return ChatResponse(
        response=response,
        session_id=sid,
        tool_calls=tool_calls,
        latency_ms=(time.perf_counter() - start) * 1000,
        span_id=span_id,
    )
