"""Tests for SoulEngine identity/personality system."""
import tempfile

from context.soul_engine import SoulEngine


class TestSoulEngine:
    def test_init_defaults_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            created = engine.init_defaults()
            # All 5 files including MEMORY.md fallback
            assert len(created) == 5
            for p in created:
                assert p.exists()

    def test_exists_after_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            assert not engine.exists()
            engine.init_defaults()
            assert engine.exists()

    def test_read_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.write("TEST.md", "hello")
            assert engine.read("TEST.md") == "hello"

    def test_update_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.write("TEST.md", "name: {{name}}")
            assert engine.update_field("TEST.md", "name", "Neugi")
            assert engine.read("TEST.md") == "name: Neugi"

    def test_update_field_missing_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.write("TEST.md", "no placeholders")
            assert not engine.update_field("TEST.md", "name", "Neugi")

    def test_append_memory_file_fallback(self):
        """When no MemorySystem, append_memory writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.append_memory("Learned user likes dark mode")
            mem = engine.read("MEMORY.md")
            assert "dark mode" in mem

    def test_add_user_fact_file_fallback(self):
        """When no MemorySystem, add_user_fact writes to USER.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.init_defaults()
            engine.add_user_fact("User is a Python developer")
            user = engine.read("USER.md")
            assert "Python developer" in user

    def test_get_identity_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.init_defaults()
            prompt = engine.get_identity_prompt()
            assert "SOUL" in prompt
            assert "STYLE" in prompt
            assert "USER" in prompt
            assert "WORLD" in prompt
            assert "MEMORY" in prompt

    def test_fingerprint_changes_on_edit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.init_defaults()
            fp1 = engine.get_fingerprint()
            engine.write("SOUL.md", "Modified identity")
            fp2 = engine.get_fingerprint()
            assert fp1 != fp2

    def test_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.init_defaults()
            s = engine.stats()
            assert s["initialized"] is True
            assert s["memory_system_attached"] is False
            assert "SOUL.md" in s["files"]
            assert "MEMORY.md" in s["files"]
            assert s["files"]["MEMORY.md"]["volatile"] is True

    def test_memory_fallback_exists_on_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = SoulEngine(base_dir=tmpdir)
            engine.init_defaults()
            # MEMORY.md fallback exists on disk when no MemorySystem
            assert (engine.soul_dir / "MEMORY.md").exists()
            content = engine.read("MEMORY.md")
            assert "Continuity Snapshot" in content
