"""Flow matcher - matches user questions with predefined support flows."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FlowMatch:
    """Result of flow matching."""

    flow_name: str
    matched_keywords: list[str]
    match_score: float
    flow_description: str
    needs_staff_approval: bool = False
    escalation_type: Optional[str] = None


class FlowMatcher:
    """Matches user questions with predefined support flows."""

    FLOWS = {
        "return_refund": {
            "keywords": [
                "возврат",
                "refund",
                "вернуть",
                "вернуть деньги",
                "деньги",
                "средства",
                "возврат средств",
            ],
            "description": "Процесс возврата и заморозки подписки",
            "patterns": [
                r"(возврат|refund|вернуть)",
                r"(деньги|средства|money)",
            ],
        },
        "career_assistance": {
            "keywords": [
                "карьер",
                "career",
                "резюме",
                "помощь",
                "assistance",
                "профессиональн",
                "разбор",
            ],
            "description": "Карьерная помощь и консультации экспертов",
            "patterns": [
                r"(карьер|career).*помощь",
                r"резюме.*разбор",
                r"(профессиональн|expert).*консультац",
            ],
        },
        "job_archival": {
            "keywords": [
                "архивиров",
                "archive",
                "вакансия",
                "удалить вакансию",
                "заблокир",
                "suppress",
            ],
            "description": "Архивация вакансий и их удаление из выдачи",
            "patterns": [
                r"(архивиров|archive).*вакансия",
                r"удалить.*вакансию",
                r"заблокир.*вакансию",
            ],
        },
        "referral_promo": {
            "keywords": [
                "реферальный",
                "промокод",
                "referal",
                "promo",
                "код",
                "друзья",
                "заработать",
                "скидка",
            ],
            "description": "Реферальный промокод и программа рефералов",
            "patterns": [
                r"(реферальн|referal).*код",
                r"промокод.*15%",
                r"друг.*скидка",
                r"заработать.*друг",
            ],
        },
        "review_promo": {
            "keywords": [
                "отзыв",
                "review",
                "промокод",
                "promo",
                "спасибо",
                "благодаря",
            ],
            "description": "Промокод за отзыв о сервисе",
            "patterns": [
                r"отзыв.*скидка",
                r"промокод.*отзыв",
                r"спасибо.*промокод",
            ],
        },
        "crypto_payment": {
            "keywords": [
                "крипто",
                "crypto",
                "bitcoin",
                "иностранн",
                "карта",
                "card",
                "платеж",
                "payment",
            ],
            "description": "Оплата криптовалютой или иностранной картой",
            "patterns": [
                r"(крипто|crypto|bitcoin)",
                r"(иностранн|foreign).*карт",
                r"платеж.*крипто",
            ],
        },
        "account_deletion": {
            "keywords": [
                "удалить аккаунт",
                "удаление",
                "delete account",
                "удали",
            ],
            "description": "Удаление аккаунта и данных",
            "patterns": [
                r"(удалить|delete).*аккаунт",
                r"удаление.*аккаунта",
            ],
        },
        "search_configuration": {
            "keywords": [
                "настроить",
                "поиск",
                "configure",
                "search",
                "ключевые слова",
                "keywords",
                "фильтры",
            ],
            "description": "Настройка поиска и фильтров вакансий",
            "patterns": [
                r"(настро|config).*поиск",
                r"ключевые слова",
                r"фильтр",
            ],
        },
        "subscription_management": {
            "keywords": [
                "подписка",
                "subscription",
                "тариф",
                "продлить",
                "автопродление",
                "отключить",
            ],
            "description": "Управление подпиской и автопродлением",
            "patterns": [
                r"подписка",
                r"(продлить|renew)",
                r"(автопродление|auto)",
            ],
        },
        "response_sending": {
            "keywords": [
                "отклик",
                "response",
                "отправка",
                "лимит",
                "дневной лимит",
                "не отправляется",
            ],
            "description": "Отправка откликов и лимиты",
            "patterns": [
                r"(отклик|response)",
                r"(не )?отправл",
                r"лимит",
            ],
        },
        "account_access": {
            "keywords": [
                "вход",
                "авторизация",
                "логин",
                "пароль",
                "не могу войти",
                "ошибка входа",
            ],
            "description": "Проблемы с входом в аккаунт",
            "patterns": [
                r"(вход|login|auth)",
                r"(не могу|can't) (войти|login)",
                r"ошибка.*вход",
            ],
        },
    }

    def _check_escalation_pattern(self, question: str) -> tuple[bool, Optional[str]]:
        """Check if question matches escalation pattern (bug/error + compensation/money).

        Args:
            question: User question text.

        Returns:
            Tuple of (is_escalation, escalation_type).
        """
        question_lower = question.lower()

        # Keywords for bugs/errors
        bug_keywords = [
            "баг",
            "ошибка",
            "bug",
            "error",
            "не работает",
            "сломал",
            "crash",
            "проблема",
        ]

        # Keywords for compensation/money
        compensation_keywords = [
            "компенсация",
            "возмещение",
            "деньги",
            "refund",
            "compensation",
            "money",
            "возврат",
            "выплата",
        ]

        # Check if both groups are present
        has_bug = any(kw in question_lower for kw in bug_keywords)
        has_compensation = any(kw in question_lower for kw in compensation_keywords)

        if has_bug and has_compensation:
            return True, "bug_with_compensation"
        return False, None

    def match(self, question: str) -> Optional[FlowMatch]:
        """Match question with a support flow.

        Args:
            question: User question text.

        Returns:
            FlowMatch if a flow is matched, None otherwise.
        """
        # STAGE 0: Check for escalations first (highest priority)
        is_escalation, escalation_type = self._check_escalation_pattern(question)
        if is_escalation:
            logger.info(
                f"ESCALATION DETECTED: {escalation_type} - requires staff approval"
            )
            escalation_match = FlowMatch(
                flow_name="escalation_bug_compensation",
                matched_keywords=["escalation_detected", escalation_type or ""],
                match_score=1.0,
                flow_description="Критическая эскалация: баг + компенсация (требует одобрения сотрудника)",
                needs_staff_approval=True,
                escalation_type=escalation_type,
            )
            return escalation_match

        best_match: Optional[FlowMatch] = None
        best_score = 0.0

        question_lower = question.lower()

        for flow_name, flow_config in self.FLOWS.items():
            matched_keywords: list[str] = []
            score = 0.0

            # Check keywords
            for keyword in flow_config["keywords"]:
                if keyword.lower() in question_lower:
                    matched_keywords.append(keyword)
                    score += 0.15

            # Check patterns
            for pattern in flow_config["patterns"]:
                if re.search(pattern, question_lower, re.IGNORECASE):
                    score += 0.25
                    if pattern not in matched_keywords:
                        matched_keywords.append(f"pattern:{pattern[:20]}")

            # Normalize score
            score = min(score, 1.0)

            if score > best_score and score >= 0.3:  # Minimum threshold
                best_score = score
                best_match = FlowMatch(
                    flow_name=flow_name,
                    matched_keywords=matched_keywords,
                    match_score=round(best_score, 2),
                    flow_description=flow_config["description"],
                )

        if best_match:
            logger.info(
                f"Flow matched: {best_match.flow_name} "
                f"(score: {best_match.match_score}, "
                f"keywords: {best_match.matched_keywords})"
            )
        else:
            logger.info(f"No flow matched for question: {question[:100]}")

        return best_match
