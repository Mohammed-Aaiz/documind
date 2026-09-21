"""
DocuMind Brain — orchestration layer.

The Brain decides *what* to do.  Services execute.

Brain.process(context) orchestrates:
  1. Classify intent
  2. Build plan
  3. Execute plan steps
  4. Apply evidence gate
  5. Assemble response

Usage::

    from brain import Brain
    from brain.types import ExecutionContext

    ctx = ExecutionContext(user_id="...", raw_question="When was Darwin born?")
    brain = Brain(registry)
    result = await brain.process(ctx)
    # result.response is a BrainResponse
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable, Any

from brain.classifier import classify
from brain.planner import build_plan
from brain.executor import Executor, CapabilityRegistry
from brain.gate import evaluate
from brain.response import assemble
from brain.types import (
    ExecutionContext,
    ErrorRecord,
    PlanStep,
)
from outcomes import Outcome


class Brain:
    """DocuMind Brain — thin orchestration layer.

    Receives an ExecutionContext, classifies the intent, builds a plan,
    executes it through registered capabilities, applies the evidence
    gate, and assembles the response.

    The Brain does NOT contain service logic.  It delegates to adapters
    registered in the CapabilityRegistry.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._executor = Executor(registry)
        self._registry = registry

    async def process(self, ctx: ExecutionContext) -> ExecutionContext:
        """Process a user request through the Brain pipeline.

        Returns the updated ExecutionContext with response set.
        """
        start = time.monotonic()

        # 1. Classify intent
        parsed = classify(ctx.raw_question)
        ctx.parsed_request = parsed

        # 2. Build plan
        plan = build_plan(parsed)
        ctx.plan = plan

        # 3. Handle unsupported / empty requests immediately
        if len(plan.steps) == 0:
            ctx.outcome = Outcome.FAILED
            ctx.errors.append(
                ErrorRecord(
                    category="invalid_request",
                    message="Request cannot be handled by any available capability.",
                    service="brain",
                )
            )
            ctx.response = assemble(ctx)
            ctx.timing.total_ms = int((time.monotonic() - start) * 1000)
            return ctx

        # 4. Check capability availability before execution
        unavailable = [
            cap for cap in plan.required_capabilities
            if not self._registry.is_available(cap)
        ]
        if unavailable:
            for cap in unavailable:
                ctx.errors.append(
                    ErrorRecord(
                        category="capability_unavailable",
                        message=f"Capability '{cap.value}' is not available.",
                        service="brain",
                    )
                )
            ctx.outcome = Outcome.UNAVAILABLE
            ctx.response = assemble(ctx)
            ctx.timing.total_ms = int((time.monotonic() - start) * 1000)
            return ctx

        # 4. Execute plan
        ctx = await self._executor.run(ctx, plan)

        # 5. Populate evidence from execution results
        self._collect_evidence(ctx)

        # 6. Apply evidence gate
        ctx.outcome = evaluate(ctx)

        # 7. Assemble response
        ctx.response = assemble(ctx)

        # 8. Record timing
        ctx.timing.total_ms = int((time.monotonic() - start) * 1000)

        return ctx

    def _collect_evidence(self, ctx: ExecutionContext) -> None:
        """Populate the EvidenceBundle from execution results stored in context.

        Phase 3D: when the context builder reports which chunks it actually
        included, evidence is restricted to that set.  Previously every
        retrieved chunk was reported as evidence even though the QA model only
        saw the first part of the context, so source attribution overstated
        what supported the answer.  Chunks that were retrieved but did not fit
        the QA window are recorded in ``grounding_signals`` so the omission is
        visible rather than silent.  When no such report exists (e.g. a plain
        string context), the previous behaviour is preserved.

        Invariant (Phase 3D correction): reported evidence must NEVER contain a
        chunk that was not supplied to the QA model.  When *no* retrieved chunk
        reaches QA the reported evidence is the empty set — it is not silently
        widened back to the retrieved set.  An empty evidence set then drives
        the gate to ``INSUFFICIENT_EVIDENCE``, so the system abstains honestly
        instead of attributing a vacuous answer to unevidenced sources.
        """
        evidence = ctx.evidence

        # Collect retrieval sources — executor stores results via setattr,
        # so we check with hasattr to distinguish "not set" from "set to None".
        try:
            sources = ctx.retrieval_sources
            if sources is not None and isinstance(sources, list):
                evidence.sources = sources
                evidence.retrieval_scores = [
                    s.score for s in sources if hasattr(s, "score")
                ]
        except AttributeError:
            pass

        # Restrict reported evidence to what the context actually contains.
        try:
            context_obj = ctx.context
        except AttributeError:
            context_obj = None

        included_ids = getattr(context_obj, "included_ids", None)
        if included_ids is not None and evidence.sources:
            included = set(included_ids)
            kept = [s for s in evidence.sources if s.chunk_id in included]
            omitted = [s for s in evidence.sources if s.chunk_id not in included]

            # Strict restriction: `kept` may legitimately be empty.  Reporting
            # the retrieved set here would attribute an answer to chunks the QA
            # model never received, so the empty set is kept and the gate is
            # left to decide honestly.
            evidence.sources = kept
            evidence.retrieval_scores = [s.score for s in kept]
            evidence.grounding_signals["omitted_source_ids"] = [
                s.chunk_id for s in omitted
            ]
            evidence.grounding_signals["retrieved_source_count"] = len(kept) + len(
                omitted
            )
            evidence.grounding_signals["context_budget_tokens"] = getattr(
                context_obj, "budget_tokens", 0
            )
            evidence.grounding_signals["context_used_tokens"] = getattr(
                context_obj, "used_tokens", 0
            )
            evidence.grounding_signals["context_truncated_source_ids"] = list(
                getattr(context_obj, "truncated_ids", ())
            )

        # Collect QA result
        try:
            qa_result = ctx.qa_result
            if qa_result is not None:
                evidence.qa_result = qa_result

                # Compute factual grounding
                context_str = context_obj

                if (
                    context_str
                    and isinstance(context_str, str)
                    and qa_result.answer.strip()
                ):
                    evidence.factual_grounded = (
                        qa_result.answer.strip().lower() in context_str.lower()
                    )
                    evidence.grounding_signals["answer_found_in_context"] = (
                        evidence.factual_grounded
                    )
        except AttributeError:
            pass
