"""Main benchmark script - evaluates QA system on 15 test questions."""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))


from src.benchmarking.approval_generator import ApprovalTokenGenerator
from src.benchmarking.confidence_calculator import (
    ConfidenceCalculator,
    ConfidenceSource,
)
from src.benchmarking.hybrid_retriever import HybridRetriever
from src.benchmarking.llm_flow_matcher import LLMFlowMatcher
from src.benchmarking.llm_improver import LLMImprover

# Setup logging. Use mode="w" so each run starts from a clean log file and
# results from separate benchmark runs are never interleaved.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("benchmark.log", mode="w", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStage:
    """Single processing stage in question handling."""

    stage_name: str
    result: str  # matched, skipped, failed, found, not_found
    details: str
    score: Optional[float] = None
    duration_ms: Optional[float] = None


@dataclass
class BenchmarkResult:
    """Result of processing a single benchmark question."""

    question_id: str
    question: str
    flow_matched: Optional[str] = None
    flow_match_score: Optional[float] = None
    source: Optional[str] = None
    answer: Optional[str] = None
    confidence: float = 0.0
    confidence_level: str = "very_low"
    approval_token: Optional[str] = None
    processing_stages: list[ProcessingStage] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    needs_staff_approval: bool = False
    escalation_type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "question_id": self.question_id,
            "question": self.question,
            "flow_matched": self.flow_matched,
            "flow_match_score": self.flow_match_score,
            "source": self.source,
            # Store the full answer; truncating here previously cut answers
            # mid-word in the saved report.
            "answer": self.answer,
            "confidence": self.confidence,

            "confidence_level": self.confidence_level,
            "approval_token": self.approval_token,
            "processing_stages": [asdict(stage) for stage in self.processing_stages],
            "timestamp": self.timestamp,
        }


