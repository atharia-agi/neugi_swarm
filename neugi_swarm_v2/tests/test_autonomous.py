"""
Tests for the autonomous subsystem.

Covers: IdleObserver, ProactiveDecisionEngine, SelfDirectedExecutor,
ActivityReporter, and AutonomousLoop.
"""

from __future__ import annotations

import sqlite3
import tempfile
import time
from pathlib import Path

import pytest
from autonomous.decision import (
    Decision,
    DecisionCriteria,
    DecisionOutcome,
    DecisionType,
    ProactiveDecisionEngine,
)
from autonomous.executor import (
    ExecutionContext,
    ExecutionResult,
    ExecutionType,
    SelfDirectedExecutor,
)
from autonomous.loop_engine import (
    AutonomousLoop,
    LoopConfig,
    LoopResult,
    LoopState,
)
from autonomous.observer import (
    IdleObserver,
    Observation,
    ObservationType,
)
from autonomous.reporter import (
    ActivityReporter,
    ReportChannel,
    ReportSeverity,
)
from autonomous.research_engine import (
    ResearchConfig,
    ResearchEngine,
    ResearchFinding,
    ResearchReport,
    ResearchSource,
)

# -- Fixtures -----------------------------------------------------------------

@pytest.fixture
def temp_memory_db():
    """Create a temporary memory database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize minimal schema
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE memory_entries (
            id INTEGER PRIMARY KEY,
            content TEXT,
            role TEXT,
            created_at REAL,
            tags TEXT
        );
        CREATE TABLE entry_tags (
            entry_id INTEGER,
            tag TEXT
        );
    """)
    conn.close()

    yield db_path

    # On Windows, force garbage collection before unlink
    import gc
    gc.collect()
    try:
        Path(db_path).unlink(missing_ok=True)
    except PermissionError:
        pass  # Windows file lock; tempfile will clean up eventually


@pytest.fixture
def temp_goals_db():
    """Create a temporary goals database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE goals (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            updated_at REAL,
            metadata TEXT,
            parent_id TEXT
        );
    """)
    conn.close()

    yield db_path

    import gc
    gc.collect()
    try:
        Path(db_path).unlink(missing_ok=True)
    except PermissionError:
        pass


# -- IdleObserver Tests -------------------------------------------------------

class TestIdleObserver:
    def test_init(self, temp_memory_db):
        observer = IdleObserver(memory_db_path=temp_memory_db)
        assert observer.memory_db_path == temp_memory_db

    def test_observe_empty(self, temp_memory_db):
        observer = IdleObserver(memory_db_path=temp_memory_db)
        observations = observer.observe()
        assert isinstance(observations, list)

    def test_memory_signal(self, temp_memory_db):
        # Seed with data
        conn = sqlite3.connect(temp_memory_db)
        now = time.time()
        for i in range(10):
            conn.execute(
                "INSERT INTO memory_entries (content, role, created_at, tags) VALUES (?, ?, ?, ?)",
                (f"test content {i}", "user", now, "test"),
            )
            conn.execute(
                "INSERT INTO entry_tags (entry_id, tag) VALUES (?, ?)",
                (i + 1, "python"),
            )
        conn.commit()
        conn.close()

        observer = IdleObserver(memory_db_path=temp_memory_db)
        signal = observer._get_memory_signal()
        assert signal.memory_count_24h == 10
        assert len(signal.top_topics) > 0

    def test_goal_signal(self, temp_memory_db, temp_goals_db):
        conn = sqlite3.connect(temp_goals_db)
        now = time.time()
        conn.execute(
            "INSERT INTO goals (id, title, status, updated_at, metadata) VALUES (?, ?, ?, ?, ?)",
            ("g1", "Test Goal", "active", now - 90000, '{}'),
        )
        conn.commit()
        conn.close()

        observer = IdleObserver(
            memory_db_path=temp_memory_db,
            goals_db_path=temp_goals_db,
        )
        signal = observer._get_goal_signal()
        assert signal.total_count == 1
        assert len(signal.stuck_goals) == 1

    def test_observation_priority_score(self):
        obs = Observation(
            obs_type=ObservationType.MEMORY_TREND,
            source="memory",
            description="test",
            confidence=1.0,
            urgency=1.0,
            value=1.0,
        )
        assert obs.priority_score == 1.0

        obs2 = Observation(
            obs_type=ObservationType.MEMORY_TREND,
            source="memory",
            description="test",
            confidence=0.5,
            urgency=0.5,
            value=0.5,
        )
        assert obs2.priority_score == 0.125


