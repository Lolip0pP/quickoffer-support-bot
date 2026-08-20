"""Main benchmark script - evaluates QA system on 10 test questions."""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.benchmarking.approval_generator import ApprovalTokenGenerator
from src.benchmarking.confidence_calculator import ConfidenceCalculator, ConfidenceSource
from src.benchmarking.flow_matcher import FlowMatcher
from src.benchmarking.rag_retriever import RAGRetriever

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("benchmark.log"),
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
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "question_id": self.question_id,
            "question": self.question,
            "flow_matched": self.flow_matched,
            "flow_match_score": self.flow_match_score,
            "source": self.source,
            "answer": self.answer[:200] if self.answer else None,  # Truncate for JSON
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "approval_token": self.approval_token,
            "processing_stages": [
                asdict(stage) for stage in self.processing_stages
            ],
            "timestamp": self.timestamp,
        }


class Benchmark:
    """Main benchmark class."""

    def __init__(self, dataset_path: str = "docs/rag_dataset.jsonl"):
        """Initialize benchmark.

        Args:
            dataset_path: Path to RAG dataset.
        """
        logger.info("=" * 80)
        logger.info("QUICKOFFER SUPPORT BOT - BENCHMARK INITIALIZATION")
        logger.info("=" * 80)

        self.dataset_path = dataset_path
        self.flow_matcher = FlowMatcher()
        self.rag_retriever = RAGRetriever(dataset_path)
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
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    if extracted_count >= num_questions:
                        break

                    try:
                        record = json.loads(line)
                        qa_pairs = record.get("qa_pairs", [])

                        if qa_pairs:
                            qa = qa_pairs[0]
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

            # STAGE 2: RAG Retrieval
            logger.info("\n[STAGE 2] Searching in RAG dataset (BM25)...")
            rag_matches = self.rag_retriever.retrieve(question["text"], top_k=1)

            if rag_matches:
                top_match = rag_matches[0]
                logger.info(
                    f"  [YES] RAG MATCH FOUND (relevance: {top_match.relevance_score})"
                )
                logger.info(f"    Original Q: {top_match.question[:70]}...")
                logger.info(f"    Answer: {top_match.answer[:100]}...")

                result.source = "rag_history"
                result.answer = top_match.answer

                # Calculate confidence
                confidence = ConfidenceCalculator.calculate_rag_confidence(
                    top_match.relevance_score,
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
                        details=f"Source: {top_match.source_id}",
                        score=top_match.relevance_score,
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

                # STAGE 3: LLM Fallback (not implemented - just logging)
                logger.info("\n[STAGE 3] LLM fallback would be used here")
                logger.info("  (LLM integration skipped for benchmark)")

                result.source = "llm_fallback"
                result.answer = "Unable to find answer in knowledge base"
                result.confidence = 0.3
                result.confidence_level = "low"

                result.processing_stages.append(
                    ProcessingStage(
                        stage_name="llm_fallback",
                        result="skipped",
                        details="LLM fallback not configured",
                        score=0.0,
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
        test_questions = self._extract_test_questions(num_questions=10)

        if not test_questions:
            logger.error("Failed to extract test questions!")
            return {}

        # Process each question
        logger.info(f"\n{'=' * 80}")
        logger.info("STEP 2: PROCESSING QUESTIONS")
        logger.info(f"{'=' * 80}")

        for i, question in enumerate(test_questions, 1):
            logger.info(f"\n\n>>> QUESTION {i}/10 <<<")
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
            "very_high": sum(1 for r in self.results if r.confidence_level == "very_high"),
            "high": sum(1 for r in self.results if r.confidence_level == "high"),
            "medium": sum(1 for r in self.results if r.confidence_level == "medium"),
            "low": sum(1 for r in self.results if r.confidence_level == "low"),
            "very_low": sum(1 for r in self.results if r.confidence_level == "very_low"),
        }

        summary = {
            "benchmark_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "total_questions": total,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "flow_match_rate": f"{(flow_matches / total * 100):.1f}%" if total > 0 else "0%",
                "flow_matches": flow_matches,
                "rag_matches": rag_matches,
                "llm_fallback": llm_fallback,
                "no_match": no_match,
                "average_confidence": round(avg_confidence, 2),
                "sources_breakdown": {
                    "instruction_flow": f"{(flow_matches / total * 100):.1f}%" if total > 0 else "0%",
                    "rag_history": f"{(rag_matches / total * 100):.1f}%" if total > 0 else "0%",
                    "llm_fallback": f"{(llm_fallback / total * 100):.1f}%" if total > 0 else "0%",
                    "no_match": f"{(no_match / total * 100):.1f}%" if total > 0 else "0%",
                },
                "confidence_distribution": confidence_distribution,
            },
        }

        # Log summary
        logger.info("BENCHMARK RESULTS SUMMARY")
        logger.info("-" * 80)
        logger.info(f"Total Questions: {total}")
        logger.info(f"Flow Matches: {flow_matches} ({summary['summary']['flow_match_rate']})")
        logger.info(f"RAG Matches: {rag_matches} ({summary['summary']['sources_breakdown']['rag_history']})")
        logger.info(f"LLM Fallback: {llm_fallback} ({summary['summary']['sources_breakdown']['llm_fallback']})")
        logger.info(f"No Match: {no_match} ({summary['summary']['sources_breakdown']['no_match']})")
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

        logger.info(f"\n✓ Results saved to {output_file.absolute()}")


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
