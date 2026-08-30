# QuickOffer Support Bot

A support-processing core that can run locally today and be connected to Telegram tomorrow.

- **Mode A** plans one of six deterministic support flows. Mutating steps remain outside the LLM and require the existing approval/FSM path.
- **Mode B** searches the knowledge base and optionally improves a read-only response with an LLM.
- The same `QuestionProcessor` is used by the local CLI, benchmarks, and future Telegram handlers.

## Run locally

```bash
pip install -e '.[dev,benchmarking]'
python -m src.benchmarking.interactive_demo
pytest
```

Copy `.env.example` to `.env` only when external services are needed. The demo starts without Telegram credentials. See [architecture](ARCHITECTURE.md) and the [Russian README](README_RU.md).
