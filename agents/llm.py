"""Model access: Foundry (keyless) or offline, plus a resilient call wrapper."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel


@dataclass
class CallResult:
    value: Any | None
    tool_texts: list[str] = field(default_factory=list)
    error: str | None = None
    seconds: float = 0.0
    attempts: int = 0
    tool_errors: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    blocked: str | None = None          # the Foundry guardrail control that stopped the call
    errors: list[str] = field(default_factory=list)     # one line per failed attempt
    session: Any = None                 # the session the successful (or last) attempt used


GUARDRAIL_LABELS = {
    "jailbreak": "Prompt Shields (user prompt attack)", "indirect_attack": "Prompt Shields (indirect attack)",
    "hate": "content filter (hate)", "sexual": "content filter (sexual)", "violence": "content filter (violence)",
    "self_harm": "content filter (self-harm)", "profanity": "profanity filter",
    "protected_material_text": "protected material", "protected_material_code": "protected material",
    "custom_blocklists": "blocklist",
}
# A control that fired, written out in an error message: 'jailbreak': {'detected': True, 'filtered': True}
_FILTERED_IN_TEXT = re.compile(r"['\"](\w+)['\"]:\s*\{[^{}]*?['\"]filtered['\"]:\s*(?:True|true)")


def _filtered_keys(obj, parent: str | None = None) -> list[str]:
    """Every control marked filtered, wherever the error body puts it (Chat Completions: innererror.
    content_filter_result; Responses API: content_filters[].content_filter_results)."""
    out: list[str] = []
    if isinstance(obj, dict):
        if obj.get("filtered") is True and parent:
            out.append(parent)
        for k, v in obj.items():
            out += _filtered_keys(v, k)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += _filtered_keys(v, parent)
    else:
        if getattr(obj, "filtered", False) and parent:     # Agent Framework's ContentFilterResult objects
            out.append(parent)
    return out


def guardrail_hit(e: BaseException) -> str | None:
    """Which guardrail control stopped a model call, or None if `e` is some other error."""
    try:
        from agent_framework.exceptions import ChatClientContentFilterException as CF
    except ImportError:                       # pragma: no cover
        CF = ()
    chain, seen, x = [], set(), e
    while isinstance(x, BaseException) and id(x) not in seen:
        seen.add(id(x))
        chain.append(x)
        x = x.__cause__ or x.__context__ or next((a for a in x.args if isinstance(a, BaseException)), None)
    text = " ".join(str(c) for c in chain)
    if not (any(isinstance(c, CF) for c in chain) or "content_filter" in text
            or "ResponsibleAIPolicyViolation" in text or "content management policy" in text):
        return None
    hits: list[str] = []
    for c in chain:
        hits += _filtered_keys(getattr(c, "content_filter_result", None) or {})
        hits += _filtered_keys(getattr(c, "body", None))
    hits = [h for h in hits if h not in ("content_filter_result", "content_filter_results", "innererror", "error")]
    hits = hits or _FILTERED_IN_TEXT.findall(text)
    labels = list(dict.fromkeys(GUARDRAIL_LABELS.get(h, h.replace("_", " ")) for h in hits))
    return ", ".join(labels) or "content filter"


def make_client(mode: str, max_function_calls: int = 8, model: str | None = None):
    """Return a chat client, or None in offline mode. model: a deployment name other than FOUNDRY_MODEL."""
    if mode == "offline":
        return None
    if mode == "foundry":
        from azure.identity import DefaultAzureCredential
        from agent_framework.foundry import FoundryChatClient
        # Reads FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL from the environment / .env.
        # Keyless: az login locally, managed identity on Azure.
        from pathlib import Path
        env = Path(__file__).resolve().parent.parent / ".env"
        return FoundryChatClient(
            credential=DefaultAzureCredential(), env_file_path=str(env) if env.exists() else None,
            **({"model": model} if model else {}),
            # Bound every agent's tool loop: no runaway tool calling during a live match.
            function_invocation_configuration={"max_iterations": 6, "max_function_calls": max_function_calls,
                                               "include_detailed_errors": True})
    raise ValueError(f"Unknown mode {mode}")


def model_options(reasoning_effort: str | None) -> dict:
    opts: dict[str, Any] = {}
    if reasoning_effort:
        opts["reasoning"] = {"effort": reasoning_effort}
    return opts


def tool_errors(response: Any) -> list[str]:
    """Tool calls that failed, with the tool's own error message."""
    out = []
    for m in getattr(response, "messages", []) or []:
        for c in getattr(m, "contents", []) or []:
            if getattr(c, "type", None) == "function_result" and getattr(c, "exception", None):
                out.append(str(c.exception))
    return out


