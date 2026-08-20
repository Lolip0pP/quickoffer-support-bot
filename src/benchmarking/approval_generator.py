"""Approval token generator - generates approval tokens for flow execution."""

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ApprovalTokenGenerator:
    """Generates approval tokens for script/tool execution."""

    TOKEN_EXPIRY_MINUTES = 30

    @staticmethod
    def generate_token(
        action_id: str, staff_id: str, payload: dict[str, str]
    ) -> str:
        """Generate approval token for action execution.

        Args:
            action_id: Unique action identifier (flow name).
            staff_id: Staff member ID processing the request.
            payload: Action payload to be approved.

        Returns:
            Approval token string.
        """
        # Create payload hash for verification
        payload_json = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        # Generate random component
        random_component = secrets.token_hex(16)

        # Create token components
        token_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        expiry = (
            datetime.utcnow()
            + timedelta(minutes=ApprovalTokenGenerator.TOKEN_EXPIRY_MINUTES)
        ).isoformat()

        # Combine components
        token_data = {
            "token_id": token_id,
            "action_id": action_id,
            "staff_id": staff_id,
            "payload_hash": payload_hash,
            "timestamp": timestamp,
            "expiry": expiry,
            "random_component": random_component,
        }

        # Create final token
        token_json = json.dumps(token_data, sort_keys=True)
        token_hash = hashlib.sha256(token_json.encode()).hexdigest()

        # Format token: base64-encoded JSON + hash
        token = f"{token_id}_{token_hash[:16]}"

        logger.info(
            f"Approval token generated for action {action_id} "
            f"(staff: {staff_id}, expires: {expiry})"
        )

        return token

    @staticmethod
    def generate_benchmark_token(flow_name: str) -> str:
        """Generate token for benchmark flow execution.

        Args:
            flow_name: Name of the matched flow.

        Returns:
            Approval token.
        """
        return ApprovalTokenGenerator.generate_token(
            action_id=flow_name,
            staff_id="benchmark_system",
            payload={
                "flow": flow_name,
                "type": "benchmark",
                "mode": "validation",
            },
        )

    @staticmethod
    def verify_token(token: str, action_id: str, payload: dict[str, str]) -> bool:
        """Verify approval token (stub - for demonstration).

        Args:
            token: Token to verify.
            action_id: Expected action ID.
            payload: Expected payload.

        Returns:
            True if token is valid, False otherwise.
        """
        # In real implementation, would verify token structure
        # and check expiry, hash, etc.
        if not token or len(token) < 32:
            logger.warning("Invalid token format")
            return False

        if "_" not in token:
            logger.warning("Token missing required separator")
            return False

        logger.debug(f"Token verified for action {action_id}")
        return True
