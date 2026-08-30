"""LLM-based flow matcher - uses LLM to detect support flow intent."""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from src.services.processing.flow_matcher import FlowMatch, FlowMatcher

logger = logging.getLogger(__name__)


class LLMFlowMatcher:
    """Matches user questions with support flows using LLM."""

    def __init__(self, fallback_matcher: Optional[FlowMatcher] = None):
        """Initialize LLM flow matcher.

        Args:
            fallback_matcher: Optional FlowMatcher for fallback when LLM unavailable.
        """
        self.api_key = os.getenv("LLM_PROVIDER_KEY")
        self.api_base = os.getenv("LLM_BASE_URL", "https://litellm.ai.nestle.ru/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-4-turbo")
        self.fallback_matcher = fallback_matcher or FlowMatcher()

        if not self.api_key:
            logger.warning("LLM_PROVIDER_KEY not found, will use fallback matcher")

        logger.info(f"LLM Flow Matcher initialized with model: {self.model}")

    def match(self, question: str) -> Optional[FlowMatch]:
        """Match question with a support flow using LLM.

        Args:
            question: User question text.

        Returns:
            FlowMatch if a flow is matched, None otherwise.
        """
        if not self.api_key:
            logger.warning("LLM API key not configured, using fallback matcher")
            return self.fallback_matcher.match(question)

        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key, base_url=self.api_base)

            # Build system prompt
            system_prompt = self._build_system_prompt()

            # Build user prompt
            user_prompt = f"""Analyze this support question and determine which support flow it belongs to.

Question: {question}

Respond in JSON format:
{{
    "flow_name": "flow_name_here",
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

If no flow matches well, set flow_name to null."""

            # Call LLM
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=32768,
            )

            response_text = response.choices[0].message.content

            # Parse response
            import json

            result = json.loads(response_text)

            # Only accept high-confidence *transactional* flow matches. Purely
            # informational questions ("in what format...", "how does X work",
            # "how do I get Y included in my plan") must fall through to RAG
            # (Mode B), even when they mention a flow topic. A conservative
            # threshold prevents flows from hijacking these questions.
            flow_acceptance_threshold = 0.8

            if result.get("flow_name") and result.get("flow_name") in FlowMatcher.FLOWS:
                flow_name = result["flow_name"]
                confidence = float(result.get("confidence", 0.7))

                # Ensure confidence is in valid range
                confidence = max(0.0, min(1.0, confidence))

                if confidence < flow_acceptance_threshold:
                    logger.info(
                        f"LLM flow '{flow_name}' below acceptance threshold "
                        f"({confidence:.2f} < {flow_acceptance_threshold}); "
                        f"routing to RAG (Mode B)"
                    )
                    return None

                flow_match = FlowMatch(
                    flow_name=flow_name,
                    matched_keywords=[
                        f"llm_detected: {result.get('reason', 'intent matched')}"
                    ],
                    match_score=round(confidence, 2),
                    flow_description=FlowMatcher.FLOWS[flow_name]["description"],
                )

                logger.info(
                    f"LLM Flow matched: {flow_match.flow_name} "
                    f"(confidence: {flow_match.match_score}, "
                    f"reason: {result.get('reason', 'N/A')})"
                )
                return flow_match
            else:
                logger.info(f"LLM: No flow matched for question: {question[:100]}")
                return None

        except ImportError:
            logger.warning("OpenAI library not installed, using fallback matcher")
            return self.fallback_matcher.match(question)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}, using fallback")
            return self.fallback_matcher.match(question)
        except Exception as e:
            logger.error(f"Error in LLM flow matching: {e}, using fallback")
            return self.fallback_matcher.match(question)

    def _build_system_prompt(self) -> str:
        """Build system prompt for MODE A flow detection (PHASE 1: INTENT CLASSIFICATION).

        Returns:
            System prompt string for classifying questions into 6 deterministic flows.
        """
        return """You are QuickOffer support intent classifier (PHASE 1: INTENT CLASSIFICATION).

Classify user questions into MODE A deterministic flows or identify as MODE B.

MODE A: 6 DETERMINISTIC FLOWS (from Technical Specification):

1. return_refund - Refund payment + subscription deletion (staff approval required)
2. career_assistance - Career advice and expert consultations
3. job_archival - Permanent job vacancy suppression
4. referral_promo - Referral code generation (15% unlimited)
5. review_promo - Review reward promo codes (15% one-time)
6. crypto_alt_payment - Crypto/foreign card payment options

FEW-SHOT EXAMPLES:

[MODE A EXAMPLES]
User: "Как мне вернуть деньги?" → Flow: return_refund (confidence: 0.95)
User: "Помогите с карьерой" → Flow: career_assistance (confidence: 0.92)
User: "Дайте промокод друга" → Flow: referral_promo (confidence: 0.88)
User: "Хочу заархивировать вакансию" → Flow: job_archival (confidence: 0.90)

[MODE B EXAMPLES - NO DETERMINISTIC FLOW]
User: "Почему не работает поиск?" → No flow match (Mode B: RAG+LLM investigation)
User: "Как перезагрузить приложение?" → No flow match (Mode B)

[MODE B EXAMPLES - INFORMATIONAL QUESTIONS ABOUT A FLOW TOPIC]
User: "В каком формате проходит карьерная консультация?" → No flow match (informational, Mode B)
User: "Как получить карьерную консультацию, доступную по тарифу?" → No flow match (informational, Mode B)
User: "Как работает реферальная программа?" → No flow match (informational, Mode B)
User: "Куда оставить отзыв, чтобы получить скидку?" → No flow match (informational, Mode B)

CLASSIFICATION RULES:
- Analyze intent deeply, not just keywords
- Consider Russian language variations
- Return confidence 0.0-1.0
- MODE A is ONLY for TRANSACTIONAL intent where the user asks the system to
  PERFORM an action (refund me, archive this vacancy, generate my promo code,
  pay with crypto). It is NOT for informational questions.
- INFORMATIONAL questions ("in what format...", "how does X work", "how do I
  get Y", "where do I...", "how much...") are ALWAYS Mode B, even if they
  mention a flow topic. Set flow_name to null for these.
- If best match confidence < 0.8: classify as MODE_B (no deterministic flow)
- For MODE_B questions: set flow_name to null"""
