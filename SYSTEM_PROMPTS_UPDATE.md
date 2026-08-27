# System Prompts Update - New Terminology

## Overview

All LLM system prompts have been updated to reflect the new architecture understanding:
- **MODE A**: Deterministic State Machine (6 flows from ТЗ)
- **MODE B**: LLM Investigation with RAG

## Files Updated

### 1. `src/services/llm.py` - Generic LLM Service (OpenAI & Anthropic)

**Previous:**
```python
"You are a helpful support bot assistant. "
"Analyze support tickets and provide suggestions. "
"You cannot execute any actions - only analyze and suggest."
```

**Updated:**
```python
"You are a QuickOffer support bot assistant (MODE B: LLM Investigation). "
"You are read-only: analyze questions and provide suggestions only. "
"Never execute actions, mutations, or access production data. "
"For high-risk operations (refund, job archival, crypto), defer to staff approval."
```

**Why:** Now explicitly mentions this is MODE B (LLM Investigation), not MODE A (deterministic flows).

### 2. `src/benchmarking/llm_flow_matcher.py` - MODE A Flow Detection (PHASE 1)

**Purpose:** Classify questions into 6 deterministic flows OR identify as MODE B.

**Key Changes:**
- Updated all 6 flows to match ТЗ (Technical Specification):
  1. `return_refund` - Refund + subscription deletion
  2. `career_assistance` - Career advice
  3. `job_archival` - Job suppression
  4. `referral_promo` - Referral codes
  5. `review_promo` - Review codes
  6. `crypto_alt_payment` - Crypto/foreign card

- **Added Few-Shot Examples:**
  ```
  User: "Как мне вернуть деньги?" → Flow: return_refund (confidence: 0.95)
  User: "Помогите с карьерой" → Flow: career_assistance (confidence: 0.92)
  User: "Дайте промокод друга" → Flow: referral_promo (confidence: 0.88)
  User: "Как перезагрузить приложение?" → No flow match (Mode B)
  ```

- **Classification Rule:** If confidence < 0.7, classify as MODE_B (no deterministic flow).

**Why:** LLM now knows:
- What MODE A vs MODE B is
- Exactly which 6 flows are deterministic
- When to defer to MODE B (RAG + LLM)
- Examples help with accuracy

### 3. `src/benchmarking/llm_improver.py` - MODE B Answer Improvement (PHASE 3)

**Purpose:** Improve RAG answers in MODE B investigation when confidence is low.

**Key Changes:**
- Explicitly states: "ВАША РОЛЬ (MODE B ТОЛЬКО)" - Your role (MODE B ONLY)
- **Added Few-Shot Examples for answer improvement:**
  ```
  Исходный: "секундочку... нужно в приложение зайти... дайте проверю"
  Улучшенный: "Чтобы найти настройки, откройте приложение, нажмите на значок профиля..."
  
  Исходный: "вчера я видел что-то похожее... может быть..."
  Улучшенный: "Попробуйте обновить приложение до последней версии..."
  ```

- **Added Rules for MODE A vs MODE B:**
  - "НИКОГДА не обещать Mode A действия (возврат, архивирование, выдачу крипто)"
  - "Если вопрос про refund → скажите 'Запросите возврат в приложении, команда одобрит'"
  - "Если про архивирование вакансии → 'Напишите нам с деталями, команда поможет'"

**Why:** LLM now understands:
- It only operates in MODE B
- Mode A actions require staff approval
- How to improve low-quality answers with examples
- When to defer to human staff

## Impact on System Behavior

### Before

LLM prompts were generic, didn't distinguish between:
- Deterministic (MODE A) vs Investigation (MODE B)
- When to execute vs when to defer
- Which 6 flows are "real" state machines

### After

LLM prompts now explicitly:
1. **Classify correctly** (PHASE 1): Determine MODE A or MODE B
2. **Handle MODE A flows** (if matched): Prepare for state machine execution
3. **Handle MODE B answers** (if no match): Improve via RAG + LLM with examples
4. **Defer appropriately**: Know when to escalate to staff approval

## Few-Shot Learning

All three prompts now include specific examples:

### Flow Matcher Examples (PHASE 1)
```
MODE A: "Как мне вернуть деньги?" → return_refund (0.95)
MODE B: "Почему не работает поиск?" → No match (Mode B investigation)
```

### Answer Improver Examples (PHASE 3)
```
Bad → Good transformations showing:
- Chat artifacts removal ("секундочку" → removed)
- Imperative tone ("откройте" instead of "нужно")
- Clear steps (numbered instructions)
- Mobile-friendly formatting
```

## Testing

To verify the updates:

```bash
# Compile check
python -m py_compile src/services/llm.py \
  src/benchmarking/llm_flow_matcher.py \
  src/benchmarking/llm_improver.py

# Run interactive demo
python -m src.benchmarking.interactive_demo

# Test cases:
# MODE A: "как мне вернуть деньги?" → shows refund flow + expected tools
# MODE B: "как перезагрузить приложение?" → shows RAG + LLM path
```

## Consistency with Architecture

These changes align with:
- **ARCHITECTURE.md** - Documents MODE A vs MODE B phases
- **FLOW_TERMINOLOGY.md** - Clarifies flow terminology
- **ProcessingContext** - Tracks mode, flow type, phases, tools
- **IntentRouter** - Routes to MODE A or MODE B

## Future Considerations

- Few-shot examples should be expanded as we collect more test cases
- Prompts can be version-controlled with flow definitions
- Consider prompt caching for high-volume scenarios
- Monitor LLM accuracy for MODE A vs MODE B classification

## Related Files

- `src/benchmarking/processing_phases.py` - Data structures for phases
- `src/benchmarking/intent_router.py` - Routes questions to modes
- `src/benchmarking/interactive_demo.py` - Shows phase-by-phase execution
- `ARCHITECTURE.md` - Full architecture documentation
- `FLOW_TERMINOLOGY.md` - Terminology clarification