# -- ProactiveDecisionEngine Tests --------------------------------------------

class TestProactiveDecisionEngine:
    def test_decide_no_observations(self):
        engine = ProactiveDecisionEngine()
        decisions = engine.decide([])
        assert decisions == []

    def test_decide_low_confidence_rejected(self):
        engine = ProactiveDecisionEngine()
        obs = Observation(
            obs_type=ObservationType.MEMORY_TREND,
            source="memory",
            description="low confidence",
            confidence=0.1,  # Below default 0.5
            urgency=0.9,
            value=0.9,
        )
        decisions = engine.decide([obs])
        assert len(decisions) == 1
        assert decisions[0].outcome == DecisionOutcome.REJECTED

    def test_decide_approved(self):
        engine = ProactiveDecisionEngine()
        obs = Observation(
            obs_type=ObservationType.MEMORY_TREND,
            source="memory",
            description="high confidence memory trend",
            confidence=0.9,
            urgency=0.8,
            value=0.8,
        )
        decisions = engine.decide([obs])
        assert len(decisions) == 1
        assert decisions[0].outcome == DecisionOutcome.APPROVED
        assert decisions[0].decision_type == DecisionType.CONSOLIDATE_MEMORY

    def test_decide_risk_escalation(self):
        engine = ProactiveDecisionEngine(criteria=DecisionCriteria(max_risk=0.1))
        obs = Observation(
            obs_type=ObservationType.SYSTEM_HEALTH,
            source="health",
            description="critical system issue",
            confidence=0.95,
            urgency=0.9,
            value=0.9,
        )
        decisions = engine.decide([obs])
        assert len(decisions) == 1
        assert decisions[0].outcome == DecisionOutcome.ESCALATED

    def test_rate_limiting(self):
        engine = ProactiveDecisionEngine(
            criteria=DecisionCriteria(max_daily_autonomous_actions=1),
            today_action_count=1,
        )
        obs = Observation(
            obs_type=ObservationType.MEMORY_TREND,
            source="memory",
            description="test",
            confidence=0.9,
            urgency=0.5,
            value=0.5,
        )
        decisions = engine.decide([obs])
        approved = [d for d in decisions if d.outcome == DecisionOutcome.APPROVED]
        assert len(approved) == 0  # Deferred due to rate limit

    def test_stats(self):
        engine = ProactiveDecisionEngine()
        obs = Observation(
            obs_type=ObservationType.MEMORY_TREND,
            source="memory",
            description="test",
            confidence=0.9,
            urgency=0.5,
            value=0.5,
        )
        engine.decide([obs])
        stats = engine.get_stats()
        assert stats["total_evaluated"] == 1
        assert stats["approved"] == 1


# -- SelfDirectedExecutor Tests -----------------------------------------------

class TestSelfDirectedExecutor:
    def test_execute_not_approved(self):
        context = ExecutionContext()
        executor = SelfDirectedExecutor(context)

        from autonomous.decision import Decision
        decision = Decision(
            decision_type=DecisionType.IDLE,
            source_observation=Observation(
                obs_type=ObservationType.MEMORY_TREND,
                source="memory",
                description="test",
            ),
            outcome=DecisionOutcome.REJECTED,
        )

        result = executor.execute(decision)
        assert not result.success
        assert result.execution_type == ExecutionType.NOOP

    def test_execute_noop(self):
        context = ExecutionContext()
        executor = SelfDirectedExecutor(context)

        decision = Decision(
            decision_type=DecisionType.IDLE,
            source_observation=Observation(
                obs_type=ObservationType.MEMORY_TREND,
                source="memory",
                description="test",
            ),
            outcome=DecisionOutcome.APPROVED,
        )

        result = executor.execute(decision)
        assert result.success
        assert result.execution_type == ExecutionType.NOOP

    def test_execute_batch(self):
        context = ExecutionContext()
        executor = SelfDirectedExecutor(context)

        decisions = [
            Decision(
                decision_type=DecisionType.IDLE,
                source_observation=Observation(
                    obs_type=ObservationType.MEMORY_TREND,
                    source="memory",
                    description="test",
                ),
                outcome=DecisionOutcome.APPROVED,
            ),
        ]

        results = executor.execute_batch(decisions)
        assert len(results) == 1
        assert results[0].success

    def test_dry_run(self):
        context = ExecutionContext(dry_run=True)
        executor = SelfDirectedExecutor(context)

        decision = Decision(
            decision_type=DecisionType.CONSOLIDATE_MEMORY,
            source_observation=Observation(
                obs_type=ObservationType.MEMORY_TREND,
                source="memory",
                description="test",
                data={"entry_count": 10},
            ),
            outcome=DecisionOutcome.APPROVED,
        )

        result = executor.execute(decision)
        assert result.success
        assert result.output.get("dry_run") is True

    def test_stats(self):
        context = ExecutionContext()
        executor = SelfDirectedExecutor(context)

        decision = Decision(
            decision_type=DecisionType.IDLE,
            source_observation=Observation(
                obs_type=ObservationType.MEMORY_TREND,
                source="memory",
                description="test",
            ),
            outcome=DecisionOutcome.APPROVED,
        )
        executor.execute(decision)

        stats = executor.get_stats()
        assert stats["total_executions"] == 1
        assert stats["success_rate"] == 1.0


