"""Tests for rescue_wizard module."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from cli.rescue_wizard import RescueWizard, WizardError


class TestRescueWizard:
    def test_initialization_default_dir(self):
        wizard = RescueWizard()
        assert wizard.base_dir == Path("~/.neugi").expanduser()

    def test_initialization_custom_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            assert wizard.base_dir == Path(tmpdir)

    def test_check_health_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            health = wizard.check_health()
            assert isinstance(health, dict)
            assert "config_valid" in health
            assert "ollama_running" in health

    def test_load_current_config_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            cfg = wizard._load_current_config()
            assert cfg == {}

    def test_load_current_config_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            wizard.base_dir.mkdir(parents=True, exist_ok=True)
            with open(wizard.config_path, "w") as f:
                json.dump({"llm": {"provider": "ollama"}}, f)
            cfg = wizard._load_current_config()
            assert cfg["llm"]["provider"] == "ollama"

    def test_load_current_config_corrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            wizard.base_dir.mkdir(parents=True, exist_ok=True)
            with open(wizard.config_path, "w") as f:
                f.write("not json {{[")
            cfg = wizard._load_current_config()
            assert cfg == {}

    def test_setup_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            success = wizard._setup_directories()
            assert success is True
            assert (wizard.base_dir / "skills").exists()
            assert (wizard.base_dir / "memory").exists()
            assert (wizard.base_dir / "sessions").exists()

    def test_save_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            wizard._save_config("ollama", "qwen2.5-coder:7b", {"memory": True})
            assert wizard.config_path.exists()
            with open(wizard.config_path) as f:
                cfg = json.load(f)
            assert cfg["llm"]["provider"] == "ollama"
            assert cfg["llm"]["model"] == "qwen2.5-coder:7b"

    def test_update_config_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            wizard._save_config("ollama", "qwen2.5-coder:7b", {})
            wizard._update_config_field("provider", "openai")
            cfg = wizard._load_current_config()
            assert cfg["llm"]["provider"] == "openai"

    def test_restore_default_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            wizard._restore_default_config()
            assert wizard.config_path.exists()
            cfg = wizard._load_current_config()
            assert cfg["llm"]["provider"] == "ollama"

    def test_check_directories_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            issues = wizard._check_directories()
            assert len(issues) > 0
            assert "Directory missing" in issues[0]

    def test_check_directories_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            wizard._setup_directories()
            issues = wizard._check_directories()
            assert len(issues) == 0

    def test_check_config_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            issues = wizard._check_config()
            assert "Config file missing" in issues

    def test_check_config_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            wizard._save_config("ollama", "qwen2.5-coder:7b", {})
            issues = wizard._check_config()
            assert len(issues) == 0

    def test_auto_fix_missing_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            fixes = wizard._auto_fix(["Config file missing"], "config")
            assert len(fixes) > 0
            assert wizard.config_path.exists()

    def test_auto_fix_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wizard = RescueWizard(base_dir=tmpdir)
            fixes = wizard._auto_fix(["Directory missing: skills"], "directories")
            assert len(fixes) > 0
            assert (wizard.base_dir / "skills").exists()

    def test_list_workflow_ids_implemented(self):
        """Test that list_workflow_ids is no longer NotImplementedError."""
        from workflows.checkpoint import SQLiteCheckpointStorage
        db_path = os.path.join(tempfile.gettempdir(), "neugi_test_ckpt.db")
        try:
            storage = SQLiteCheckpointStorage(db_path)
            # Should not raise
            ids = storage.list_workflow_ids()
            assert isinstance(ids, list)
        finally:
            # Clean up on Windows (close connection first)
            import sqlite3
            try:
                conn = sqlite3.connect(db_path)
                conn.close()
            except Exception:
                pass
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass
