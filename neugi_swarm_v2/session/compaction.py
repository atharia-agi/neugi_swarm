"""
Context compaction engine for managing conversation token budgets.

Handles automatic summarization, truncation, and memory preservation
when sessions approach their token limits. Provides pre/post hooks,
timeout protection, and transcript hygiene.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CompactionStrategy(str, Enum):
    """Strategy for context compaction."""
    SUMMARIZE = "summarize"
    TRUNCATE = "truncate"
    HYBRID = "hybrid"


@dataclass
class CompactionConfig:
    """Configuration for the compaction engine."""
    token_threshold: int = 32768
    strategy: CompactionStrategy = CompactionStrategy.HYBRID
    timeout_seconds: float = 30.0
    preserve_system_prompt: bool = True
    preserve_recent_turns: int = 6
    max_summary_tokens: int = 2048
    enable_pre_hooks: bool = True
    enable_post_sync: bool = True
    enable_transcript_hygiene: bool = True
    silent_flush_turns: int = 1
    min_messages_before_compact: int = 10

    def __post_init__(self) -> None:
        if self.token_threshold <= 0:
            raise ValueError("token_threshold must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.preserve_recent_turns < 0:
            raise ValueError("preserve_recent_turns must be non-negative")


@dataclass
class CompactionResult:
    """Result of a compaction operation."""
    success: bool
    tokens_before: int
    tokens_after: int
    tokens_saved: int
    messages_before: int
    messages_after: int
    strategy_used: str
    summary: Optional[str] = None
    preserved_facts: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    timed_out: bool = False
    checkpoint_id: Optional[str] = None

    @property
    def compression_ratio(self) -> float:
        """Ratio of tokens saved to original count."""
        if self.tokens_before == 0:
            return 0.0
        return self.tokens_saved / self.tokens_before


class CompactionEngine:
    """
    Manages context compaction to keep sessions within token budgets.

    The compaction engine monitors token usage and triggers compaction
    when thresholds are exceeded. It supports multiple strategies,
    pre/post hooks for memory operations, and timeout protection.

    Lifecycle:
        1. Check if compaction is needed (token threshold exceeded)
        2. Acquire session write lock
        3. Run pre-compaction hooks (save important context)
        4. Perform silent memory flush turn
        5. Execute compaction strategy (summarize, truncate, or hybrid)
        6. Run post-compaction sync
        7. Perform transcript hygiene
        8. Release write lock

    Usage:
        engine = CompactionEngine(config)
        engine.register_pre_hook(my_hook)
        result = engine.compact(session, messages, token_count)
    """

    def __init__(self, config: Optional[CompactionConfig] = None) -> None:
        self.config = config or CompactionConfig()
        self._pre_hooks: List[Callable[["CompactionContext"], None]] = []
        self._post_hooks: List[Callable[["CompactionContext", CompactionResult], None]] = []
        self._history: List[CompactionResult] = []
        self._summarizer: Optional[Callable[[List[Dict[str, Any]]], str]] = None
        self._key_fact_extractor: Optional[Callable[[List[Dict[str, Any]]], List[str]]] = None

    def register_pre_hook(self, hook: Callable[["CompactionContext"], None]) -> None:
        """
        Register a hook to run before compaction begins.

        Pre-hooks are used to save important context to external memory
        before the conversation is summarized or truncated.
        """
        self._pre_hooks.append(hook)

    def register_post_hook(
        self, hook: Callable[["CompactionContext", CompactionResult], None]
    ) -> None:
        """Register a hook to run after compaction completes."""
        self._post_hooks.append(hook)

    def set_summarizer(self, func: Callable[[List[Dict[str, Any]]], str]) -> None:
        """
        Set the summarization function.

        The function takes a list of message dicts and returns a summary string.
        """
        self._summarizer = func

    def set_key_fact_extractor(
        self, func: Callable[[List[Dict[str, Any]]], List[str]]
    ) -> None:
        """
        Set the key fact extraction function.

        The function takes a list of message dicts and returns a list of
        important facts to preserve after compaction.
        """
        self._key_fact_extractor = func

    def needs_compaction(self, token_count: int, message_count: int) -> bool:
        """
        Determine if compaction should be triggered.

        Args:
            token_count: Current estimated token count.
            message_count: Current message count.

        Returns:
            True if compaction should be triggered.
        """
        if token_count >= self.config.token_threshold:
            return True
        return False

    def compact(
        self,
        session: Any,
        messages: List[Dict[str, Any]],
        token_count: int,
        system_prompt: Optional[str] = None,
    ) -> CompactionResult:
        """
        Execute compaction on the given messages.

        Args:
            session: The session object (for locking and metadata).
            messages: Current conversation messages.
            token_count: Current estimated token count.
            system_prompt: Optional system prompt to preserve.

        Returns:
            CompactionResult with details of the operation.
        """
        start_time = time.monotonic()
        messages_before = len(messages)

        if messages_before < self.config.min_messages_before_compact:
            logger.debug(
                "Skipping compaction: only %d messages (min=%d)",
                messages_before,
                self.config.min_messages_before_compact,
            )
            return CompactionResult(
                success=False,
                tokens_before=token_count,
                tokens_after=token_count,
                tokens_saved=0,
                messages_before=messages_before,
                messages_after=messages_before,
                strategy_used="none",
                error="Insufficient messages for compaction",
            )

        lock_owner = f"compaction-{uuid.uuid4().hex[:8]}"

        if not session.acquire_write_lock(lock_owner):
            return CompactionResult(
                success=False,
                tokens_before=token_count,
                tokens_after=token_count,
                tokens_saved=0,
                messages_before=messages_before,
                messages_after=messages_before,
                strategy_used="none",
                error="Failed to acquire write lock",
            )

        try:
            ctx = CompactionContext(
                session=session,
                messages=messages,
                token_count=token_count,
                system_prompt=system_prompt,
            )

            if self.config.enable_pre_hooks:
                self._run_pre_hooks(ctx)

            self._silent_memory_flush(ctx)

            result = self._execute_strategy(ctx)

            if result.success and self.config.enable_post_sync:
                self._post_compaction_sync(ctx, result)

            if result.success and self.config.enable_transcript_hygiene:
                self._transcript_hygiene(ctx, result)

            result.duration_seconds = time.monotonic() - start_time

            if self.config.enable_post_hooks:
                self._run_post_hooks(ctx, result)

            session.increment_compaction_count()
            self._history.append(result)

            logger.info(
                "Compaction complete: %d -> %d tokens (%.1f%% saved, strategy=%s)",
                result.tokens_before,
                result.tokens_after,
                result.compression_ratio * 100,
                result.strategy_used,
            )

            return result

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error("Compaction failed after %.2fs: %s", elapsed, e)
            return CompactionResult(
                success=False,
                tokens_before=token_count,
                tokens_after=token_count,
                tokens_saved=0,
                messages_before=messages_before,
                messages_after=messages_before,
                strategy_used=self.config.strategy.value,
                error=str(e),
                duration_seconds=elapsed,
            )
        finally:
            session.release_write_lock(lock_owner)

    def _run_pre_hooks(self, ctx: "CompactionContext") -> None:
        """Execute all registered pre-compaction hooks."""
        for hook in self._pre_hooks:
            try:
                hook(ctx)
            except Exception:
                logger.exception("Error in pre-compaction hook")

    def _run_post_hooks(
        self, ctx: "CompactionContext", result: CompactionResult
    ) -> None:
        """Execute all registered post-compaction hooks."""
        for hook in self._post_hooks:
            try:
                hook(ctx, result)
            except Exception:
                logger.exception("Error in post-compaction hook")

    def _silent_memory_flush(self, ctx: "CompactionContext") -> None:
        """
        Perform a silent memory flush turn before summarization.

        This gives the system a chance to persist important state
        to external memory before context is lost.
        """
        for _ in range(self.config.silent_flush_turns):
            try:
                session = ctx.session
                if hasattr(session, "key_space") and session.key_space:
                    if hasattr(session, "save_metadata"):
                        session.save_metadata()
            except Exception:
                logger.exception("Error during silent memory flush")

    def _execute_strategy(self, ctx: "CompactionContext") -> CompactionResult:
        """Execute the configured compaction strategy."""
        strategy = self.config.strategy

        if strategy == CompactionStrategy.SUMMARIZE:
            return self._strategy_summarize(ctx)
        elif strategy == CompactionStrategy.TRUNCATE:
            return self._strategy_truncate(ctx)
        elif strategy == CompactionStrategy.HYBRID:
            return self._strategy_hybrid(ctx)
        else:
            return CompactionResult(
                success=False,
                tokens_before=ctx.token_count,
                tokens_after=ctx.token_count,
                tokens_saved=0,
                messages_before=len(ctx.messages),
                messages_after=len(ctx.messages),
                strategy_used=strategy.value,
                error=f"Unknown strategy: {strategy}",
            )

    def _strategy_summarize(self, ctx: "CompactionContext") -> CompactionResult:
        """
        Summarize older messages while preserving recent context.

        Keeps the system prompt and recent turns intact, replaces
        older conversation with a summary.
        """
        messages = ctx.messages
        preserve_count = self.config.preserve_recent_turns * 2

        if preserve_count >= len(messages):
            preserve_count = max(2, len(messages) - 2)

        to_summarize = messages[:-preserve_count] if preserve_count < len(messages) else []
        to_keep = messages[-preserve_count:] if preserve_count > 0 else []

        summary = ""
        if to_summarize and self._summarizer:
            try:
                deadline = time.monotonic() + self.config.timeout_seconds
                summary = self._summarize_with_timeout(to_summarize, deadline)
            except TimeoutError:
                summary = "[Conversation summarized - details omitted due to timeout]"
                logger.warning("Summarization timed out, using placeholder")
        elif to_summarize:
            summary = f"[{len(to_summarize)} messages summarized]"

        facts = []
        if to_summarize and self._key_fact_extractor:
            try:
                facts = self._key_fact_extractor(to_summarize)
            except Exception:
                logger.exception("Key fact extraction failed")

        summary_message = {
            "role": "system",
            "content": f"Previous conversation summary: {summary}",
            "metadata": {
                "compacted": True,
                "original_message_count": len(to_summarize),
                "compacted_at": datetime.now(timezone.utc).isoformat(),
                "preserved_facts": facts,
            },
        }

        new_messages = []
        if self.config.preserve_system_prompt and ctx.system_prompt:
            new_messages.append({"role": "system", "content": ctx.system_prompt})

        new_messages.append(summary_message)
        new_messages.extend(to_keep)

        estimated_tokens = self._estimate_tokens(new_messages)

        return CompactionResult(
            success=True,
            tokens_before=ctx.token_count,
            tokens_after=estimated_tokens,
            tokens_saved=ctx.token_count - estimated_tokens,
            messages_before=len(messages),
            messages_after=len(new_messages),
            strategy_used="summarize",
            summary=summary,
            preserved_facts=facts,
        )

    def _strategy_truncate(self, ctx: "CompactionContext") -> CompactionResult:
        """
        Truncate older messages to fit within token budget.

        Keeps the system prompt and most recent messages, drops
        the oldest messages until under threshold.
        """
        messages = ctx.messages
        target_tokens = int(self.config.token_threshold * 0.7)

        new_messages = []
        if self.config.preserve_system_prompt and ctx.system_prompt:
            new_messages.append({"role": "system", "content": ctx.system_prompt})

        recent_messages = messages[-self.config.preserve_recent_turns * 2:]
        if not recent_messages:
            recent_messages = messages[-2:] if len(messages) >= 2 else messages

        current_tokens = self._estimate_tokens(new_messages + recent_messages)

        if current_tokens > target_tokens:
            while len(recent_messages) > 2 and current_tokens > target_tokens:
                recent_messages = recent_messages[1:]
                current_tokens = self._estimate_tokens(new_messages + recent_messages)

        new_messages.extend(recent_messages)
        estimated_tokens = self._estimate_tokens(new_messages)

        return CompactionResult(
            success=True,
            tokens_before=ctx.token_count,
            tokens_after=estimated_tokens,
            tokens_saved=ctx.token_count - estimated_tokens,
            messages_before=len(messages),
            messages_after=len(new_messages),
            strategy_used="truncate",
        )

    def _strategy_hybrid(self, ctx: "CompactionContext") -> CompactionResult:
        """
        Hybrid strategy: summarize first, then truncate if still over budget.

        Combines the benefits of summarization (context preservation) with
        truncation (guaranteed token reduction).
        """
        result = self._strategy_summarize(ctx)

        if result.success and result.tokens_after > self.config.token_threshold:
            ctx.messages = self._rebuild_messages_from_result(ctx, result)
            truncate_result = self._strategy_truncate(ctx)
            truncate_result.strategy_used = "hybrid"
            truncate_result.summary = result.summary
            truncate_result.preserved_facts = result.preserved_facts
            return truncate_result

        result.strategy_used = "hybrid"
        return result

    def _rebuild_messages_from_result(
        self, ctx: "CompactionContext", result: CompactionResult
    ) -> List[Dict[str, Any]]:
        """Rebuild message list from a compaction result for further processing."""
        new_messages = []
        if self.config.preserve_system_prompt and ctx.system_prompt:
            new_messages.append({"role": "system", "content": ctx.system_prompt})

        if result.summary:
            new_messages.append({
                "role": "system",
                "content": f"Previous conversation summary: {result.summary}",
            })

        preserve_count = self.config.preserve_recent_turns * 2
        new_messages.extend(ctx.messages[-preserve_count:])
        return new_messages

    def _summarize_with_timeout(
        self, messages: List[Dict[str, Any]], deadline: float
    ) -> str:
        """Run summarization with timeout protection."""
        if self._summarizer is None:
            return f"[{len(messages)} messages summarized]"

        if time.monotonic() >= deadline:
            raise TimeoutError("Summarization deadline exceeded")

        try:
            return self._summarizer(messages)
        except Exception as e:
            logger.error("Summarizer error: %s", e)
            return f"[{len(messages)} messages summarized - error: {e}]"

    def _post_compaction_sync(
        self, ctx: "CompactionContext", result: CompactionResult
    ) -> None:
        """
        Sync session state after compaction.

        Updates token estimates and persists session metadata.
        """
        try:
            session = ctx.session
            if hasattr(session, "increment_message_count"):
                token_delta = result.tokens_after - ctx.token_count
                session.increment_message_count(token_delta)
            if hasattr(session, "save_metadata"):
                session.save_metadata()
        except Exception:
            logger.exception("Post-compaction sync failed")

    def _transcript_hygiene(
        self, ctx: "CompactionContext", result: CompactionResult
    ) -> None:
        """
        Clean up transcript artifacts after compaction.

        Removes old tool results that are no longer referenced,
        keeps only summaries of removed content.
        """
        try:
            session = ctx.session
            if hasattr(session, "metadata") and session.metadata.transcript_path:
                from .transcript import Transcript
                transcript = Transcript(session.metadata.transcript_path)
                transcript.prune_old_tool_results(keep_recent=10)
        except Exception:
            logger.exception("Transcript hygiene failed")

    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Estimate token count for a list of messages.

        Uses a simple character-based approximation (4 chars ~ 1 token).
        For production use, replace with a proper tokenizer.
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            total_chars += len(content)
            name = msg.get("name", "")
            total_chars += len(name)
        return max(1, total_chars // 4)

    def get_history(self) -> List[CompactionResult]:
        """Get the history of compaction operations."""
        return list(self._history)

    def get_stats(self) -> Dict[str, Any]:
        """Get compaction engine statistics."""
        if not self._history:
            return {
                "total_compactions": 0,
                "successful_compactions": 0,
                "failed_compactions": 0,
                "total_tokens_saved": 0,
                "average_compression_ratio": 0.0,
            }

        successful = [r for r in self._history if r.success]
        failed = [r for r in self._history if not r.success]

        return {
            "total_compactions": len(self._history),
            "successful_compactions": len(successful),
            "failed_compactions": len(failed),
            "total_tokens_saved": sum(r.tokens_saved for r in successful),
            "average_compression_ratio": (
                sum(r.compression_ratio for r in successful) / len(successful)
                if successful else 0.0
            ),
            "last_compaction": self._history[-1].to_dict() if self._history else None,
        }


@dataclass
class CompactionContext:
    """
    Context object passed to compaction hooks.

    Provides access to the session, messages, and token state
    during compaction operations.
    """
    session: Any
    messages: List[Dict[str, Any]]
    token_count: int
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
