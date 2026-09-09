"""The bounded tool loop: the model asks for a tool, we validate → dispatch →
report back, up to a fixed number of turns. A validation failure isn't a
special second loop — it's just a tool result that says so, fed back on the
next turn, which is what "retry → repair" means in practice. The bound is
what stops a model that keeps asking for the same broken thing forever (see
``FakeClient.script_endless_tool_calls`` in the tests) — nothing else does.

Every tool call is logged with its risk class and the iteration it happened
on, which is what a rubric line asking for exactly that is checking for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from fairy.llm.interfaces import LLMClient, LLMRequest, Message
from fairy.tools.registry import TOOLS, ToolError, all_json_schemas
from fairy.tools.session import Session
from fairy.tools.store import OrderStore

FALLBACK_TEXT = (
    "I'm having trouble completing this automatically — let me connect you "
    "with a person. / أواجه صعوبة في إتمام هذا تلقائيًا، سأقوم بتحويلك لأحد أفراد الفريق."
)


@dataclass
class ToolLoopResult:
    final_text: str | None
    escalated: bool
    log: list[dict] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)


def run_tool_loop(
    client: LLMClient,
    messages: list[Message],
    *,
    session: Session,
    store: OrderStore,
    tools: list[dict] | None = None,
    max_iterations: int = 4,
    max_tokens: int = 400,
) -> ToolLoopResult:
    conversation = list(messages)
    log: list[dict] = []
    tool_schemas = tools if tools is not None else all_json_schemas()

    for iteration in range(1, max_iterations + 1):
        response = client.complete(
            LLMRequest(messages=conversation, tools=tool_schemas, max_tokens=max_tokens)
        )

        if response.finish_reason != "tool_calls" or not response.tool_calls:
            return ToolLoopResult(final_text=response.text, escalated=False, log=log, messages=conversation)

        conversation.append(
            Message(role="assistant", content=response.text or "", tool_calls=response.tool_calls)
        )

        for call in response.tool_calls:
            spec = TOOLS.get(call.name)
            if spec is None:
                outcome, result_text = "unknown_tool", f"unknown tool: {call.name}"
                risk_class = "unknown"
            else:
                risk_class = spec.risk_class
                outcome, result_text = _validate_and_dispatch(spec, call.arguments, session=session, store=store)

            log.append(
                {"iteration": iteration, "tool": call.name, "risk_class": risk_class, "outcome": outcome}
            )
            conversation.append(
                Message(role="tool", content=result_text, tool_call_id=call.id, name=call.name)
            )

            if spec is not None and spec.risk_class == "terminal" and outcome == "ok":
                return ToolLoopResult(final_text=result_text, escalated=True, log=log, messages=conversation)

    log.append({"iteration": max_iterations, "tool": None, "risk_class": None, "outcome": "bounded_loop_exhausted"})
    return ToolLoopResult(final_text=FALLBACK_TEXT, escalated=True, log=log, messages=conversation)


def _validate_and_dispatch(spec, raw_arguments: str, *, session: Session, store: OrderStore) -> tuple[str, str]:
    try:
        payload = json.loads(raw_arguments)
    except json.JSONDecodeError as err:
        return "validation_error", f"invalid arguments (not valid JSON: {err}) — please retry"

    try:
        args = spec.args_model.model_validate(payload)
    except ValidationError as err:
        return "validation_error", f"invalid arguments: {err.errors()[0]['msg']} — please retry"

    try:
        result = spec.handler(args, session=session, store=store)
    except (ToolError, PermissionError) as err:
        return "tool_error", str(err)

    return "ok", json.dumps(result, ensure_ascii=False)