# -- ActivityReporter Tests ---------------------------------------------------

class TestActivityReporter:
    def test_report_success(self):
        reporter = ActivityReporter()

        decision = Decision(
            decision_type=DecisionType.CONSOLIDATE_MEMORY,
            source_observation=Observation(
                obs_type=ObservationType.MEMORY_TREND,
                source="memory",
                description="test",
            ),
            outcome=DecisionOutcome.APPROVED,
        )
        result = ExecutionResult(decision=decision, execution_type=ExecutionType.DREAMING, success=True)

        report = reporter.report(result)
        assert report.severity == ReportSeverity.INFO
        assert ReportChannel.LOG in report.channels
        assert ReportChannel.MEMORY in report.channels

    def test_report_failure(self):
        reporter = ActivityReporter()

        decision = Decision(
            decision_type=DecisionType.CONSOLIDATE_MEMORY,
            source_observation=Observation(
                obs_type=ObservationType.MEMORY_TREND,
                source="memory",
                description="test",
                urgency=0.9,
            ),
            outcome=DecisionOutcome.APPROVED,
        )
        result = ExecutionResult(decision=decision, execution_type=ExecutionType.DREAMING, success=False)

        report = reporter.report(result)
        assert report.severity == ReportSeverity.CRITICAL

    def test_summary(self):
        reporter = ActivityReporter()

        decision = Decision(
            decision_type=DecisionType.CONSOLIDATE_MEMORY,
            source_observation=Observation(
                obs_type=ObservationType.MEMORY_TREND,
                source="memory",
                description="test",
            ),
            outcome=DecisionOutcome.APPROVED,
        )
        result = ExecutionResult(decision=decision, execution_type=ExecutionType.DREAMING, success=True)
        reporter.report(result)

        summary = reporter.get_summary()
        assert summary["total_activities"] == 1


# -- AutonomousLoop Tests -----------------------------------------------------

