from dataclasses import dataclass

import pytest

from src.services.processing.processing_phases import ProcessingMode
from src.services.processing.question_processor import QuestionProcessor


@dataclass
class Match:
    question: str = "Как настроить поиск?"
    answer: str = "Откройте настройки поиска."
    rerank_score: float = 0.9


class FakeRetriever:
    def __init__(self, matches):
        self.matches = matches
        self.queries = []
        self.closed = False

    async def retrieve(self, query, top_k=1):
        self.queries.append((query, top_k))
        return self.matches

    async def close(self):
        self.closed = True


class FakeImprover:
    def __init__(self):
        self.calls = []

    async def improve_answer(self, question, weak_answer, confidence, **kwargs):
        self.calls.append((question, weak_answer, confidence, kwargs))
        return "Уточнённый ответ.", 0.6


@pytest.mark.asyncio
async def test_deterministic_request_only_creates_safe_plan():
    retriever = FakeRetriever([])
    processor = QuestionProcessor(retriever=retriever, improver=FakeImprover())

    result = await processor.process("Хочу вернуть деньги")

    assert result.context.processing_mode is ProcessingMode.MODE_A_DETERMINISTIC
    assert result.context.executed_tools == []
    assert result.context.requires_staff_approval is True
    assert result.context.approval_token
    assert retriever.queries == []


@pytest.mark.asyncio
async def test_investigation_returns_retrieved_answer_without_llm_for_high_confidence():
    improver = FakeImprover()
    processor = QuestionProcessor(retriever=FakeRetriever([Match()]), improver=improver)

    result = await processor.process("Как настроить поиск?")

    assert result.context.processing_mode is ProcessingMode.MODE_B_INVESTIGATION
    assert result.context.final_answer == "Откройте настройки поиска."
    assert result.confidence_level == "high"
    assert improver.calls == []


@pytest.mark.asyncio
async def test_investigation_falls_back_to_llm_when_knowledge_is_empty():
    improver = FakeImprover()
    processor = QuestionProcessor(retriever=FakeRetriever([]), improver=improver)

    result = await processor.process("Неизвестный вопрос")

    assert result.context.final_answer == "Уточнённый ответ."
    assert result.context.confidence == 0.6
    assert len(improver.calls) == 1


@pytest.mark.asyncio
async def test_empty_question_is_rejected():
    processor = QuestionProcessor(retriever=FakeRetriever([]), improver=FakeImprover())
    with pytest.raises(ValueError, match="must not be empty"):
        await processor.process("   ")
