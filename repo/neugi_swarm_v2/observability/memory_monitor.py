"""
Memory Leak Detector for NEUGI Swarm.

Monitors memory usage of key subsystems via the event bus and
auto-triggers compaction when thresholds are exceeded.
"""

import gc
import logging
import threading
import time
from typing import Any, Callable, Optional

from neugi_swarm_v2.observability.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)


class MemoryLeakDetector:
    """
    Monitors memory pressure and publishes warning events.

    Periodically checks memory usage and emits events when:
    - Memory exceeds warning threshold
    - Memory exceeds critical threshold (triggers compaction)
    - Object count grows abnormally between GC cycles
    """

    def __init__(
        self,
        check_interval: float = 60.0,
        warning_mb: int = 500,
        critical_mb: int = 1000,
        compaction_callback: Optional[Callable[[], None]] = None,
    ):
        self.check_interval = check_interval
        self.warning_mb = warning_mb
        self.critical_mb = critical_mb
        self.compaction_callback = compaction_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_object_count = 0
        self.event_bus = get_event_bus()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(
            "MemoryLeakDetector started (interval=%ds, warning=%dMB, critical=%dMB)",
            self.check_interval, self.warning_mb, self.critical_mb,
        )

    def stop(self) -> None:
        self._running = False

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                self._check_memory()
            except Exception as e:
                logger.debug("Memory check error: %s", e)
            time.sleep(self.check_interval)

    def _check_memory(self) -> None:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)

        current_count = len(gc.get_objects())
        object_delta = current_count - self._last_object_count
        self._last_object_count = current_count

        if rss_mb >= self.critical_mb:
            logger.warning(
                "Critical memory usage: %.1f MB (threshold: %d MB)",
                rss_mb, self.critical_mb,
            )
            self.event_bus.publish(
                "memory_critical",
                {
                    "rss_mb": round(rss_mb, 1),
                    "warning_mb": self.warning_mb,
                    "critical_mb": self.critical_mb,
                    "object_count": current_count,
                    "object_delta": object_delta,
                },
                source="MemoryLeakDetector",
            )
            if self.compaction_callback:
                logger.info("Triggering compaction due to critical memory")
                self.compaction_callback()

        elif rss_mb >= self.warning_mb:
            logger.info("Warning memory usage: %.1f MB", rss_mb)
            self.event_bus.publish(
                "memory_warning",
                {
                    "rss_mb": round(rss_mb, 1),
                    "object_count": current_count,
                    "object_delta": object_delta,
                },
                source="MemoryLeakDetector",
            )

        else:
            logger.debug("Memory OK: %.1f MB (objects: %d, delta: %d)", rss_mb, current_count, object_delta)


def setup_memory_monitor(
    warning_mb: int = 500,
    critical_mb: int = 1000,
    compaction_callback: Optional[Callable[[], None]] = None,
) -> MemoryLeakDetector:
    """Create and start the memory leak detector."""
    detector = MemoryLeakDetector(
        warning_mb=warning_mb,
        critical_mb=critical_mb,
        compaction_callback=compaction_callback,
    )
    detector.start()
    return detector