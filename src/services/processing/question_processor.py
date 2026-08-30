"""Single application pipeline used by the CLI, benchmarks, and Telegram adapter."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from src.services.processing.approval_generator import ApprovalTokenGenerator
from src.services.processing.confidence_calculator import ConfidenceCalculator

if TYPE_CHECKING:
    from src.services.processing.hybrid_retriever import HybridRAGMatch

from src.core.config import settings
from src.services.processing.intent_router import IntentRouter
from src.services.processing.llm_improver import LLMImprover
from src.services.processing.processing_phases import (
    OperationPhase,
    ProcessingContext,
    ProcessingMode,
)


class Retriever(Protocol):
    """Minimal retrieval port so the pipeline can be tested without network access."""

    async def retrieve(self, query: str, top_k: int = 1) -> list[object]: ...

    async def close(self) -> None: ...


class AnswerImprover(Protocol):
    """Read-only answer synthesis port."""

    async def improve_answer(
        self, question: str, weak_answer: str, confidence: float, **kwargs: object
    ) -> tuple[str, float]: ...


@dataclass(frozen=True)
class ProcessingResult:
    """Stable result contract for all input adapters."""

    context: ProcessingContext
    confidence_level: str


class QuestionProcessor:
    """Routes a support question and performs only safe read-only work.

    Mode A creates a *plan* for the Telegram FSM; it deliberately never executes
    mutation tools. Mode B retrieves knowledge and may improve the answer through
    the configured LLM provider.
    """

    def __init__(
        self,
        router: IntentRouter | None = None,
        retriever: Retriever | None = None,
        improver: AnswerImprover | None = None,
        approval_generator: ApprovalTokenGenerator | None = None,
        dataset_path: str | Path = "docs/rag_dataset_train.jsonl",
    ) -> None:
        self.router = router or IntentRouter()
        if retriever is None:
            from src.services.processing.hybrid_retriever import HybridRetriever

            retriever = HybridRetriever(
                dataset_path=str(dataset_path),
                base_url=settings.llm_base_url,
                api_key=settings.llm_provider_key,
                embedding_model=settings.embedding_model,
                reranker_model=settings.reranker_model or "default",
                use_reranker=bool(settings.reranker_base_url),
            )
            if settings.reranker_base_url:
                retriever.reranker_service.base_url = settings.reranker_base_url
        self.retriever = retriever
        self.improver = improver or LLMImprover()
        self.approval_generator = approval_generator or ApprovalTokenGenerator()

    async def process(self, question: str) -> ProcessingResult:
        """Process a non-empty question and return an adapter-neutral result."""
        if not question or not question.strip():
            raise ValueError("question must not be empty")

        context = self.router.route(question.strip())
        context.add_phase_log(
            OperationPhase.INTENT_CLASSIFICATION,
            status="success",
            details={
                "mode": context.processing_mode.value,
                "confidence": context.confidence,
            },
        )
        if context.processing_mode == ProcessingMode.MODE_A_DETERMINISTIC:
            self._plan_deterministic_flow(context)
        else:
            await self._answer_investigation(context)
        return ProcessingResult(
            context=context,
            confidence_level=ConfidenceCalculator.get_confidence_level(
                context.confidence
            ),
        )

    def _plan_deterministic_flow(self, context: ProcessingContext) -> None:
        context.add_phase_log(
            OperationPhase.STATE_MACHINE_INIT,
            status="success",
            details={
                "flow": context.flow_type.value,
                "tools_count": len(context.expected_tools),
            },
        )
        if context.requires_staff_approval:
            context.approval_token = self.approval_generator.generate_benchmark_token(
                context.flow_type.value
            )
        context.add_phase_log(
            OperationPhase.TOOL_EXECUTION,
            status="skipped",
            details={"reason": "awaiting Telegram FSM and approved backend execution"},
        )
        context.add_phase_log(
            OperationPhase.HANDOFF,
            status="pending" if context.requires_staff_approval else "skipped",
        )
        context.final_answer = (
            "Запрос принят. Продолжим обработку в безопасном сценарии."
        )

    async def _answer_investigation(self, context: ProcessingContext) -> None:
        matches = await self.retriever.retrieve(context.question, top_k=1)
        if not matches:
            context.add_phase_log(OperationPhase.RAG_RETRIEVAL, status="not_found")
            answer, confidence = await self.improver.improve_answer(
                context.question, "В базе знаний нет подходящего ответа.", 0.0
            )
            context.final_answer, context.confidence = answer, confidence
            context.add_phase_log(OperationPhase.LLM_GENERATION, status="success")
            return
        match = matches[0]
        confidence = ConfidenceCalculator.calculate_hybrid_rag_confidence(
            match.rerank_score, len(match.answer)
        )
        context.final_answer, context.confidence = match.answer, confidence
        context.add_phase_log(
            OperationPhase.RAG_RETRIEVAL,
            status="success",
            details={"score": match.rerank_score},
        )
        if confidence < 0.65:
            answer, confidence = await self.improver.improve_answer(
                context.question,
                match.answer,
                confidence,
                always_improve=True,
                rag_context=f"retrieved question: {match.question}",
            )
            context.final_answer, context.confidence = answer, confidence
            context.add_phase_log(OperationPhase.LLM_GENERATION, status="success")

    async def close(self) -> None:
        """Release adapter resources when the application shuts down."""
        await self.retriever.close()
