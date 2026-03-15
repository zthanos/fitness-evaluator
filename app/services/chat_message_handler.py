"""Chat Message Handler - Thin Coordinator with Dual Runtime Support

Coordinates between API layer, ChatSessionService, and ChatAgent.
Supports feature-flag-based runtime selection between CE and legacy paths,
including per-user pilot rollout routing (Phase 6.6).

Requirements: 3.1, 3.2 (Phase 3), 6.1, 6.6 (Phase 6)
"""
import time
import logging
from typing import Dict, Any, Optional

from app.config import Settings, get_settings
from app.services.chat_session_service import ChatSessionService
from app.services.chat_agent import ChatAgent
from app.services.runtime_comparison import run_comparison
from app.services.pilot_rollout import PilotUserRegistry

logger = logging.getLogger(__name__)


class ChatMessageHandler:
    """Thin coordinator with dual runtime support.

    Selects between CE and legacy chat runtimes based on the
    ``USE_CE_CHAT_RUNTIME`` feature flag or per-user pilot routing.
    When the flag is *True* or the user is in the pilot group,
    the handler delegates to ``ChatAgent`` (CE path).  Otherwise
    it falls back to the legacy ``ChatService`` path.

    Attributes:
        runtime: ``"ce"`` or ``"legacy"`` — which path is active.
    """

    def __init__(
        self,
        db,
        session_service: ChatSessionService,
        agent: Optional[ChatAgent] = None,
        user_id: int = 0,
        session_id: int = 0,
        settings: Optional[Settings] = None,
        invocation_logger=None,
        pilot_registry: Optional[PilotUserRegistry] = None,
    ):
        self.db = db
        self.session_service = session_service
        self.user_id = user_id
        self.session_id = session_id
        self._settings = settings or get_settings()
        self._invocation_logger = invocation_logger
        self._pilot_registry = pilot_registry or PilotUserRegistry(self._settings)

        # Determine active runtime from feature flags + pilot routing
        use_ce = self._pilot_registry.should_use_ce_runtime(self.user_id)

        if use_ce:
            if agent is None:
                raise ValueError(
                    "ChatAgent is required when CE runtime is enabled "
                    "(global flag or pilot user)"
                )
            self.agent = agent
            self.runtime = "ce"
        else:
            self.agent = agent  # may be None in legacy mode
            self.runtime = "legacy"

        logger.info(
            "ChatMessageHandler initialised with runtime=%s",
            self.runtime,
            extra={
                "runtime": self.runtime,
                "user_id": self.user_id,
                "session_id": self.session_id,
                "use_ce_chat_runtime": self._settings.USE_CE_CHAT_RUNTIME,
                "legacy_chat_enabled": self._settings.LEGACY_CHAT_ENABLED,
                "is_pilot_user": self._pilot_registry.is_pilot_user(self.user_id),
            },
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        user_message: str,
        max_tool_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Handle a chat message, routing to the active runtime.

        Args:
            user_message: The athlete's message text.
            max_tool_iterations: Forwarded to agent (CE path only).

        Returns:
            Dict with at least ``content``, ``latency_ms``, and a
            ``runtime`` key indicating which path was used.
        """
        # Comparison mode: invoke both runtimes and return the primary result
        if self._settings.ENABLE_RUNTIME_COMPARISON and self.agent is not None:
            return await self._handle_comparison(user_message, max_tool_iterations)

        if self.runtime == "ce":
            return await self._handle_ce(user_message, max_tool_iterations)
        return await self._handle_legacy(user_message)

    # ------------------------------------------------------------------
    # Comparison mode
    # ------------------------------------------------------------------

    async def _handle_comparison(
        self,
        user_message: str,
        max_tool_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Run both runtimes, log the comparison, return the primary result.

        The primary result is determined by the ``USE_CE_CHAT_RUNTIME``
        flag — the comparison is purely observational and does not change
        which response the caller receives.
        """
        report = await run_comparison(
            user_message=user_message,
            session_id=self.session_id,
            user_id=self.user_id,
            ce_handler_fn=lambda msg: self._handle_ce(msg, max_tool_iterations),
            legacy_handler_fn=lambda msg: self._handle_legacy(msg),
            invocation_logger=self._invocation_logger,
        )

        logger.info(
            "Comparison report: %s",
            report.summary(),
            extra={
                "user_id": self.user_id,
                "session_id": self.session_id,
                "comparison": report.to_dict(),
            },
        )

        # Return whichever runtime is the active primary
        if self.runtime == "ce" and report.ce_result and report.ce_result.error is None:
            return {
                "content": report.ce_result.content,
                "tool_calls_made": report.ce_result.tool_calls_made,
                "iterations": report.ce_result.iterations,
                "latency_ms": report.ce_result.latency_ms,
                "context_token_count": report.ce_result.context_token_count,
                "ce_context_used": True,
                "runtime": "ce",
                "comparison": report.to_dict(),
            }

        if report.legacy_result and report.legacy_result.error is None:
            return {
                "content": report.legacy_result.content,
                "tool_calls_made": report.legacy_result.tool_calls_made,
                "iterations": report.legacy_result.iterations,
                "latency_ms": report.legacy_result.latency_ms,
                "context_token_count": report.legacy_result.context_token_count,
                "ce_context_used": False,
                "runtime": "legacy",
                "comparison": report.to_dict(),
            }

        # Both failed — raise the CE error if available
        error_msg = (
            report.ce_result.error
            if report.ce_result and report.ce_result.error
            else (report.legacy_result.error if report.legacy_result else "unknown")
        )
        raise RuntimeError(f"Both runtimes failed during comparison: {error_msg}")

    # ------------------------------------------------------------------
    # CE runtime path
    # ------------------------------------------------------------------

    async def _handle_ce(
        self,
        user_message: str,
        max_tool_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Execute via ChatAgent (Context Engineering path)."""
        start_time = time.time()

        try:
            conversation_history = self.session_service.get_active_buffer(
                self.session_id
            )

            result = await self.agent.execute(
                user_message=user_message,
                session_id=self.session_id,
                user_id=self.user_id,
                conversation_history=conversation_history,
            )

            self.session_service.append_messages(
                self.session_id,
                user_message,
                result["content"],
            )

            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                "CE runtime handled message in %.0f ms",
                latency_ms,
                extra={
                    "runtime": "ce",
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "latency_ms": latency_ms,
                    "tool_calls": result.get("tool_calls_made", 0),
                },
            )

            if latency_ms > 3000:
                logger.warning(
                    "CE chat latency exceeded 3 s target: %.0f ms",
                    latency_ms,
                    extra={
                        "runtime": "ce",
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                    },
                )

            return {
                "content": result["content"],
                "tool_calls_made": result.get("tool_calls_made", 0),
                "iterations": result.get("iterations", 0),
                "latency_ms": latency_ms,
                "context_token_count": result.get("context_token_count", 0),
                "ce_context_used": True,
                "runtime": "ce",
            }

        except Exception as e:
            logger.error(
                "CE runtime error: %s",
                e,
                extra={
                    "runtime": "ce",
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                },
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------
    # Legacy runtime path
    # ------------------------------------------------------------------

    async def _handle_legacy(self, user_message: str) -> Dict[str, Any]:
        """Execute via legacy ChatService path."""
        start_time = time.time()

        try:
            from app.services.chat_service import ChatService

            chat_service = ChatService(self.db)

            # Build conversation from session buffer
            conversation_history = self.session_service.get_active_buffer(
                self.session_id
            )
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in conversation_history
            ]
            messages.append({"role": "user", "content": user_message})

            response = await chat_service.get_chat_response(messages)

            assistant_content = response.get("content", "")

            self.session_service.append_messages(
                self.session_id,
                user_message,
                assistant_content,
            )

            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                "Legacy runtime handled message in %.0f ms",
                latency_ms,
                extra={
                    "runtime": "legacy",
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "latency_ms": latency_ms,
                },
            )

            if latency_ms > 3000:
                logger.warning(
                    "Legacy chat latency exceeded 3 s target: %.0f ms",
                    latency_ms,
                    extra={
                        "runtime": "legacy",
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                    },
                )

            return {
                "content": assistant_content,
                "tool_calls_made": response.get("iterations", 0),
                "iterations": response.get("iterations", 0),
                "latency_ms": latency_ms,
                "context_token_count": 0,
                "ce_context_used": False,
                "runtime": "legacy",
            }

        except Exception as e:
            logger.error(
                "Legacy runtime error: %s",
                e,
                extra={
                    "runtime": "legacy",
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                },
                exc_info=True,
            )
            raise
