#!/usr/bin/env python3
"""
🤖 NEUGI MONITORING & METRICS
==============================

System monitoring and metrics:
- CPU, Memory, Disk, Network
- Process monitoring
- Alert thresholds
- Prometheus export

Version: 1.0
Date: March 15, 2026
"""

import os
import time
import json
import threading
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Metrics:
    """System metrics"""

    cpu_percent: float = 0
    memory_percent: float = 0
    memory_used: int = 0
    memory_total: int = 0
    disk_percent: float = 0
    disk_used: int = 0
    disk_total: int = 0
    network_sent: int = 0
    network_recv: int = 0
    timestamp: str = ""


@dataclass
class Alert:
    """Alert definition"""

    name: str
    metric: str
    threshold: float
    operator: str  # "gt", "lt", "eq"
    triggered: bool = False
    last_triggered: str = ""


class Monitoring:
    """
    NEUGI Monitoring & Metrics

    Real-time system monitoring
    """

    def __init__(self):
        self.metrics_history: List[Metrics] = []
        self.alerts: List[Alert] = []
        self.monitoring = False
        self._thread = None
        self._setup_default_alerts()

    def _setup_default_alerts(self):
        """Setup default alerts"""
        self.alerts = [
            Alert("High CPU", "cpu_percent", 90, "gt"),
            Alert("High Memory", "memory_percent", 90, "gt"),
            Alert("High Disk", "disk_percent", 95, "gt"),
        ]

    def get_metrics(self) -> Metrics:
        """Get current metrics"""
        try:
            import psutil

            metrics = Metrics()
            metrics.cpu_percent = psutil.cpu_percent()

            mem = psutil.virtual_memory()
            metrics.memory_percent = mem.percent
            metrics.memory_used = mem.used
            metrics.memory_total = mem.total

            disk = psutil.disk_usage("/")
            metrics.disk_percent = disk.percent
            metrics.disk_used = disk.used
            metrics.disk_total = disk.total

            net = psutil.net_io_counters()
            metrics.network_sent = net.bytes_sent
            metrics.network_recv = net.bytes_recv

            metrics.timestamp = datetime.now().isoformat()

            return metrics

        except ImportError:
            return Metrics(timestamp=datetime.now().isoformat())

    def record_metrics(self):
        """Record metrics to history"""
        metrics = self.get_metrics()
        self.metrics_history.append(metrics)

        # Keep only last 1000 records
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

        # Check alerts
        self._check_alerts(metrics)

        return metrics

    def _check_alerts(self, metrics: Metrics):
        """Check alert thresholds"""
        for alert in self.alerts:
            value = getattr(metrics, alert.metric, 0)

            triggered = False
            if alert.operator == "gt" and value > alert.threshold:
                triggered = True
            elif alert.operator == "lt" and value < alert.threshold:
                triggered = True
            elif alert.operator == "eq" and value == alert.threshold:
                triggered = True

            if triggered and not alert.triggered:
                alert.triggered = True
                alert.last_triggered = datetime.now().isoformat()
                print(f"⚠️ ALERT: {alert.name} - {alert.metric} = {value}")
            elif not triggered:
                alert.triggered = False

    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get metrics history"""
        history = self.metrics_history[-limit:]
        return [
            {
                "cpu": m.cpu_percent,
                "memory": m.memory_percent,
                "disk": m.disk_percent,
                "timestamp": m.timestamp,
            }
            for m in history
        ]

    def start_monitoring(self, interval: int = 5):
        """Start continuous monitoring"""
        if self.monitoring:
            return

        self.monitoring = True

        def monitor_loop():
            while self.monitoring:
                self.record_metrics()
                time.sleep(interval)

        self._thread = threading.Thread(target=monitor_loop, daemon=True)
        self._thread.start()

    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False

    def get_alerts(self) -> List[Dict]:
        """Get alert status"""
        return [
            {
                "name": a.name,
                "metric": a.metric,
                "threshold": a.threshold,
                "operator": a.operator,
                "triggered": a.triggered,
                "last_triggered": a.last_triggered,
            }
            for a in self.alerts
        ]

    def add_alert(self, name: str, metric: str, threshold: float, operator: str = "gt"):
        """Add custom alert"""
        self.alerts.append(Alert(name, metric, threshold, operator))

    def get_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        metrics = self.get_metrics()

        lines = [
            "# HELP neugi_cpu_percent CPU usage percentage",
            "# TYPE neugi_cpu_percent gauge",
            f"neugi_cpu_percent {metrics.cpu_percent}",
            "",
            "# HELP neugi_memory_percent Memory usage percentage",
            "# TYPE neugi_memory_percent gauge",
            f"neugi_memory_percent {metrics.memory_percent}",
            "",
            "# HELP neugi_disk_percent Disk usage percentage",
            "# TYPE neugi_disk_percent gauge",
            f"neugi_disk_percent {metrics.disk_percent}",
            "",
            "# HELP neugi_network_sent Network bytes sent",
            "# TYPE neugi_network_sent counter",
            f"neugi_network_sent {metrics.network_sent}",
            "",
            "# HELP neugi_network_recv Network bytes received",
            "# TYPE neugi_network_recv counter",
            f"neugi_network_recv {metrics.network_recv}",
        ]

        return "\n".join(lines)

    def get_top_processes(self, limit: int = 10) -> List[Dict]:
        """Get top processes by CPU"""
        try:
            import psutil

            processes = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    processes.append(
                        {
                            "pid": p.info["pid"],
                            "name": p.info["name"],
                            "cpu": p.info["cpu_percent"],
                            "memory": p.info["memory_percent"],
                        }
                    )
                except:
                    pass

            processes.sort(key=lambda x: x["cpu"] or 0, reverse=True)
            return processes[:limit]

        except ImportError:
            return []

    def get_system_info(self) -> Dict:
        """Get system info"""
        try:
            import psutil

            return {
                "platform": os.name,
                "cpu_count": psutil.cpu_count(),
                "cpu_count_logical": psutil.cpu_count(logical=True),
                "memory_total": psutil.virtual_memory().total,
                "disk_total": psutil.disk_usage("/").total,
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
            }
        except:
            return {"platform": os.name}


# ========== CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Monitoring")
    parser.add_argument(
        "action", choices=["metrics", "history", "alerts", "prometheus", "top", "info", "monitor"]
    )
    parser.add_argument("--limit", type=int, default=10, help="Limit results")
    parser.add_argument("--interval", type=int, default=5, help="Monitoring interval")

    args = parser.parse_args()

    monitor = Monitoring()

    if args.action == "metrics":
        m = monitor.get_metrics()
        print(f"\n📊 System Metrics")
        print("=" * 40)
        print(f"CPU: {m.cpu_percent:.1f}%")
        print(
            f"Memory: {m.memory_percent:.1f}% ({m.memory_used / 1024**3:.2f}GB / {m.memory_total / 1024**3:.2f}GB)"
        )
        print(
            f"Disk: {m.disk_percent:.1f}% ({m.disk_used / 1024**3:.2f}GB / {m.disk_total / 1024**3:.2f}GB)"
        )
        print(f"Network: ↑{m.network_sent / 1024**2:.2f}MB ↓{m.network_recv / 1024**2:.2f}MB")

    elif args.action == "history":
        history = monitor.get_history(args.limit)
        print(f"\n📈 Metrics History (last {len(history)} records)")
        for h in history[-5:]:
            print(f"  {h['timestamp'][:19]} | CPU: {h['cpu']:.1f}% | MEM: {h['memory']:.1f}%")

    elif args.action == "alerts":
        alerts = monitor.get_alerts()
        print(f"\n⚠️ Alerts")
        for a in alerts:
            status = "🔴 TRIGGERED" if a["triggered"] else "🟢 OK"
            print(f"  {status} {a['name']} ({a['metric']} {a['operator']} {a['threshold']}%)")

    elif args.action == "prometheus":
        print(monitor.get_prometheus_metrics())

    elif args.action == "top":
        processes = monitor.get_top_processes(args.limit)
        print(f"\n🔝 Top Processes")
        print(f"{'PID':<8} {'Name':<20} {'CPU':<10} {'Memory':<10}")
        for p in processes:
            print(f"{p['pid']:<8} {p['name'][:20]:<20} {p['cpu']:<10.1f} {p['memory']:<10.1f}")

    elif args.action == "info":
        info = monitor.get_system_info()
        print(f"\n💻 System Info")
        for k, v in info.items():
            print(f"  {k}: {v}")

    elif args.action == "monitor":
        print(f"\n🔄 Monitoring (Ctrl+C to stop)...")
        monitor.start_monitoring(args.interval)
        try:
            while True:
                m = monitor.get_metrics()
                print(
                    f"\rCPU: {m.cpu_percent:5.1f}% | MEM: {m.memory_percent:5.1f}% | DISK: {m.disk_percent:5.1f}%",
                    end="",
                )
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\nStopped")
            monitor.stop_monitoring()


if __name__ == "__main__":
    main()