class Benchmark:
    """Main benchmark class."""

    def __init__(
        self,
        test_dataset_path: str = "docs/rag_dataset_test.jsonl",
        train_dataset_path: str = "docs/rag_dataset_train.jsonl",
    ):
        """Initialize benchmark.

        Args:
            test_dataset_path: Path to test questions dataset.
            train_dataset_path: Path to RAG training dataset.
        """
        logger.info("=" * 80)
        logger.info("QUICKOFFER SUPPORT BOT - BENCHMARK INITIALIZATION")
        logger.info("=" * 80)

        self.test_dataset_path = test_dataset_path
        self.train_dataset_path = train_dataset_path
        self.flow_matcher = LLMFlowMatcher()

        # Initialize hybrid retriever with environment variables
        import os

        llm_base_url = os.getenv(
            "LLM_BASE_URL", "https://litellm.ai.nestle.ru/v1"
        )
        llm_api_key = os.getenv("LLM_PROVIDER_KEY", "")

        self.hybrid_retriever = HybridRetriever(
            dataset_path=train_dataset_path,
            base_url=llm_base_url,
            api_key=llm_api_key,
            use_reranker=True,
        )

        self.llm_improver = LLMImprover()
        self.approval_generator = ApprovalTokenGenerator()
        self.results: list[BenchmarkResult] = []

        logger.info("[OK] Benchmark components initialized successfully")

    def _extract_test_questions(self, num_questions: int = 10) -> list[dict[str, str]]:
        """Extract test questions from RAG dataset.

        Args:
            num_questions: Number of questions to extract.

        Returns:
            List of test question dictionaries.
        """
        logger.info(f"\n{'=' * 80}")
        logger.info(f"STEP 1: EXTRACTING {num_questions} TEST QUESTIONS")
        logger.info(f"{'=' * 80}")

        questions = []
        extracted_count = 0

        try:
            with open(self.test_dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    if extracted_count >= num_questions:
                        break

                    try:
                        qa = json.loads(line)

                        # Each line is a direct QA pair from llm_qa_pairs
                        if "question" in qa and "answer" in qa:
                            question_obj = {
                                "id": f"q_{extracted_count + 1}",
                                "text": qa["question"],
                                "expected_answer": qa["answer"],
                            }
                            questions.append(question_obj)
                            extracted_count += 1

                            logger.info(
                                f"  [{extracted_count}] Extracted: "
                                f"{qa['question'][:60]}..."
                            )

                    except (json.JSONDecodeError, KeyError):
                        continue

        except Exception as e:
            logger.error(f"Error extracting test questions: {e}")

        logger.info(f"[OK] Successfully extracted {len(questions)} test questions")
        return questions

    def process_question(self, question: dict[str, str]) -> BenchmarkResult:
        """Process a single question through the Q&A pipeline.

        Args:
            question: Question dictionary with id, text, expected_answer.

        Returns:
            BenchmarkResult with processing details.
        """
        result = BenchmarkResult(
            question_id=question["id"],
            question=question["text"],
        )

        logger.info(f"\n{'-' * 80}")
        logger.info(f"PROCESSING: {question['id']} - {question['text'][:70]}")
        logger.info(f"{'-' * 80}")

        # STAGE 1: Flow Matching
        logger.info("\n[STAGE 1] Matching with instruction flows...")
        flow_match = self.flow_matcher.match(question["text"])

        if flow_match:
            logger.info(
                f"  [YES] FLOW MATCHED: {flow_match.flow_name} "
                f"(score: {flow_match.match_score})"
            )
            logger.info(f"    Description: {flow_match.flow_description}")
            logger.info(f"    Keywords: {flow_match.matched_keywords}")

            # Handle escalations (requires staff approval)
            if flow_match.needs_staff_approval:
                logger.warning(
                    f"  [ESCALATION] Critical issue detected - requires staff approval"
                )
                logger.warning(f"    Type: {flow_match.escalation_type}")

                result.flow_matched = flow_match.flow_name
                result.flow_match_score = flow_match.match_score
                result.source = "escalation_requires_approval"
                result.answer = (
                    "This case requires staff review and approval. "
                    "Our team will contact you shortly."
                )
                result.needs_staff_approval = True
                result.escalation_type = flow_match.escalation_type
                result.confidence = 0.3  # Low confidence for escalations
                result.confidence_level = "low"

                result.processing_stages.append(
                    ProcessingStage(
                        stage_name="escalation_detection",
                        result="escalation_flagged",
                        details=f"Escalation: {flow_match.escalation_type}",
                        score=1.0,
                    )
                )
            else:
                result.flow_matched = flow_match.flow_name
                result.flow_match_score = flow_match.match_score
                result.source = "instruction_flow"
                result.answer = flow_match.flow_description

                # Generate approval token
                approval_token = self.approval_generator.generate_benchmark_token(
                    flow_match.flow_name
                )
                result.approval_token = approval_token
                logger.info(f"    Token: {approval_token[:32]}...")

                # Calculate confidence
                confidence = ConfidenceCalculator.calculate_flow_confidence(
                    flow_match.match_score
                )
                result.confidence = confidence
                result.confidence_level = ConfidenceCalculator.get_confidence_level(
                    confidence
                )

                result.processing_stages.append(
                    ProcessingStage(
                        stage_name="flow_matching",
                        result="matched",
                        details=f"Matched flow: {flow_match.flow_name}",
                        score=flow_match.match_score,
                    )
                )

        else:
            logger.info("  [NO] No flow matched, proceeding to RAG retrieval...")

            result.processing_stages.append(
                ProcessingStage(
                    stage_name="flow_matching",
                    result="not_matched",
                    details="No matching flow found",
                    score=0.0,
                )
            )

            # STAGE 2: Hybrid RAG Retrieval (BM25 + Semantic + Reranking)
            logger.info("\n[STAGE 2] Searching in RAG dataset (Hybrid)...")
            rag_matches = self.hybrid_retriever.retrieve(question["text"], top_k=1)

            if rag_matches:
                top_match = rag_matches[0]
                logger.info(
                    f"  [YES] RAG MATCH FOUND (rerank score: {top_match.rerank_score})"
                )
                logger.info(f"    BM25: {top_match.bm25_score}, Semantic: {top_match.semantic_score}")
                logger.info(f"    Original Q: {top_match.question[:70]}...")
                logger.info(f"    Answer: {top_match.answer[:100]}...")

                result.source = "rag_history"
                result.answer = top_match.answer

                # Calculate confidence using rerank score (better signal than BM25)
                confidence = ConfidenceCalculator.calculate_hybrid_rag_confidence(
                    top_match.rerank_score,
                    len(top_match.answer),
                )
                result.confidence = confidence
                result.confidence_level = ConfidenceCalculator.get_confidence_level(
                    confidence
                )

                result.processing_stages.append(
                    ProcessingStage(
                        stage_name="rag_retrieval",
                        result="found",
                        details=f"Source: {top_match.source_id} (rerank: {top_match.rerank_score})",
                        score=top_match.rerank_score,
                    )
                )

                # STAGE 3: LLM Synthesis (always, for Mode B).
                # Historical RAG answers are raw support-dialog snippets that
                # frequently answer a *different* question than the user's, or
                # contain chat artifacts. We always run the improver so it can
                # (a) verify relevance and defer with "call_human" when the
                # retrieved answer does not match, and (b) adapt/clean the text
                # for the specific question.
                logger.info(
                    f"\n[STAGE 3] Synthesizing RAG answer with LLM "
                    f"(base confidence: {confidence})..."
                )
                improved_answer, improved_confidence = (
                    self.llm_improver.improve_answer(
                        question["text"],
                        result.answer,
                        confidence,
                        always_improve=True,
                        rag_context=f"retrieved question: {top_match.question}",
                    )
                )

                result.answer = improved_answer
                result.confidence = improved_confidence
                result.confidence_level = ConfidenceCalculator.get_confidence_level(
                    improved_confidence
                )
                result.source = "rag_history+llm_improvement"

                logger.info(
                    f"  [YES] LLM synthesized answer "
                    f"(confidence: {confidence} -> {improved_confidence})"
                )

                result.processing_stages.append(
                    ProcessingStage(
                        stage_name="llm_improvement",
                        result="improved",
                        details="LLM synthesized/validated RAG answer",
                        score=improved_confidence,
                    )
                )


            else:
                logger.info("  [NO] No relevant Q&A found in RAG dataset")

                result.processing_stages.append(
                    ProcessingStage(
                        stage_name="rag_retrieval",
                        result="not_found",
                        details="No relevant Q&A pairs found",
                        score=0.0,
                    )
                )

                # STAGE 3: LLM Fallback
                logger.info("\n[STAGE 3] Attempting LLM fallback...")
                fallback_answer, fallback_confidence = self.llm_improver.improve_answer(
                    question["text"],
                    "No information found in knowledge base.",
                    0.0,
                )

                result.source = "llm_fallback"
                result.answer = fallback_answer
                result.confidence = fallback_confidence
                result.confidence_level = ConfidenceCalculator.get_confidence_level(
                    fallback_confidence
                )

                logger.info(
                    f"  [YES] LLM generated fallback answer "
                    f"(confidence: {fallback_confidence})"
                )

                result.processing_stages.append(
                    ProcessingStage(
                        stage_name="llm_fallback",
                        result="generated",
                        details="LLM generated answer when no RAG match found",
                        score=fallback_confidence,
                    )
                )

        # Final logging
        logger.info(f"\n[RESULT] {question['id']}")
        logger.info(f"  Source: {result.source}")
        logger.info(f"  Confidence: {result.confidence} ({result.confidence_level})")
        if result.approval_token:
            logger.info(f"  Approval Token: {result.approval_token[:32]}...")

        return result

    def run_benchmark(self) -> dict[str, Any]:
        """Run the complete benchmark.

        Returns:
            Benchmark results dictionary.
        """
        logger.info("\n\n")
        logger.info("#" * 80)
        logger.info("QUICKOFFER SUPPORT BOT - BENCHMARK EXECUTION")
        logger.info("#" * 80)

        # Extract test questions
        test_questions = self._extract_test_questions(num_questions=15)

        if not test_questions:
            logger.error("Failed to extract test questions!")
            return {}

        # Process each question
        logger.info(f"\n{'=' * 80}")
        logger.info("STEP 2: PROCESSING QUESTIONS")
        logger.info(f"{'=' * 80}")

        total_questions = len(test_questions)
        for i, question in enumerate(test_questions, 1):
            logger.info(f"\n\n>>> QUESTION {i}/{total_questions} <<<")

            result = self.process_question(question)
            self.results.append(result)

        # Generate summary
        logger.info(f"\n\n{'=' * 80}")
        logger.info("STEP 3: BENCHMARK SUMMARY")
        logger.info(f"{'=' * 80}\n")

        return self._generate_summary()

    def _generate_summary(self) -> dict[str, Any]:
        """Generate benchmark summary statistics.

        Returns:
            Summary dictionary.
        """
        total = len(self.results)
        flow_matches = sum(1 for r in self.results if r.flow_matched)
        rag_matches = sum(1 for r in self.results if r.source == "rag_history")
        llm_fallback = sum(1 for r in self.results if r.source == "llm_fallback")
        no_match = sum(1 for r in self.results if not r.answer)

        avg_confidence = (
            sum(r.confidence for r in self.results) / total if total > 0 else 0
        )

        confidence_distribution = {
            "very_high": sum(
                1 for r in self.results if r.confidence_level == "very_high"
            ),
            "high": sum(1 for r in self.results if r.confidence_level == "high"),
            "medium": sum(1 for r in self.results if r.confidence_level == "medium"),
            "low": sum(1 for r in self.results if r.confidence_level == "low"),
            "very_low": sum(
                1 for r in self.results if r.confidence_level == "very_low"
            ),
        }

        summary = {
            "benchmark_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),

            "total_questions": total,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "flow_match_rate": (
                    f"{(flow_matches / total * 100):.1f}%" if total > 0 else "0%"
                ),
                "flow_matches": flow_matches,
                "rag_matches": rag_matches,
                "llm_fallback": llm_fallback,
                "no_match": no_match,
                "average_confidence": round(avg_confidence, 2),
                "sources_breakdown": {
                    "instruction_flow": (
                        f"{(flow_matches / total * 100):.1f}%" if total > 0 else "0%"
                    ),
                    "rag_history": (
                        f"{(rag_matches / total * 100):.1f}%" if total > 0 else "0%"
                    ),
                    "llm_fallback": (
                        f"{(llm_fallback / total * 100):.1f}%" if total > 0 else "0%"
                    ),
                    "no_match": (
                        f"{(no_match / total * 100):.1f}%" if total > 0 else "0%"
                    ),
                },
                "confidence_distribution": confidence_distribution,
            },
        }

        # Log summary
        logger.info("BENCHMARK RESULTS SUMMARY")
        logger.info("-" * 80)
        logger.info(f"Total Questions: {total}")
        logger.info(
            f"Flow Matches: {flow_matches} ({summary['summary']['flow_match_rate']})"
        )
        logger.info(
            f"RAG Matches: {rag_matches} ({summary['summary']['sources_breakdown']['rag_history']})"
        )
        logger.info(
            f"LLM Fallback: {llm_fallback} ({summary['summary']['sources_breakdown']['llm_fallback']})"
        )
        logger.info(
            f"No Match: {no_match} ({summary['summary']['sources_breakdown']['no_match']})"
        )
        logger.info(f"\nAverage Confidence: {summary['summary']['average_confidence']}")
        logger.info(f"Confidence Distribution: {confidence_distribution}")
        logger.info("=" * 80)

        return summary

    def save_results(self, output_path: str = "benchmark_results.json") -> None:
        """Save benchmark results to JSON file.

        Args:
            output_path: Path to save results.
        """
        if not self.results:
            logger.error("No results to save!")
            return

        # Build summary
        summary = self._generate_summary()

        # Save to file
        output_file = Path(output_path)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"\n[OK] Results saved to {output_file.absolute()}")


def main() -> None:
    """Main entry point for benchmark."""
    benchmark = Benchmark()

    # Run benchmark
    results = benchmark.run_benchmark()

    # Save results
    benchmark.save_results("benchmark_results.json")

    logger.info("\n" + "=" * 80)
    logger.info("BENCHMARK COMPLETED")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
