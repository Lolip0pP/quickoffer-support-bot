# Architecture

## One processing core

`src.services.processing.QuestionProcessor` is the application boundary for every input adapter. It validates the question, classifies it, records phases, and returns a `ProcessingResult`. The CLI is intentionally a thin adapter; Telegram handlers should call this class rather than duplicate routing or RAG logic.

```text
CLI / Telegram / benchmark
          │
  QuestionProcessor
   ├─ Mode A: IntentRouter → safe FSM plan → approval/backend execution
   └─ Mode B: HybridRetriever → optional LLM answer improvement
```

Mode A **never executes tools** in the processor. It produces a plan and, for risky flows, an approval token. A Telegram FSM owns data collection and calls typed M2M clients only after approval.

## Provider configuration

All LLM chat calls use an OpenAI-compatible `LLM_BASE_URL`:

| Purpose | Example configuration |
| --- | --- |
| Local LiteLLM | `LLM_PROVIDER=local`, `LLM_BASE_URL=http://localhost:4000/v1` |
| OpenRouter | `LLM_PROVIDER=openrouter`, `LLM_BASE_URL=https://openrouter.ai/api/v1` |
| ZeroEntropy reranking | `RERANKER_BASE_URL=…`, `RERANKER_MODEL=…` |

`LLM_PROVIDER_KEY` is optional for an unauthenticated local proxy, but required by hosted providers. Embeddings use `LLM_BASE_URL`; set `RERANKER_BASE_URL` to route only reranking to ZeroEntropy. No Telegram configuration is required for the local CLI or tests.

## Repository layout

- `src/services/processing/`: reusable routing, retrieval, confidence, and pipeline code.
- `src/benchmarking/`: evaluation scripts only; it depends on the processing package.
- `src/presentation/telegram/`: input adapter and deterministic flow UI.
- `docs/instruction.md`: operational policy for support flows.
