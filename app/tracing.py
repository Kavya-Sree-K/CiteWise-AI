"""Optional Langfuse tracing. Everything here does nothing unless the Langfuse keys are set.

    $env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."
    $env:LANGFUSE_SECRET_KEY = "sk-lf-..."
    $env:LANGFUSE_HOST = "https://cloud.langfuse.com"     # or https://us.cloud.langfuse.com
"""
import logging
import os
from contextlib import ExitStack, contextmanager

logger = logging.getLogger("knowledge.tracing")


def enabled():
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


@contextmanager
def trace_run(user, conversation_id, trace_id):
    """Wrap one question in a Langfuse trace. Yields the callbacks to pass to the graph."""
    callbacks = []
    stack = ExitStack()
    if enabled():
        try:
            from langfuse import get_client, propagate_attributes
            from langfuse.langchain import CallbackHandler
            root = stack.enter_context(get_client().start_as_current_observation(
                as_type="span", name="ask"))
            stack.enter_context(propagate_attributes(
                user_id=user.username, trace_name="ask",
                session_id=f"conversation-{conversation_id}" if conversation_id else None,
                tags=["citewise"], metadata={"trace_id": trace_id}))
            callbacks = [CallbackHandler()]
        except Exception:
            logger.warning("Langfuse is configured but tracing could not start", exc_info=True)
    try:
        yield callbacks
    finally:
        try:
            stack.close()
        except Exception:
            logger.debug("Langfuse trace could not be closed", exc_info=True)


def record_generation(model, prompt, output, input_tokens, output_tokens):
    """Show one model call (model, text, tokens) inside the current trace."""
    if not enabled():
        return
    try:
        from langfuse import get_client
        with get_client().start_as_current_observation(
                as_type="generation", name="model-call", model=model, input=prompt,
                output=output, usage_details={"input": int(input_tokens or 0),
                                              "output": int(output_tokens or 0)}):
            pass
    except Exception:
        logger.debug("Langfuse generation skipped", exc_info=True)