"""Confidence calculator - determines confidence in answers."""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ConfidenceSource(str, Enum):
    """Source of answer confidence."""

    INSTRUCTION_FLOW = "instruction_flow"
    RAG_HISTORY = "rag_history"
    LLM_FALLBACK = "llm_fallback"
    NO_MATCH = "no_match"


class ConfidenceCalculator:
    """Calculates confidence scores for different answer sources."""

    # Base confidence scores for different sources
    BASE_SCORES = {
        ConfidenceSource.INSTRUCTION_FLOW: 0.9,
        ConfidenceSource.RAG_HISTORY: 0.7,
        ConfidenceSource.LLM_FALLBACK: 0.5,
        ConfidenceSource.NO_MATCH: 0.0,
    }

    @staticmethod
    def calculate_flow_confidence(flow_match_score: float) -> float:
        """Calculate confidence for instruction flow match.

        Args:
            flow_match_score: Flow matching score (0-1).

        Returns:
            Confidence score (0-1).
        """
        # Flow match score directly impacts confidence
        # Minimum 0.7 for flow matches (score >= 0.3)
        base = ConfidenceCalculator.BASE_SCORES[ConfidenceSource.INSTRUCTION_FLOW]
        confidence = base * (0.8 + flow_match_score * 0.2)
        return round(min(confidence, 1.0), 2)

    @staticmethod
    def calculate_rag_confidence(
        relevance_score: float, answer_length: int = 100
    ) -> float:
        """Calculate confidence for RAG-based answer.

        Args:
            relevance_score: BM25 relevance score.
            answer_length: Length of the answer.

        Returns:
            Confidence score (0-1).
        """
        base = ConfidenceCalculator.BASE_SCORES[ConfidenceSource.RAG_HISTORY]

        # BM25 scores typically range from 0 to 10+
        # Normalize to 0-1 for confidence
        normalized_relevance = min(relevance_score / 10.0, 1.0)

        # Length bonus: longer answers are usually more complete
        length_bonus = min(answer_length / 500.0, 0.2)

        confidence = base * (0.8 + normalized_relevance * 0.15 + length_bonus)

        return round(min(confidence, 1.0), 2)

    @staticmethod
    def calculate_hybrid_rag_confidence(
        rerank_score: float, answer_length: int = 100
    ) -> float:
        """Calculate confidence for hybrid RAG-based answer using reranker score.

        Args:
            rerank_score: Reranker relevance score (0-1 or higher).
            answer_length: Length of the answer.

        Returns:
            Confidence score (0-1).
        """
        base = ConfidenceCalculator.BASE_SCORES[ConfidenceSource.RAG_HISTORY]

        # Reranker scores are typically in 0-1 range, but can be higher
        # Normalize to 0-1 for confidence
        normalized_rerank = min(rerank_score, 1.0)

        # Length bonus: longer answers are usually more complete
        length_bonus = min(answer_length / 500.0, 0.2)

        # Hybrid confidence: higher base with reranker score being the primary signal
        confidence = base * (0.75 + normalized_rerank * 0.20) + length_bonus

        return round(min(confidence, 1.0), 2)

    @staticmethod
    def calculate_llm_confidence(
        uncertainty_indicators: int = 0, answer_length: int = 100
    ) -> float:
        """Calculate confidence for LLM-generated answer.

        Args:
            uncertainty_indicators: Number of uncertainty phrases found.
            answer_length: Length of the answer.

        Returns:
            Confidence score (0-1).
        """
        base = ConfidenceCalculator.BASE_SCORES[ConfidenceSource.LLM_FALLBACK]

        # Uncertainty penalty
        uncertainty_penalty = min(uncertainty_indicators * 0.1, 0.3)

        # Length bonus
        length_bonus = min(answer_length / 500.0, 0.15)

        confidence = base * (1.0 - uncertainty_penalty) + length_bonus

        return round(min(confidence, 1.0), 2)

    @staticmethod
    def detect_uncertainty_phrases(text: str) -> int:
        """Detect uncertainty phrases in LLM response.

        Args:
            text: LLM response text.

        Returns:
            Count of uncertainty indicators.
        """
        uncertainty_phrases = [
            "возможно",
            "может быть",
            "вероятно",
            "не уверен",
            "затрудняюсь",
            "сложно сказать",
            "probably",
            "maybe",
            "might",
            "could",
            "perhaps",
        ]

        count = 0
        text_lower = text.lower()

        for phrase in uncertainty_phrases:
            count += text_lower.count(phrase)

        return count

    @staticmethod
    def get_confidence_level(score: float) -> str:
        """Get human-readable confidence level.

        Args:
            score: Confidence score (0-1).

        Returns:
            Confidence level string.
        """
        if score >= 0.85:
            return "very_high"
        elif score >= 0.7:
            return "high"
        elif score >= 0.5:
            return "medium"
        elif score >= 0.3:
            return "low"
        else:
            return "very_low"
