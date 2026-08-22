"""LLM-based flow matcher - uses LLM to detect support flow intent."""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from src.benchmarking.flow_matcher import FlowMatch, FlowMatcher

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
                max_tokens=200,
            )

            response_text = response.choices[0].message.content

            # Parse response
            import json

            result = json.loads(response_text)

            if result.get("flow_name") and result.get("flow_name") in FlowMatcher.FLOWS:
                flow_name = result["flow_name"]
                confidence = float(result.get("confidence", 0.7))

                # Ensure confidence is in valid range
                confidence = max(0.0, min(1.0, confidence))

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
        """Build system prompt for flow detection.

        Returns:
            System prompt string.
        """
        return """You are an expert support system flow classifier for QuickOffer, a job search and career service platform.

Your task is to analyze user questions and determine which support flow they belong to.

AVAILABLE SUPPORT FLOWS:

1. return_refund
   - Keywords: возврат, refund, вернуть, деньги, средства
   - Purpose: Handle payment refunds and subscription freezing
   - Example: "Can I get a refund?" "Вернить деньги"

2. account_deletion
   - Keywords: удалить аккаунт, delete account, удаление
   - Purpose: Handle account and data deletion
   - Example: "How to delete my account?" "Удалить мой аккаунт"

3. search_configuration
   - Keywords: настроить, поиск, configure, keywords, фильтры
   - Purpose: Help with search query setup and filters
   - Example: "How to configure search?" "Как настроить поиск по ключевым словам?"

4. subscription_management
   - Keywords: подписка, subscription, тариф, продлить, автопродление
   - Purpose: Manage subscription, plan changes, auto-renewal
   - Example: "Can I extend my subscription?" "Как отключить автопродление?"

5. response_sending
   - Keywords: отклик, response, отправка, лимит, дневной лимит
   - Purpose: Handle application/response sending and limits
   - Example: "Why can't I send responses?" "Дневной лимит откликов"

6. account_access
   - Keywords: вход, авторизация, login, пароль, не могу войти
   - Purpose: Handle login issues and account access
   - Example: "I can't log in" "Ошибка входа"

IMPORTANT RULES:
- Analyze the intent of the question, not just keywords
- Return a confidence score (0.0-1.0) based on how well the question matches the flow
- Consider Russian language variations and synonyms
- If multiple flows match, return the most relevant one
- Return null flow_name only if absolutely no flow matches well"""
