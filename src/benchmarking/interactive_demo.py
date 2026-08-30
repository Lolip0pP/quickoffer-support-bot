"""Local, Telegram-free CLI for the same support processing pipeline."""

import asyncio
import logging

from src.services.processing import QuestionProcessor

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


async def main() -> None:
    """Run the local support assistant until the user exits."""
    processor = QuestionProcessor()
    print("QuickOffer Support Bot — local demo. Type 'exit' to quit.")
    try:
        while True:
            question = input("\nQuestion: ").strip()
            if question.lower() in {"exit", "quit", "q"}:
                return
            if not question:
                continue
            result = await processor.process(question)
            context = result.context
            print(f"\n{context.final_answer}\n")
            print(context.format_for_display())
    finally:
        await processor.close()


if __name__ == "__main__":
    asyncio.run(main())
