"""Interactive CLI demo - allows user to input questions and see bot responses."""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.benchmarking.approval_generator import ApprovalTokenGenerator
from src.benchmarking.confidence_calculator import ConfidenceCalculator
from src.benchmarking.hybrid_retriever import HybridRetriever
from src.benchmarking.intent_router import IntentRouter
from src.benchmarking.llm_improver import LLMImprover
from src.benchmarking.processing_phases import OperationPhase, ProcessingMode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
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

        self.intent_router = IntentRouter()

        # Initialize hybrid retriever with environment variables
        llm_base_url = os.getenv(
            "LLM_BASE_URL", "https://litellm.ai.nestle.ru/v1"
        )
        llm_api_key = os.getenv("LLM_PROVIDER_KEY", "")

        self.hybrid_retriever = HybridRetriever(
            dataset_path="docs/rag_dataset.jsonl",
            base_url=llm_base_url,
            api_key=llm_api_key,
            use_reranker=True,
        )

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
        print("\n" + "=" * 80)
        print("[PHASE 1] INTENT CLASSIFICATION")
        print("=" * 80)

        # PHASE 1: Intent Classification (MODE_A vs MODE_B)
        context = self.intent_router.route(question)
        context.add_phase_log(
            OperationPhase.INTENT_CLASSIFICATION,
            status="success",
            details={
                "mode": context.processing_mode.value,
                "flow_type": context.flow_type.value if context.flow_type else None,
                "confidence": f"{context.confidence:.2f}",
            },
        )

        print(f"\nProcessing Mode: {context.processing_mode.value.upper()}")
        if context.flow_type:
            print(f"Flow Type: {context.flow_type.value.upper()}")
        print(f"Confidence: {context.confidence:.2f}")

        # Display expected tools for MODE_A
        if context.processing_mode == ProcessingMode.MODE_A_DETERMINISTIC:
            print("\nExpected Operations:")
            for i, tool in enumerate(context.expected_tools, 1):
                approval_str = (
                    " (requires approval)" if tool.requires_approval else ""
                )
                print(f"  {i}. {tool.description}{approval_str}")

            if context.requires_staff_approval:
                print("\n⚠️  Staff Approval Required: YES")

            # PHASE 2: State Machine Initialization (MODE_A only)
            print("\n" + "=" * 80)
            print("[PHASE 2] STATE MACHINE INITIALIZATION")
            print("=" * 80)
            print(f"\nFlow: {context.flow_type.value.upper()}")
            print("Initial State: IDENTIFY")
            print(f"Approval Required: {context.requires_staff_approval}")

            context.add_phase_log(
                OperationPhase.STATE_MACHINE_INIT,
                status="success",
                details={
                    "flow": context.flow_type.value,
                    "state": "IDENTIFY",
                    "tools_count": len(context.expected_tools),
                },
            )

            # Generate approval token if needed
            if context.requires_staff_approval:
                context.approval_token = (
                    self.approval_generator.generate_benchmark_token(
                        context.flow_type.value
                    )
                )
                print(f"Approval Token: {context.approval_token[:32]}...")

            # PHASE 3: Tool Execution (MODE_A only)
            print("\n" + "=" * 80)
            print("[PHASE 3] TOOL EXECUTION (SIMULATED)")
            print("=" * 80)
            print("\nSimulating state machine progression:")
            for i, tool in enumerate(context.expected_tools, 1):
                status_icon = "✓"
                print(f"  {status_icon} [{i}] {tool.description}")
                # Simulate tool execution
                tool.status = "success"
                context.add_executed_tool(tool)

            context.add_phase_log(
                OperationPhase.TOOL_EXECUTION,
                status="success",
                details={"tools_executed": len(context.executed_tools)},
            )

            print(
                f"\n✓ All {len(context.executed_tools)} tools executed successfully"
            )
            context.final_answer = (
                f"State machine for {context.flow_type.value} completed successfully. "
                f"Awaiting staff approval for critical operations."
            )
            context.add_phase_log(
                OperationPhase.HANDOFF,
                status="pending" if context.requires_staff_approval else "skipped",
                details={"requires_approval": context.requires_staff_approval},
            )

        else:
            # MODE_B: RAG + LLM Investigation
            print("\n" + "=" * 80)
            print("[PHASE 2] RAG RETRIEVAL")
            print("=" * 80)
            print("\nSearching in RAG dataset (Hybrid Search)...")

            hybrid_matches = self.hybrid_retriever.retrieve(question, top_k=1)

            if hybrid_matches:
                top_match = hybrid_matches[0]
                print(f"\n✓ Found relevant Q&A")
                print(f"  BM25 Score: {top_match.bm25_score:.2f}")
                print(f"  Semantic Score: {top_match.semantic_score:.2f}")
                print(f"  Rerank Score: {top_match.rerank_score:.2f}")
                print(f"  Similar question: {top_match.question[:80]}...")

                context.add_phase_log(
                    OperationPhase.RAG_RETRIEVAL,
                    status="success",
                    details={
                        "bm25_score": f"{top_match.bm25_score:.2f}",
                        "semantic_score": f"{top_match.semantic_score:.2f}",
                        "rerank_score": f"{top_match.rerank_score:.2f}",
                    },
                )

                context.final_answer = top_match.answer
                confidence = ConfidenceCalculator.calculate_hybrid_rag_confidence(
                    top_match.rerank_score, len(top_match.answer)
                )
                context.confidence = confidence

                # PHASE 3: LLM Improvement (if needed)
                if confidence < 0.65:
                    print(f"\n[PHASE 3] LLM IMPROVEMENT")
                    print("=" * 80)
                    print(f"\nConfidence too low ({confidence:.2f})")
                    print("Attempting LLM improvement...")

                    improved_answer, improved_confidence = (
                        self.llm_improver.improve_answer(
                            question, context.final_answer, confidence
                        )
                    )

                    print(f"✓ LLM improved answer")
                    print(f"  Confidence: {confidence:.2f} → {improved_confidence:.2f}")

                    context.add_phase_log(
                        OperationPhase.LLM_GENERATION,
                        status="success",
                        details={
                            "original_confidence": f"{confidence:.2f}",
                            "improved_confidence": f"{improved_confidence:.2f}",
                        },
                    )

                    context.final_answer = improved_answer
                    context.confidence = improved_confidence

            else:
                print("\n✗ No relevant Q&A found in knowledge base")

                context.add_phase_log(
                    OperationPhase.RAG_RETRIEVAL,
                    status="not_found",
                    details={},
                )

                # PHASE 3: LLM Fallback
                print("\n[PHASE 3] LLM FALLBACK GENERATION")
                print("=" * 80)
                print("\nAttempting LLM fallback generation...")

                fallback_answer, fallback_confidence = (
                    self.llm_improver.improve_answer(
                        question, "No information found in knowledge base.", 0.0
                    )
                )

                print(f"✓ LLM generated fallback answer")
                print(f"  Confidence: {fallback_confidence:.2f}")

                context.add_phase_log(
                    OperationPhase.LLM_GENERATION,
                    status="success",
                    details={"type": "fallback", "confidence": f"{fallback_confidence:.2f}"},
                )

                context.final_answer = fallback_answer
                context.confidence = fallback_confidence

        return {
            "context": context,
            "confidence_level": ConfidenceCalculator.get_confidence_level(
                context.confidence
            ),
        }

    def display_result(self, result: dict) -> None:
        """Display processing result in a user-friendly format.

        Args:
            result: Processing result dictionary.
        """
        context = result["context"]

        print("\n" + "=" * 80)
        print("RESULT")
        print("=" * 80)

        print(f"\nFinal Answer:\n{context.final_answer}")

        print(
            f"\nConfidence: {context.confidence:.2f} ({result['confidence_level']})"
        )

        if context.approval_token:
            print(f"Approval Token: {context.approval_token[:32]}...")

        if context.handoff_triggered:
            print(
                f"\n⚠️  Handoff Triggered: {context.handoff_reason}"
            )

        # Summary table
        print("\n" + "=" * 80)
        print("PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Mode: {context.processing_mode.value}")
        if context.flow_type:
            print(f"Flow: {context.flow_type.value}")
        print(f"Confidence: {context.confidence:.2f}")
        print(f"Phases: {len(context.phases)}")
        print(f"Expected Tools: {len(context.expected_tools)}")
        print(f"Executed Tools: {len(context.executed_tools)}")

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