def tool_names(response: Any) -> list[str]:
    """Names of the tools the agent called, in order."""
    return [c.name for m in getattr(response, "messages", []) or [] for c in getattr(m, "contents", []) or []
            if getattr(c, "type", None) == "function_call" and getattr(c, "name", None)]


def tool_texts(response: Any) -> list[str]:
    """Text of every tool result the agent saw (becomes evidence for the Verifier)."""
    out = []
    for m in getattr(response, "messages", []) or []:
        for c in getattr(m, "contents", []) or []:
            if getattr(c, "type", None) == "function_result":
                r = getattr(c, "result", None)
                if r is None:
                    continue
                if isinstance(r, list):
                    out.append(" ".join(str(getattr(x, "text", x)) for x in r))
                else:
                    out.append(str(getattr(r, "text", r)))
    return out


def _unanswered_calls(resp: Any) -> int:
    calls, answered = set(), set()
    for m in getattr(resp, "messages", []) or []:
        for c in getattr(m, "contents", []) or []:
            if getattr(c, "type", None) == "function_call":
                calls.add(getattr(c, "call_id", None))
            elif getattr(c, "type", None) == "function_result":
                answered.add(getattr(c, "call_id", None))
    return len(calls - answered)


async def ask(agent: Any, prompt: str, schema: type[BaseModel], timeout_s: float = 90.0, retries: int = 1,
              options: dict | None = None, session: Any = None) -> CallResult:
    """session: a conversation kept across calls (the Scout's rewrite)."""
    t0 = time.time()
    last = None
    errors: list[str] = []
    for attempt in range(retries + 1):
        try:
            opts = {"response_format": schema, **(options or {})}
            resp = await asyncio.wait_for(agent.run(prompt, options=opts, session=session), timeout_s)
            if str(getattr(resp, "finish_reason", "") or "") == "content_filter":     # the reply itself was filtered
                return CallResult(None, tool_texts(resp), "blocked by the Foundry guardrail (output)",
                                  time.time() - t0, attempt + 1, tool_errors(resp), tool_names(resp),
                                  blocked="content filter (output)")
            value = resp.value
            if value is None:
                text = _json_block(resp.text)
                if not text:
                    raise ValueError(f"no answer in the reply (finish={getattr(resp, 'finish_reason', None)}, "
                                     f"tool calls without results={_unanswered_calls(resp)}, "
                                     f"tools used={len(tool_names(resp))}, tool errors={tool_errors(resp)[:2]})")
                value = schema.model_validate_json(text)
            elif not isinstance(value, schema):
                value = schema.model_validate(value)
            return CallResult(value, tool_texts(resp), None, time.time() - t0, attempt + 1, tool_errors(resp),
                              tool_names(resp), errors=errors, session=session)
        except Exception as e:  # timeouts, auth, rate limits, invalid JSON...
            last = f"{type(e).__name__}: {str(e)[:300]}"
            errors.append(f"attempt {attempt + 1}: {last}")
            blocked = guardrail_hit(e)
            if blocked:                       # asking again would be blocked again
                return CallResult(None, [], f"blocked by the Foundry guardrail: {blocked}", time.time() - t0,
                                  attempt + 1, blocked=blocked, errors=errors, session=session)
            if session is not None and hasattr(agent, "create_session"):
                session = agent.create_session()
            if attempt < retries:
                throttled = "429" in last or "rate" in last.lower()
                wait = (10.0 if throttled else 2.0) * (attempt + 1)
                hint = re.search(r"retry after (\d+) second", str(e), re.I)     # Azure says how long to wait
                if hint:
                    wait = max(wait, min(60.0, float(hint.group(1)) + 1))
                await asyncio.sleep(wait)
    return CallResult(None, [], last, time.time() - t0, retries + 1, errors=errors, session=session)


def _json_block(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start >= 0 else text


# Scripted model for tests and dry runs (no network)

def scripted_client(responder: Callable[[type | None, list], Any]):
    """A chat client whose replies come from `responder(response_format, messages)`."""
    from agent_framework import BaseChatClient, ChatResponse, FunctionInvocationLayer, Message

    class ScriptedChatClient(FunctionInvocationLayer, BaseChatClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def _inner_get_response(self, *, messages, stream, options, **kwargs):
            self.calls += 1
            reply = responder(options.get("response_format"), list(messages))
            contents = reply if isinstance(reply, list) else [reply]
            return ChatResponse(messages=[Message(role="assistant", contents=contents)], response_id=f"scripted-{self.calls}")

    return ScriptedChatClient()


def prompt_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)
