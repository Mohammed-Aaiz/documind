"""
Brain executor for DocuMind.

Runs a deterministic plan step-by-step, resolving inputs from the
ExecutionContext and storing outputs back into it.

The executor owns:
  • Step sequencing
  • Input resolution from context
  • Capability invocation through the registry
  • Output storage in context
  • Error recording

The executor does NOT own:
  • SQL, database access, file parsing, model loading
  • Retrieval, QA, embedding, or any service logic
  • Intent classification or planning
  • Evidence gating or outcome classification
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from brain.types import (
    Capability,
    ExecutionContext,
    ErrorRecord,
    ModelUnavailableError,
    Plan,
    PlanStep,
    QaResult,
    SourceRef,
)


# ---------------------------------------------------------------------------
# Capability adapter type
# ---------------------------------------------------------------------------

# An adapter is an async callable that receives keyword arguments resolved
# from the ExecutionContext and returns a result stored in context.
CapabilityAdapter = Callable[..., Awaitable[Any]]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class CapabilityRegistry:
    """Maps Capability enum values to callable adapters.

    Adapters bridge the Brain to real service implementations.
    During this phase, adapters that are not yet wired return explicit
    UNAVAILABLE markers rather than faking results.
    """

    def __init__(self) -> None:
        self._adapters: dict[Capability, CapabilityAdapter] = {}

    def register(self, capability: Capability, adapter: CapabilityAdapter) -> None:
        """Register an adapter for a capability."""
        self._adapters[capability] = adapter

    def get(self, capability: Capability) -> CapabilityAdapter | None:
        """Get the adapter for a capability, or None if not registered."""
        return self._adapters.get(capability)

    def is_available(self, capability: Capability) -> bool:
        """Check if a capability has a registered adapter."""
        return capability in self._adapters

    @property
    def available_capabilities(self) -> set[Capability]:
        """Return the set of all registered capabilities."""
        return set(self._adapters.keys())


# ---------------------------------------------------------------------------
# Built-in adapters for unavailable capabilities
# ---------------------------------------------------------------------------

async def _unavailable_adapter(**kwargs: Any) -> None:
    """Placeholder for capabilities not yet implemented."""
    return None


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class Executor:
    """Executes a Brain plan by running each step sequentially.

    For each step:
      1. Resolve inputs from ExecutionContext
      2. Look up the capability adapter in the registry
      3. Invoke the adapter with resolved inputs
      4. Store the result in the context at the step's output_key
      5. Record any errors

    If a capability is unavailable, execution stops and the context
    is marked with an error.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    async def run(self, ctx: ExecutionContext, plan: Plan) -> ExecutionContext:
        """Execute all steps in the plan sequentially.

        Returns the updated ExecutionContext.
        """
        for step in plan.steps:
            await self._run_step(ctx, step)

        return ctx

    async def _run_step(self, ctx: ExecutionContext, step: PlanStep) -> None:
        """Execute a single plan step."""
        adapter = self._registry.get(step.capability)

        if adapter is None:
            ctx.errors.append(
                ErrorRecord(
                    category="capability_unavailable",
                    message=f"Capability '{step.capability.value}' is not registered.",
                    service="brain",
                )
            )
            return

        # Resolve inputs from context
        inputs = self._resolve_inputs(ctx, step)

        # Invoke the adapter
        try:
            start = time.monotonic()
            result = await adapter(**inputs)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Store result in context
            _set_nested(ctx, step.output_key, result)

            # Track timing
            if step.capability == Capability.DOCUMENT_RETRIEVAL:
                ctx.timing.retrieval_ms = elapsed_ms
            elif step.capability == Capability.QA_ANSWER:
                ctx.timing.qa_ms = elapsed_ms

        except ModelUnavailableError as exc:
            # A missing model is a capability outage, not a bug: classify it so
            # the gate can return UNAVAILABLE and the API can answer honestly.
            ctx.errors.append(
                ErrorRecord(
                    category="model_unavailable",
                    message=f"Capability '{step.capability.value}' requires a model that is unavailable.",
                    service=step.capability.value,
                )
            )

        except Exception as exc:
            ctx.errors.append(
                ErrorRecord(
                    category="service_failure",
                    message=f"Capability '{step.capability.value}' failed: {type(exc).__name__}",
                    service=step.capability.value,
                )
            )

    def _resolve_inputs(
        self, ctx: ExecutionContext, step: PlanStep
    ) -> dict[str, Any]:
        """Resolve step input keys from the ExecutionContext.

        Uses dotted paths to locate values (e.g. 'parsed_request.cleaned_text')
        but passes the leaf name as the keyword argument to the adapter
        (e.g. 'cleaned_text').
        """
        inputs: dict[str, Any] = {}
        for key in step.input_keys:
            leaf_name = key.rsplit(".", 1)[-1]  # 'parsed_request.cleaned_text' -> 'cleaned_text'
            inputs[leaf_name] = _get_nested(ctx, key)
        return inputs


# ---------------------------------------------------------------------------
# Context access helpers
# ---------------------------------------------------------------------------

def _get_nested(ctx: ExecutionContext, key: str) -> Any:
    """Get a value from the ExecutionContext by key.

    Supports dotted paths like 'parsed_request.cleaned_text'.
    """
    obj: Any = ctx
    for part in key.split("."):
        if hasattr(obj, part):
            obj = getattr(obj, part)
        elif isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return None
    return obj


def _set_nested(ctx: ExecutionContext, key: str, value: Any) -> None:
    """Set a value in the ExecutionContext by key.

    Supports dotted paths and direct attribute setting.
    Uses setattr directly — Python allows setting arbitrary attributes
    on dataclass instances.
    """
    parts = key.split(".")
    obj: Any = ctx
    for part in parts[:-1]:
        if hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return
    setattr(obj, parts[-1], value)
