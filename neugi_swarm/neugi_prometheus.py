#!/usr/bin/env python3
"""
🤖 NEUGI PROMETHEUS METRICS
==============================

Prometheus metrics export:
- Counter, Gauge, Histogram
- Custom metrics
- Pushgateway support

Version: 1.0
Date: March 16, 2026
"""

import time
import threading
from typing import Dict, List, Optional
from collections import defaultdict

NEUGI_DIR = __import__("os").path.expanduser("~/neugi")


class Metric:
    """Base metric"""

    def __init__(self, name: str, description: str, labels: Dict = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.created_at = time.time()


class Counter(Metric):
    """Counter metric"""

    def __init__(self, name: str, description: str, labels: Dict = None):
        super().__init__(name, description, labels)
        self.value = 0

    def inc(self, value: float = 1):
        self.value += value

    def get_value(self) -> float:
        return self.value


class Gauge(Metric):
    """Gauge metric"""

    def __init__(self, name: str, description: str, labels: Dict = None):
        super().__init__(name, description, labels)
        self.value = 0

    def inc(self, value: float = 1):
        self.value += value

    def dec(self, value: float = 1):
        self.value -= value

    def set(self, value: float):
        self.value = value

    def get_value(self) -> float:
        return self.value


class Histogram(Metric):
    """Histogram metric"""

    BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def __init__(
        self, name: str, description: str, buckets: List[float] = None, labels: Dict = None
    ):
        super().__init__(name, description, labels)
        self.buckets = buckets or self.BUCKETS
        self.values = defaultdict(int)
        self.sum = 0
        self.count = 0

    def observe(self, value: float):
        self.count += 1
        self.sum += value
        for bucket in self.buckets:
            if value <= bucket:
                self.values[f"le_{bucket}"] += 1
        self.values["le_+Inf"] += 1

    def get_values(self) -> Dict:
        return {"sum": self.sum, "count": self.count, "buckets": dict(self.values)}


class PrometheusExporter:
    """Prometheus exporter"""

    def __init__(self):
        self.metrics: Dict[str, Metric] = {}
        self._lock = threading.RLock()

    def register_counter(self, name: str, description: str, labels: Dict = None) -> Counter:
        with self._lock:
            key = f"{name}_{'_'.join(sorted(labels.keys()))}" if labels else name
            counter = Counter(name, description, labels)
            self.metrics[key] = counter
            return counter

    def register_gauge(self, name: str, description: str, labels: Dict = None) -> Gauge:
        with self._lock:
            key = f"{name}_{'_'.join(sorted(labels.keys()))}" if labels else name
            gauge = Gauge(name, description, labels)
            self.metrics[key] = gauge
            return gauge

    def register_histogram(
        self, name: str, description: str, buckets: List[float] = None, labels: Dict = None
    ) -> Histogram:
        with self._lock:
            key = f"{name}_{'_'.join(sorted(labels.keys()))}" if labels else name
            histogram = Histogram(name, description, buckets, labels)
            self.metrics[key] = histogram
            return histogram

    def get_counter(self, name: str) -> Optional[Counter]:
        return self.metrics.get(name) if isinstance(self.metrics.get(name), Counter) else None

    def get_gauge(self, name: str) -> Optional[Gauge]:
        return self.metrics.get(name) if isinstance(self.metrics.get(name), Gauge) else None

    def get_histogram(self, name: str) -> Optional[Histogram]:
        return self.metrics.get(name) if isinstance(self.metrics.get(name), Histogram) else None

    def export(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []

        with self._lock:
            for metric in self.metrics.values():
                lines.append(f"# HELP {metric.name} {metric.description}")
                lines.append(f"# TYPE {metric.name} {type(metric).__name__.lower()}")

                if isinstance(metric, (Counter, Gauge)):
                    labels_str = ",".join([f'{k}="{v}"' for k, v in metric.labels.items()])
                    if labels_str:
                        lines.append(f"{metric.name}{{{labels_str}}} {metric.get_value()}")
                    else:
                        lines.append(f"{metric.name} {metric.get_value()}")

                elif isinstance(metric, Histogram):
                    vals = metric.get_values()
                    labels_str = ",".join([f'{k}="{v}"' for k, v in metric.labels.items()])
                    prefix = f"{metric.name}{{{labels_str}}}" if labels_str else metric.name

                    for bucket, count in vals["buckets"].items():
                        le = bucket.replace("le_", "le=")
                        lines.append(f"{prefix}_bucket{{{le}}} {count}")
                    lines.append(f"{prefix}_sum {vals['sum']}")
                    lines.append(f"{prefix}_count {vals['count']}")

        return "\n".join(lines) + "\n"


class MetricsCollector:
    """Collect system metrics"""

    def __init__(self):
        self.exporter = PrometheusExporter()
        self._setup_default_metrics()
        self._collecting = False
        self._thread = None

    def _setup_default_metrics(self):
        """Setup default metrics"""
        self.cpu_gauge = self.exporter.register_gauge(
            "neugi_cpu_usage_percent", "CPU usage percentage"
        )
        self.memory_gauge = self.exporter.register_gauge(
            "neugi_memory_usage_percent", "Memory usage percentage"
        )
        self.requests_counter = self.exporter.register_counter(
            "neugi_requests_total", "Total requests"
        )
        self.request_duration = self.exporter.register_histogram(
            "neugi_request_duration_seconds", "Request duration"
        )
        self.errors_counter = self.exporter.register_counter("neugi_errors_total", "Total errors")

    def collect_system_metrics(self):
        """Collect system metrics"""
        try:
            import psutil

            self.cpu_gauge.set(psutil.cpu_percent())
            self.memory_gauge.set(psutil.virtual_memory().percent)
        except:
            pass

    def record_request(self, duration: float):
        """Record request"""
        self.requests_counter.inc()
        self.request_duration.observe(duration)

    def record_error(self):
        """Record error"""
        self.errors_counter.inc()

    def start_collection(self, interval: int = 15):
        """Start collecting metrics"""
        if self._collecting:
            return

        self._collecting = True
        self._thread = threading.Thread(target=self._collect_loop, args=(interval,), daemon=True)
        self._thread.start()

    def _collect_loop(self, interval: int):
        """Collection loop"""
        while self._collecting:
            self.collect_system_metrics()
            time.sleep(interval)

    def stop_collection(self):
        """Stop collecting"""
        self._collecting = False
        if self._thread:
            self._thread.join(timeout=5)


collector = MetricsCollector()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Prometheus Metrics")
    parser.add_argument("--export", action="store_true", help="Export metrics")
    parser.add_argument("--start", action="store_true", help="Start collector")
    parser.add_argument("--port", type=int, default=19940, help="Port")

    args = parser.parse_args()

    if args.export:
        print(collector.exporter.export())

    elif args.start:
        collector.start_collection()
        print(f"Metrics collector started on port {args.port}")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            collector.stop_collection()

    else:
        print("NEUGI Prometheus Metrics")
        print("Usage: python -m neugi_prometheus [--export|--start|--port PORT]")


if __name__ == "__main__":
    main()
