"""Shared plumbing for the authoring-time model layer.

Everything probabilistic in Attest flows through this module: settings from
.env, one forced-tool call helper, one retry policy, one audit line per call
with estimated cost. The three agents (attest/triage.py, attest/compiler.py,
attest/explainer.py) own their prompts and schemas; this module owns the
wire.

Import discipline: `anthropic` and `dotenv` are imported inside functions,
never at module top. Runtime verbs (snapshot, evaluate, replay, diff) must
work on a machine where neither is installed -- PLAN.md invariant 8, and
main.py's lazy dispatch depends on it.

Retry policy (mirror of RIA's, per docs/PLAN.md): three attempts total, and
only transient failures are retried -- 429 rate limits, 5xx server errors
including 529 overloaded, and transport errors. Auth and other 4xx failures
fail fast: retrying a bad key burns time and hides a configuration error.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from .audit import audit

# Pinned model defaults. These mirror .env.example; changing a model is an
# operator decision made in .env, not an edit here.
DEFAULT_MODEL_TRIAGE = "claude-haiku-4-5-20251001"
DEFAULT_MODEL_COMPILER = "claude-opus-4-8"
DEFAULT_MODEL_EXPLAINER = "claude-haiku-4-5-20251001"

# USD per million tokens, (input, output), prefix-matched on the model id.
# Used only for the audit log's estimated cost; billing truth lives with the
# provider.
_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-8": (5.00, 25.00),
}

MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1.0, 4.0)  # sleep before attempt 2 and attempt 3


class ModelClientError(RuntimeError):
    """An authoring-time model call failed for good: bad credentials, a
    non-transient API error, transient errors exhausting all attempts, or a
    response missing the forced tool call."""


@dataclass(frozen=True)
class Settings:
    """Authoring-time configuration, resolved once per CLI invocation."""

    api_key: str
    model_triage: str
    model_compiler: str
    model_explainer: str


def load_settings() -> Settings:
    """Read .env (if present) into the environment, then resolve settings.

    dotenv is imported lazily and its absence is tolerated: plain environment
    variables are a complete configuration on their own.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return Settings(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        model_triage=os.environ.get("MODEL_TRIAGE", "").strip() or DEFAULT_MODEL_TRIAGE,
        model_compiler=os.environ.get("MODEL_COMPILER", "").strip() or DEFAULT_MODEL_COMPILER,
        model_explainer=os.environ.get("MODEL_EXPLAINER", "").strip() or DEFAULT_MODEL_EXPLAINER,
    )


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimated call cost from the pinned price table; None for a model the
    table does not know (the audit line then records the tokens alone)."""
    for prefix, (in_price, out_price) in _PRICES_PER_MTOK.items():
        if model.startswith(prefix):
            return round(input_tokens * in_price / 1e6 + output_tokens * out_price / 1e6, 6)
    return None


def print_safe(text: str) -> None:
    """Print model-derived text without crashing a cp1252 Windows console.

    Our own literals are ASCII by rule; model output is instructed to be but
    is not guaranteed. Characters the console cannot encode are escaped
    rather than allowed to raise."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"))


def call_forced_tool(
    model: str,
    system: str,
    user_content: str,
    tool_name: str,
    tool_schema: dict,
    max_tokens: int,
) -> dict:
    """One model call with tool_choice forced to `tool_name`; returns the
    tool input as a dict.

    The forced tool is the strict-JSON channel: the model cannot answer in
    prose, only by filling the schema. Deterministic backstops in the caller
    still apply afterward -- schema conformance is necessary, not sufficient.

    Retries MAX_ATTEMPTS times on transient errors only (429 / 5xx /
    overloaded / transport); any other 4xx fails fast. Every outcome writes
    one audit line (attest/audit.py), success lines carrying token counts
    and estimated cost.
    """
    import anthropic  # lazy: runtime machines need no SDK (PLAN.md invariant 8)

    try:
        client = anthropic.Anthropic(max_retries=0)  # this module owns the retry policy
    except anthropic.AnthropicError as exc:
        raise ModelClientError(
            "no API credentials: set ANTHROPIC_API_KEY in .env (see .env.example). "
            "Only the authoring verbs need it; runtime verbs never do."
        ) from exc

    request = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        tools=[{"name": tool_name, "input_schema": tool_schema}],
        tool_choice={"type": "tool", "name": tool_name},
    )

    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.messages.create(**request)
        except anthropic.RateLimitError as exc:  # 429: transient
            last_exc = exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:  # 5xx / 529 overloaded: transient
                last_exc = exc
            else:  # auth and any other 4xx: fail fast, do not retry
                audit("model.call.failed", model=model, tool=tool_name,
                      attempt=attempt, status=exc.status_code, error=type(exc).__name__)
                raise ModelClientError(
                    f"model call refused by the API (HTTP {exc.status_code}, not retried): {exc.message}"
                ) from exc
        except anthropic.APIConnectionError as exc:  # transport: transient
            last_exc = exc
        else:
            block = next(
                (b for b in response.content if b.type == "tool_use" and b.name == tool_name),
                None,
            )
            if block is None:
                audit("model.call.failed", model=model, tool=tool_name,
                      attempt=attempt, error="no_forced_tool_call",
                      stop_reason=response.stop_reason)
                raise ModelClientError(
                    f"model returned no {tool_name!r} tool call "
                    f"(stop_reason={response.stop_reason!r})"
                )
            audit(
                "model.call",
                model=model,
                tool=tool_name,
                attempts=attempt,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                estimated_cost_usd=estimate_cost_usd(
                    model, response.usage.input_tokens, response.usage.output_tokens
                ),
                stop_reason=response.stop_reason,
            )
            return dict(block.input)

        audit("model.retry", model=model, tool=tool_name, attempt=attempt,
              error=type(last_exc).__name__)
        if attempt < MAX_ATTEMPTS:
            time.sleep(_BACKOFF_SECONDS[attempt - 1])

    audit("model.call.failed", model=model, tool=tool_name,
          attempts=MAX_ATTEMPTS, error=type(last_exc).__name__)
    raise ModelClientError(
        f"model call failed after {MAX_ATTEMPTS} attempts "
        f"(last error: {type(last_exc).__name__})"
    ) from last_exc
