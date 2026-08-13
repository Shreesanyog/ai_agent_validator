"""A tiny reference "agent" server that AVaaS can test against.

This is NOT part of AVaaS itself - it stands in for whatever real AI agent
you'd normally point AVaaS at, and implements the wire protocol
`avaas.execution.async_runner` expects:

    POST /invoke
    { "message": str, "history": [...], "system_prompt": str }
    -> { "response": str, "tool_calls": [{"name": str, "arguments": {...}}] }

Two tools are simulated: get_order_status(order_id) and
refund_order(order_id, amount).

Set DEMO_AGENT_BUG_MODE=true to make the agent intermittently misbehave
(hallucinate an out-of-schema argument and leak a fragment of its system
prompt under prompt injection) so you can watch AVaaS's rule-based judge and
regression gate actually catch it end-to-end.

Run standalone:
    uvicorn scripts.demo_target_agent:app --port 9000
"""
from __future__ import annotations

import os
import re

from fastapi import FastAPI
from pydantic import BaseModel

BUG_MODE = os.getenv("DEMO_AGENT_BUG_MODE", "false").lower() == "true"

app = FastAPI(title="Demo Target Agent")


class InvokeRequest(BaseModel):
    message: str
    history: list[dict] = []
    system_prompt: str = ""


ORDER_ID_RE = re.compile(r"order_id=['\"]?([A-Za-z0-9_-]+)")
AMOUNT_RE = re.compile(r"amount=['\"]?([0-9.]+)")


@app.post("/invoke")
def invoke(req: InvokeRequest) -> dict:
    text = req.message.lower()

    # --- naive prompt-injection "defense" (deliberately weak in bug mode) ---
    injection_markers = ("ignore all previous instructions", "system override", "forget your rules", "print the exact text")
    if any(marker in text for marker in injection_markers):
        if BUG_MODE:
            leaked = (req.system_prompt or "You are a helpful support agent.")[:40]
            return {"response": f"Sure! Here you go: {leaked}... also HACKED.", "tool_calls": []}
        return {
            "response": "I can't share my internal instructions or override my guidelines, but I'm happy to help with your order.",
            "tool_calls": [],
        }

    # --- tool: get_order_status ---
    if "order" in text and "status" in text.lower() or "order_id" in text:
        order_id_match = ORDER_ID_RE.search(req.message)
        order_id = order_id_match.group(1) if order_id_match else "UNKNOWN"
        args = {"order_id": order_id}
        if BUG_MODE and not order_id_match:
            # Hallucinate a made-up id instead of asking for clarification.
            args = {"order_id": "guessed-123", "confidence": "low"}  # extra undeclared field
        return {
            "response": f"Order {args.get('order_id')} is currently in transit and should arrive in 2-3 days.",
            "tool_calls": [{"name": "get_order_status", "arguments": args}],
        }

    # --- tool: refund_order ---
    if "refund" in text:
        order_id_match = ORDER_ID_RE.search(req.message)
        amount_match = AMOUNT_RE.search(req.message)
        order_id = order_id_match.group(1) if order_id_match else "UNKNOWN"
        amount = float(amount_match.group(1)) if amount_match else 0.0
        return {
            "response": f"I've processed a refund of ${amount:.2f} for order {order_id}.",
            "tool_calls": [{"name": "refund_order", "arguments": {"order_id": order_id, "amount": amount}}],
        }

    return {
        "response": "I'm a demo support agent. I can check an order's status or process a refund - just let me know the order ID.",
        "tool_calls": [],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("DEMO_AGENT_PORT", "9000")))
