"""Token and cost tracking for every model call made while answering one question.

Usage:
    usage.start()                     # at the beginning of a question
    usage.record("ollama", model, input_tokens, output_tokens)   # after each model call
    usage.snapshot()                  # at the end: {"calls", "input_tokens", "output_tokens", "cost_usd"}

Prices are USD per 1 million tokens and come from environment variables, so you can
update them without touching code (check your provider's current price list):

    CLAUDE_PRICE_IN=3.00      CLAUDE_PRICE_OUT=15.00
    OLLAMA_PRICE_IN=0         OLLAMA_PRICE_OUT=0     # local model: free (set a number to show a notional cost)
"""
import contextvars
import os

_current = contextvars.ContextVar("llm_usage", default=None)


def price(provider):
    """(input price, output price) in USD per 1M tokens."""
    if provider == "claude":
        return (float(os.getenv("CLAUDE_PRICE_IN", "3.00")),
                float(os.getenv("CLAUDE_PRICE_OUT", "15.00")))
    return (float(os.getenv("OLLAMA_PRICE_IN", "0")),
            float(os.getenv("OLLAMA_PRICE_OUT", "0")))


def estimate_tokens(text):
    """Rough count (about 4 characters per token) for providers that report nothing."""
    return max(1, len(text or "") // 4)


def cost_of(provider, input_tokens, output_tokens):
    p_in, p_out = price(provider)
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000


def start():
    state = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    _current.set(state)
    return state


def record(provider, model, input_tokens, output_tokens):
    state = _current.get()
    if state is None:               # called outside a question (e.g. in a script)
        return
    state["calls"] += 1
    state["input_tokens"] += int(input_tokens or 0)
    state["output_tokens"] += int(output_tokens or 0)
    state["cost_usd"] += cost_of(provider, input_tokens or 0, output_tokens or 0)


def snapshot():
    state = _current.get() or {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    return {**state, "cost_usd": round(state["cost_usd"], 6)}