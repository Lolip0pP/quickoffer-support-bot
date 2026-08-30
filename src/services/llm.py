"""LLM (Large Language Model) service - READ-ONLY integration."""

import uuid
from typing import Any

from src.core.config import settings
from src.domain.interfaces import LLMService


class OpenAILLMService(LLMService):
    """OpenAI-based LLM service (READ-ONLY)."""

    def __init__(self) -> None:
        """Initialize OpenAI LLM service."""
        self.api_key = settings.llm_provider_key
        self.model = settings.llm_model
        self.provider = "openai"

    async def generate_response(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> str:
        """Generate LLM response (READ-ONLY).

        This is a read-only operation that does not modify any state.

        Args:
            prompt: User prompt.
            context: Optional context for response generation.

        Returns:
            str: Generated response.
        """
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "You are a QuickOffer support bot assistant (MODE B: LLM Investigation). "
            "You are read-only: analyze questions and provide suggestions only. "
            "Never execute actions, mutations, or access production data. "
            "For high-risk operations (refund, job archival, crypto), defer to staff approval."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def analyze_ticket(self, ticket_content: str) -> dict[str, Any]:
        """Analyze support ticket content (READ-ONLY).

        Args:
            ticket_content: Support ticket content.

        Returns:
            dict: Analysis result with severity, category, etc.
        """
        analysis_prompt = (
            f"Analyze this support ticket and provide a JSON response "
            f"with fields: severity (low|medium|high), "
            f"category (technical|billing|account|other), "
            f"suggested_action (escalate|auto_resolve|manual_review). "
            f"Ticket: {ticket_content}"
        )

        response_text = await self.generate_response(analysis_prompt)

        import json

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {
                "severity": "medium",
                "category": "other",
                "suggested_action": "manual_review",
            }

    async def suggest_resolution(self, ticket_id: uuid.UUID) -> str:
        """Suggest resolution for a ticket (READ-ONLY).

        Args:
            ticket_id: Support ticket identifier.

        Returns:
            str: Suggested resolution text.
        """
        suggestion_prompt = (
            f"Provide a helpful suggestion for resolving "
            f"support ticket {ticket_id}. "
            f"Focus on common solutions and best practices."
        )

        return await self.generate_response(suggestion_prompt)


class AnthropicLLMService(LLMService):
    """Anthropic Claude-based LLM service (READ-ONLY)."""

    def __init__(self) -> None:
        """Initialize Anthropic LLM service."""
        self.api_key = settings.llm_provider_key
        self.model = settings.llm_model or "claude-3-sonnet-20240229"
        self.provider = "anthropic"

    async def generate_response(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> str:
        """Generate LLM response (READ-ONLY).

        This is a read-only operation that does not modify any state.

        Args:
            prompt: User prompt.
            context: Optional context for response generation.

        Returns:
            str: Generated response.
        """
        import httpx

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "You are a QuickOffer support bot assistant (MODE B: LLM Investigation). "
            "You are read-only: analyze questions and provide suggestions only. "
            "Never execute actions, mutations, or access production data. "
            "For high-risk operations (refund, job archival, crypto), defer to staff approval."
        )

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def analyze_ticket(self, ticket_content: str) -> dict[str, Any]:
        """Analyze support ticket content (READ-ONLY).

        Args:
            ticket_content: Support ticket content.

        Returns:
            dict: Analysis result with severity, category, etc.
        """
        analysis_prompt = (
            f"Analyze this support ticket and provide a JSON response "
            f"with fields: severity (low|medium|high), "
            f"category (technical|billing|account|other), "
            f"suggested_action (escalate|auto_resolve|manual_review). "
            f"Ticket: {ticket_content}"
        )

        response_text = await self.generate_response(analysis_prompt)

        import json

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {
                "severity": "medium",
                "category": "other",
                "suggested_action": "manual_review",
            }

    async def suggest_resolution(self, ticket_id: uuid.UUID) -> str:
        """Suggest resolution for a ticket (READ-ONLY).

        Args:
            ticket_id: Support ticket identifier.

        Returns:
            str: Suggested resolution text.
        """
        suggestion_prompt = (
            f"Provide a helpful suggestion for resolving "
            f"support ticket {ticket_id}. "
            f"Focus on common solutions and best practices."
        )

        return await self.generate_response(suggestion_prompt)


def get_llm_service() -> LLMService:
    """Factory function to get configured LLM service.

    Returns:
        LLMService: Configured LLM service instance.

    Raises:
        ValueError: If LLM provider is not supported.
    """
    if settings.llm_provider.lower() in {"openai", "local", "openrouter"}:
        return OpenAILLMService()
    elif settings.llm_provider.lower() == "anthropic":
        return AnthropicLLMService()
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