class TestAutonomousLoop:
    def test_init(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=True, tick_interval_seconds=1.0, autostart=False)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)
        assert loop.state == LoopState.STOPPED
        assert loop.config.tick_interval_seconds == 1.0

    def test_autostart(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=True, tick_interval_seconds=1.0, autostart=True)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)
        # Give thread time to start
        time.sleep(0.2)
        assert loop.state == LoopState.RUNNING
        loop.stop()

    def test_start_stop(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=True, tick_interval_seconds=1.0, idle_threshold_seconds=0, autostart=False)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        loop.start()
        assert loop.state == LoopState.RUNNING

        # Let it tick once
        time.sleep(0.5)

        loop.stop()
        assert loop.state == LoopState.STOPPED

    def test_pause_resume(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=True, tick_interval_seconds=10.0, autostart=False)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        loop.start()
        loop.pause()
        assert loop.state == LoopState.PAUSED

        loop.resume()
        assert loop.state == LoopState.RUNNING

        loop.stop()

    def test_touch_resets_idle(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=True, tick_interval_seconds=10.0, idle_threshold_seconds=3600, autostart=False)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        loop.start()
        time.sleep(0.1)

        # Touch should reset idle timer
        loop.touch()

        loop.stop()

    def test_circuit_breaker(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(
            enabled=True,
            tick_interval_seconds=0.1,
            idle_threshold_seconds=0,
            circuit_breaker_threshold=1,
            circuit_breaker_timeout_seconds=0.1,
            autostart=False,
        )
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        # Manually open circuit
        loop._open_circuit()
        assert loop._circuit_open

        # Close circuit after timeout
        time.sleep(0.15)
        loop._close_circuit()
        assert not loop._circuit_open

    def test_stats(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=True, autostart=False)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        stats = loop.get_stats()
        assert "state" in stats
        assert "config" in stats
        assert stats["config"]["enabled"] is True

    def test_disabled_config(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=False)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        loop.start()  # Should not start because enabled=False
        assert loop.state == LoopState.STOPPED

    def test_tick_result(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(enabled=True, idle_threshold_seconds=0, autostart=False)
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        result = loop._tick()
        assert isinstance(result, LoopResult)
        assert result.success

    def test_execution_batch_exception_opens_circuit(self, temp_memory_db):
        class FakeSwarm:
            memory_db_path = temp_memory_db
            memory = None
            goals = None
            message_bus = None
            _llm_call = None

        config = LoopConfig(
            enabled=True,
            idle_threshold_seconds=0,
            circuit_breaker_threshold=1,
            autostart=False,
        )
        loop = AutonomousLoop(swarm=FakeSwarm(), config=config)

        observation = Observation(
            obs_type=ObservationType.SYSTEM_HEALTH,
            source="health",
            description="Injected failure path",
            confidence=0.9,
            urgency=0.9,
            value=0.9,
            data={"chaos": True},
        )
        decision = Decision(
            decision_type=DecisionType.SELF_HEAL,
            source_observation=observation,
            outcome=DecisionOutcome.APPROVED,
            priority=0.9,
        )

        loop.observer = type("Obs", (), {"observe": lambda self=None: [observation], "get_signals": lambda self=None: {}})()
        loop.decision_engine = type(
            "Decider",
            (),
            {
                "decide": lambda self, _obs: [decision],
                "today_action_count": 0,
                "get_stats": lambda self=None: {},
            },
        )()

        class BoomExecutor:
            def execute_batch(self, _decisions):
                raise TimeoutError("chaos-timeout")

            def get_stats(self):
                return {}

        loop.executor = BoomExecutor()

        result = loop._tick()
        assert result.success is False
        assert result.error and "execution_batch_failed" in result.error
        stats = loop.get_stats()
        assert stats["failure_count"] >= 1
        assert stats["circuit_open"] is True


# -- ResearchEngine Tests -----------------------------------------------------

class TestResearchEngine:
    def test_init(self):
        engine = ResearchEngine()
        assert engine.config is not None
        assert engine.config.max_rounds == 3

    def test_research_no_web_search(self):
        """Research without web search returns report with no sources."""
        engine = ResearchEngine(web_search=None, llm_callback=None)
        report = engine.research("test topic")
        assert isinstance(report, ResearchReport)
        assert report.topic == "test topic"
        assert len(report.all_sources) == 0
        assert report.confidence_overall >= 0.0  # Default low confidence when no findings

    def test_research_with_mock_search(self):
        """Research with mock web search works."""
        class MockSearchResult:
            def __init__(self, title, url, content, score=0.8, source="mock"):
                self.title = title
                self.url = url
                self.content = content
                self.score = score
                self.source = source

        class MockWebSearch:
            def search(self, query, max_results=5):
                return [
                    MockSearchResult("Test", "https://example.com", "Test content about " + query),
                ]

        engine = ResearchEngine(
            web_search=MockWebSearch(),
            llm_callback=None,
            config=ResearchConfig(max_rounds=1, max_sources_per_round=1),
        )
        report = engine.research("AI breakthroughs")
        assert isinstance(report, ResearchReport)
        assert len(report.rounds) == 1
        assert len(report.all_sources) == 1
        assert report.all_sources[0].title == "Test"

    def test_research_with_llm(self):
        """Research with LLM callback generates findings."""
        class MockSearchResult:
            def __init__(self, title, url, content):
                self.title = title
                self.url = url
                self.content = content
                self.score = 0.8
                self.source = "mock"

        class MockWebSearch:
            def search(self, query, max_results=5):
                return [MockSearchResult("Test", "https://ex.com", "AI is advancing fast")]

        def mock_llm(prompt, max_tokens=1000):
            return """### SYNTHESIS
AI is making rapid progress in 2026.

### FINDINGS
1. **Claim**: AI models are improving
   **Evidence**: Multiple sources confirm this
   **Confidence**: high

### HYPOTHESES
1. Will AI surpass human level?
   **Priority**: high
"""

        engine = ResearchEngine(
            web_search=MockWebSearch(),
            llm_callback=mock_llm,
            config=ResearchConfig(max_rounds=1, max_sources_per_round=1),
        )
        report = engine.research("AI progress")
        assert len(report.rounds) == 1
        assert len(report.rounds[0].findings) == 1
        assert report.rounds[0].findings[0].claim == "AI models are improving"
        assert report.rounds[0].findings[0].confidence == 0.85

    def test_research_report_markdown(self):
        """Report can be converted to markdown."""
        report = ResearchReport(topic="Test")
        report.all_sources = [
            ResearchSource(title="Source 1", url="https://ex.com", content="Content"),
        ]
        report.key_findings = [
            ResearchFinding(claim="Claim 1", evidence="Evidence 1", confidence=0.9),
        ]
        md = report.to_markdown()
        assert "# Research Report: Test" in md
        assert "Source 1" in md
        assert "Claim 1" in md
        assert "90%" in md

    def test_research_memory_storage(self, temp_memory_db):
        """Research report is stored in memory system."""
        stored = []

        class MockMemory:
            def save(self, content, role, tags, metadata):
                stored.append({"content": content, "role": role, "tags": tags, "metadata": metadata})

        class MockSearchResult:
            def __init__(self, title, url, content):
                self.title = title
                self.url = url
                self.content = content
                self.score = 0.8
                self.source = "mock"

        class MockWebSearch:
            def search(self, query, max_results=5):
                return [MockSearchResult("Test", "https://ex.com", "Content")]

        engine = ResearchEngine(
            web_search=MockWebSearch(),
            memory_system=MockMemory(),
            config=ResearchConfig(max_rounds=1, store_in_memory=True),
        )
        engine.research("test")
        assert len(stored) == 1
        assert stored[0]["role"] == "research"
        assert "autoresearch" in stored[0]["tags"]

    def test_quick_research(self):
        """Quick research returns markdown string."""
        class MockSearchResult:
            def __init__(self, title, url, content):
                self.title = title
                self.url = url
                self.content = content
                self.score = 0.8
                self.source = "mock"

        class MockWebSearch:
            def search(self, query, max_results=5):
                return [MockSearchResult("Test", "https://ex.com", "Content")]

        engine = ResearchEngine(
            web_search=MockWebSearch(),
            config=ResearchConfig(max_rounds=3),  # Will be overridden to 1
        )
        md = engine.quick_research("quick test")
        assert "# Research Report: quick test" in md

    def test_research_stats(self):
        engine = ResearchEngine()
        assert engine.get_stats()["sessions"] == 0
        assert engine.get_stats()["success_rate"] == 1.0

    def test_research_convergence(self):
        """Research stops early when no new hypotheses."""
        class MockSearchResult:
            def __init__(self, title, url, content):
                self.title = title
                self.url = url
                self.content = content
                self.score = 0.8
                self.source = "mock"

        class MockWebSearch:
            def search(self, query, max_results=5):
                return [MockSearchResult("Test", "https://ex.com", "Content")]

        def mock_llm_no_hypotheses(prompt, max_tokens=1000):
            return "### SYNTHESIS\nNo new info.\n\n### FINDINGS\n\n### HYPOTHESES\n"

        engine = ResearchEngine(
            web_search=MockWebSearch(),
            llm_callback=mock_llm_no_hypotheses,
            config=ResearchConfig(max_rounds=3, early_convergence=True),
        )
        report = engine.research("convergence test")
        # Should converge after round 1 since no hypotheses
        assert len(report.rounds) == 1

    def test_research_source_citation(self):
        src = ResearchSource(title="Paper", url="https://paper.com", content="Data")
        assert src.citation == "[Paper](https://paper.com)"
        assert "Data" in src.snippet

    def test_research_finding_priority_score(self):
        obs = Observation(
            obs_type=ObservationType.KNOWLEDGE_GAP,
            source="research",
            description="test",
            confidence=0.8,
            urgency=0.7,
            value=0.9,
        )
        assert obs.priority_score == 0.8 * 0.7 * 0.9
