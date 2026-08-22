"""Interactive CLI demo - allows user to input questions and see bot responses."""

import logging
import sys
from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.benchmarking.confidence_calculator import ConfidenceCalculator
from src.benchmarking.llm_flow_matcher import LLMFlowMatcher
from src.benchmarking.llm_improver import LLMImprover
from src.benchmarking.approval_generator import ApprovalTokenGenerator
from src.benchmarking.rag_retriever import RAGRetriever

# Setup logging (minimal output)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


class InteractiveDemo:
    """Interactive CLI demo for QuickOffer support bot."""

    def __init__(self):
        """Initialize demo components."""
        print("\n" + "=" * 80)
        print("QUICKOFFER SUPPORT BOT - INTERACTIVE DEMO")
        print("=" * 80)
        print("\nInitializing components...")

        self.flow_matcher = LLMFlowMatcher()
        self.rag_retriever = RAGRetriever("docs/rag_dataset_train.jsonl")
        self.llm_improver = LLMImprover()
        self.approval_generator = ApprovalTokenGenerator()

        print("[OK] All components initialized successfully")
        print("\nType 'exit' or 'quit' to leave the demo\n")

    def process_question(self, question: str) -> dict:
        """Process a question through the entire pipeline.

        Args:
            question: User question text.

        Returns:
            Dictionary with processing results.
        """
        result = {
            "question": question,
            "stages": [],
            "final_answer": None,
            "confidence": 0.0,
            "confidence_level": "very_low",
            "approval_token": None,
        }

        # STAGE 1: Flow Matching
        print("\n[STAGE 1] Matching with instruction flows...")
        flow_match = self.flow_matcher.match(question)

        if flow_match:
            print(f"  [YES] Flow matched: {flow_match.flow_name}")
            print(f"  Confidence: {flow_match.match_score}")
            print(f"  Description: {flow_match.flow_description}")

            result["stages"].append(
                {
                    "name": "flow_matching",
                    "result": "matched",
                    "flow_name": flow_match.flow_name,
                    "score": flow_match.match_score,
                }
            )

            result["final_answer"] = flow_match.flow_description
            result["confidence"] = ConfidenceCalculator.calculate_flow_confidence(
                flow_match.match_score
            )
            result["approval_token"] = self.approval_generator.generate_benchmark_token(
                flow_match.flow_name
            )

        else:
            print("  [NO] No flow matched, proceeding to RAG retrieval...")

            result["stages"].append(
                {
                    "name": "flow_matching",
                    "result": "not_matched",
                }
            )

            # STAGE 2: RAG Retrieval
            print("\n[STAGE 2] Searching in RAG dataset (BM25)...")
            rag_matches = self.rag_retriever.retrieve(question, top_k=3)

            if rag_matches:
                top_match = rag_matches[0]
                print(
                    f"  [YES] Found relevant Q&A (relevance: {top_match.relevance_score})"
                )
                print(f"  Similar question: {top_match.question[:80]}...")
                print(f"  Answer: {top_match.answer[:100]}...")

                result["stages"].append(
                    {
                        "name": "rag_retrieval",
                        "result": "found",
                        "similar_question": top_match.question,
                        "relevance_score": top_match.relevance_score,
                    }
                )

                result["final_answer"] = top_match.answer
                confidence = ConfidenceCalculator.calculate_rag_confidence(
                    top_match.relevance_score, len(top_match.answer)
                )
                result["confidence"] = confidence

                # STAGE 3: LLM Improvement (if needed)
                if confidence < 0.65:
                    print(f"\n[STAGE 3] Confidence too low ({confidence})")
                    print("  Attempting LLM improvement...")
                    improved_answer, improved_confidence = (
                        self.llm_improver.improve_answer(
                            question, result["final_answer"], confidence
                        )
                    )

                    print(f"  [YES] LLM improved answer")
                    print(f"  Confidence: {confidence} -> {improved_confidence}")

                    result["stages"].append(
                        {
                            "name": "llm_improvement",
                            "result": "improved",
                            "original_confidence": confidence,
                            "improved_confidence": improved_confidence,
                        }
                    )

                    result["final_answer"] = improved_answer
                    result["confidence"] = improved_confidence

            else:
                print("  [NO] No relevant Q&A found in knowledge base")

                result["stages"].append(
                    {
                        "name": "rag_retrieval",
                        "result": "not_found",
                    }
                )

                # STAGE 3: LLM Fallback
                print("\n[STAGE 3] Attempting LLM fallback generation...")
                fallback_answer, fallback_confidence = self.llm_improver.improve_answer(
                    question, "No information found in knowledge base.", 0.0
                )

                print(f"  [YES] LLM generated fallback answer")
                print(f"  Confidence: {fallback_confidence}")

                result["stages"].append(
                    {
                        "name": "llm_fallback",
                        "result": "generated",
                        "confidence": fallback_confidence,
                    }
                )

                result["final_answer"] = fallback_answer
                result["confidence"] = fallback_confidence

        result["confidence_level"] = ConfidenceCalculator.get_confidence_level(
            result["confidence"]
        )

        return result

    def display_result(self, result: dict) -> None:
        """Display processing result in a user-friendly format.

        Args:
            result: Processing result dictionary.
        """
        print("\n" + "=" * 80)
        print("RESULT")
        print("=" * 80)

        print(f"\nFinal Answer:\n{result['final_answer']}")

        print(
            f"\nConfidence: {result['confidence']:.2f} ({result['confidence_level']})"
        )

        if result["approval_token"]:
            print(f"Approval Token: {result['approval_token'][:32]}...")

        print("\nProcessing Pipeline:")
        for i, stage in enumerate(result["stages"], 1):
            stage_name = stage["name"].upper()
            stage_result = stage["result"].upper()
            print(f"  [{i}] {stage_name}: {stage_result}")

            if stage["name"] == "rag_retrieval" and stage["result"] == "found":
                print(f"      Relevance: {stage['relevance_score']}")

            if stage["name"] == "llm_improvement":
                print(
                    f"      Confidence: {stage['original_confidence']:.2f} -> "
                    f"{stage['improved_confidence']:.2f}"
                )

        print("=" * 80)

    def run(self) -> None:
        """Run the interactive demo loop."""
        while True:
            try:
                question = input("\n[Enter your question]: ").strip()

                if question.lower() in ["exit", "quit", "q"]:
                    print("\nGoodbye!")
                    break

                if not question:
                    print("Please enter a valid question.")
                    continue

                result = self.process_question(question)
                self.display_result(result)

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError processing question: {e}")
                logger.exception("Error in interactive demo")


def main() -> None:
    """Main entry point for interactive demo."""
    try:
        demo = InteractiveDemo()
        demo.run()
    except Exception as e:
        print(f"Failed to initialize demo: {e}")
        logger.exception("Failed to initialize demo")
        sys.exit(1)


if __name__ == "__main__":
    main()
