"""RAG-based LLM Investigation Service for Mode B (General Questions)."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.core.config import settings
from src.services.llm import get_llm_service

logger = logging.getLogger(__name__)


class QueryClassification(str, Enum):
    """Query classification for access control."""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    REQUIRES_HANDOFF = "requires_handoff"


@dataclass
class KnowledgeBaseMeta:
    """Knowledge base metadata with versioning."""

    kb_id: str
    owner: str
    version: str
    effective_date: datetime
    review_date: datetime
    status: str = "active"
    content_hash: str = ""

    def is_valid(self) -> bool:
        """Check if KB version is currently valid.

        Returns:
            bool: True if KB is within valid date range and active.
        """
        now = datetime.utcnow()
        return (
            self.status == "active"
            and self.effective_date <= now
            and self.review_date >= now
        )


@dataclass
class KnowledgeBaseEntry:
    """Single knowledge base entry."""

    entry_id: str
    category: str
    title: str
    content: str
    access_level: str = "public"  # public or authenticated
    tags: list[str] = field(default_factory=list)
    confidence_score: float = 1.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RetrievalResult:
    """Result from KB retrieval."""

    entries: list[KnowledgeBaseEntry]
    total_score: float
    classification: QueryClassification
    metadata: dict[str, Any] = field(default_factory=dict)


class QueryClassifier:
    """Classify user queries for appropriate KB access and response policy."""

    def __init__(self) -> None:
        """Initialize query classifier."""
        self.public_keywords = {
            "faq",
            "help",
            "how to",
            "what is",
            "general",
            "info",
            "information",
            "support",
        }
        self.auth_required_keywords = {
            "account",
            "subscription",
            "payment",
            "billing",
            "refund",
            "order",
            "personal",
            "my",
            "status",
        }
        self.handoff_keywords = {
            "human",
            "operator",
            "manager",
            "support team",
            "chargeback",
            "legal",
            "lawsuit",
            "complaint",
            "escalate",
        }

    def classify(self, query: str) -> QueryClassification:
        """Classify query based on keywords and content.

        Args:
            query: User query string.

        Returns:
            QueryClassification: Classification level.
        """
        query_lower = query.lower()

        # Check for handoff triggers first
        if any(kw in query_lower for kw in self.handoff_keywords):
            return QueryClassification.REQUIRES_HANDOFF

        # Check for authenticated access requirement
        if any(kw in query_lower for kw in self.auth_required_keywords):
            return QueryClassification.AUTHENTICATED

        # Default to public
        return QueryClassification.PUBLIC


class RAGRetriever:
    """Retrieve relevant information from curated knowledge base.

    This retriever strictly filters KB versions to prevent stale/draft content.
    """

    def __init__(self) -> None:
        """Initialize RAG retriever."""
        self.llm_service = get_llm_service()
        self.max_retrieval_count = settings.rag_max_retrieval_count
        self.confidence_threshold = settings.rag_confidence_threshold
        # Simulated KB entries (in production: fetch from KB service)
        self._kb_entries: dict[str, list[KnowledgeBaseEntry]] = {}
        self._kb_meta: dict[str, KnowledgeBaseMeta] = {}

    async def retrieve(
        self,
        query: str,
        classification: QueryClassification,
        user_id: str | None = None,
    ) -> RetrievalResult:
        """Retrieve relevant KB entries for query.

        Args:
            query: User query.
            classification: Query classification level.
            user_id: Optional user ID for authenticated queries.

        Returns:
            RetrievalResult: Retrieved entries and metadata.
        """
        logger.info(
            f"Retrieving KB entries for query: {query}, "
            f"classification: {classification}"
        )

        # Filter KB by validity (effective_date, review_date, status)
        valid_entries = await self._get_valid_kb_entries(classification)

        if not valid_entries:
            logger.warning(
                "No valid KB entries found for classification: "
                f"{classification}"
            )
            return RetrievalResult(
                entries=[],
                total_score=0.0,
                classification=classification,
                metadata={"reason": "no_valid_kb_entries"},
            )

        # Score entries based on relevance (simple keyword matching)
        scored_entries = self._score_entries(query, valid_entries)

        # Sort by score and limit
        top_entries = sorted(
            scored_entries, key=lambda x: x.confidence_score, reverse=True
        )[: self.max_retrieval_count]

        # Filter by confidence threshold
        filtered_entries = [
            e for e in top_entries
            if e.confidence_score >= self.confidence_threshold
        ]

        total_score = (
            sum(e.confidence_score for e in filtered_entries)
            / len(filtered_entries)
            if filtered_entries
            else 0.0
        )

        logger.info(
            f"Retrieved {len(filtered_entries)} entries with "
            f"avg score: {total_score:.2f}"
        )

        return RetrievalResult(
            entries=filtered_entries,
            total_score=total_score,
            classification=classification,
            metadata={
                "total_candidates": len(valid_entries),
                "filtered_count": len(filtered_entries),
            },
        )

    async def _get_valid_kb_entries(
        self, classification: QueryClassification
    ) -> list[KnowledgeBaseEntry]:
        """Get KB entries that are currently valid and match classification.

        Filters by:
        - KB version status (active only)
        - Effective date <= now
        - Review date >= now
        - Access level matches classification

        Args:
            classification: Query classification.

        Returns:
            list[KnowledgeBaseEntry]: Filtered entries.
        """
        valid_entries = []

        for kb_id, entries in self._kb_entries.items():
            # Check KB metadata validity
            if kb_id not in self._kb_meta:
                logger.warning(f"No metadata for KB: {kb_id}")
                continue

            meta = self._kb_meta[kb_id]
            if not meta.is_valid():
                logger.debug(
                    f"KB {kb_id} is not valid "
                    f"(status={meta.status}, "
                    f"effective={meta.effective_date}, "
                    f"review={meta.review_date})"
                )
                continue

            # Filter entries by access level
            for entry in entries:
                if classification == QueryClassification.PUBLIC:
                    if entry.access_level == "public":
                        valid_entries.append(entry)
                elif classification == QueryClassification.AUTHENTICATED:
                    if entry.access_level in ("public", "authenticated"):
                        valid_entries.append(entry)

        return valid_entries

    def _score_entries(
        self, query: str, entries: list[KnowledgeBaseEntry]
    ) -> list[KnowledgeBaseEntry]:
        """Score entries based on query relevance (keyword matching).

        Args:
            query: User query.
            entries: Candidate KB entries.

        Returns:
            list[KnowledgeBaseEntry]: Scored entries.
        """
        query_words = set(query.lower().split())
        scored = []

        for entry in entries:
            # Score based on tag matching and content matching
            tag_matches = sum(1 for tag in entry.tags if tag in query_words)
            content_words = set(entry.content.lower().split())
            content_matches = len(query_words & content_words)

            # Calculate confidence
            max_possible = max(
                len(entry.tags), len(entry.content.lower().split())
            )
            if max_possible == 0:
                confidence = 0.5
            else:
                confidence = (tag_matches + content_matches) / (
                    max_possible * 2
                )

            # Clamp and apply base confidence
            final_confidence = min(
                confidence * entry.confidence_score, 1.0
            )
            entry.confidence_score = final_confidence
            scored.append(entry)

        return scored


class InvestigationService:
    """Main RAG investigation orchestrator for Mode B questions."""

    def __init__(self) -> None:
        """Initialize investigation service."""
        self.classifier = QueryClassifier()
        self.retriever = RAGRetriever()
        self.llm_service = get_llm_service()
        self.confidence_threshold = settings.rag_confidence_threshold

    async def investigate(
        self,
        query: str,
        user_id: str | None = None,
        conversation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Investigate user question using RAG + LLM.

        Args:
            query: User question.
            user_id: Optional user ID for context.
            conversation_context: Previous conversation context.

        Returns:
            dict with keys:
                - answer: Generated response
                - confidence: Confidence score
                - classification: Query classification
                - sources: Retrieved KB entries
                - should_escalate: Whether to trigger handoff
        """
        logger.info(
            f"Starting investigation for query: {query[:100]}... "
            f"(user_id={user_id})"
        )

        # Step 1: Classify query
        classification = self.classifier.classify(query)
        logger.debug(f"Query classified as: {classification}")

        if classification == QueryClassification.REQUIRES_HANDOFF:
            logger.info("Query requires handoff based on classification")
            return {
                "answer": None,
                "confidence": 0.0,
                "classification": classification,
                "sources": [],
                "should_escalate": True,
                "reason": "explicit_handoff_classification",
            }

        # Step 2: Retrieve from KB
        retrieval_result = await self.retriever.retrieve(
            query, classification, user_id
        )

        if not retrieval_result.entries:
            logger.warning(
                "No KB entries retrieved for query, "
                "triggering escalation"
            )
            return {
                "answer": None,
                "confidence": 0.0,
                "classification": classification,
                "sources": [],
                "should_escalate": True,
                "reason": "no_kb_entries",
            }

        # Step 3: Generate LLM response using retrieved context
        context_text = self._format_context(retrieval_result)
        llm_prompt = self._build_llm_prompt(query, context_text)

        try:
            llm_response = await self.llm_service.generate_response(
                llm_prompt, {"query": query, "context": context_text}
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "answer": None,
                "confidence": 0.0,
                "classification": classification,
                "sources": retrieval_result.entries,
                "should_escalate": True,
                "reason": "llm_generation_failed",
            }

        # Step 4: Validate response
        if not llm_response or len(llm_response.strip()) == 0:
            logger.warning("LLM returned empty response")
            return {
                "answer": None,
                "confidence": 0.0,
                "classification": classification,
                "sources": retrieval_result.entries,
                "should_escalate": True,
                "reason": "empty_llm_response",
            }

        # Success case
        result = {
            "answer": llm_response,
            "confidence": retrieval_result.total_score,
            "classification": classification,
            "sources": [
                {
                    "title": e.title,
                    "category": e.category,
                    "snippet": e.content[:200],
                }
                for e in retrieval_result.entries
            ],
            "should_escalate": (
                retrieval_result.total_score < self.confidence_threshold
            ),
            "reason": "success"
            if retrieval_result.total_score >= self.confidence_threshold
            else "low_confidence",
        }

        logger.info(
            f"Investigation complete: confidence={result['confidence']:.2f}, "
            f"escalate={result['should_escalate']}"
        )

        return result

    def _format_context(self, result: RetrievalResult) -> str:
        """Format retrieved KB entries into context string.

        Args:
            result: Retrieval result.

        Returns:
            str: Formatted context.
        """
        if not result.entries:
            return "No relevant knowledge base entries found."

        context_parts = []
        for entry in result.entries:
            context_parts.append(
                f"[{entry.category}] {entry.title}\n{entry.content}\n"
            )

        return "\n".join(context_parts)

    def _build_llm_prompt(self, query: str, context: str) -> str:
        """Build LLM prompt with query and context.

        Args:
            query: User question.
            context: Knowledge base context.

        Returns:
            str: LLM prompt.
        """
        return (
            f"You are a helpful QuickOffer support assistant. "
            f"Using the following knowledge base entries, "
            f"answer the user's question clearly and concisely. "
            f"If you cannot find relevant information, say so. "
            f"Do not make up information.\n\n"
            f"Knowledge Base:\n{context}\n\n"
            f"User Question: {query}\n\n"
            f"Answer:"
        )

    def register_kb_version(
        self,
        kb_id: str,
        owner: str,
        version: str,
        effective_date: datetime,
        review_date: datetime,
        entries: list[KnowledgeBaseEntry],
    ) -> None:
        """Register a knowledge base version.

        Args:
            kb_id: Knowledge base identifier.
            owner: KB owner/maintainer.
            version: Version identifier.
            effective_date: Date when KB becomes active.
            review_date: Date when KB review expires.
            entries: KB entries.
        """
        from hashlib import sha256

        content_str = "".join(e.content for e in entries)
        content_hash = sha256(content_str.encode()).hexdigest()

        meta = KnowledgeBaseMeta(
            kb_id=kb_id,
            owner=owner,
            version=version,
            effective_date=effective_date,
            review_date=review_date,
            content_hash=content_hash,
        )

        self._kb_meta[kb_id] = meta
        self._kb_entries[kb_id] = entries

        logger.info(
            f"Registered KB version: {kb_id} v{version} "
            f"(owner={owner}, hash={content_hash[:8]})"
        )
