"""NEUGI SWARM - Test Suite"""

import os


class TestLandingPage:
    """Test landing page"""

    def test_index_exists(self):
        """Test index.html exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "index.html")
        assert os.path.exists(path)

    def test_docs_exists(self):
        """Test docs.html exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "docs.html")
        assert os.path.exists(path)

    def test_no_alert_popups(self):
        """Test no alert() in JS (replaced with toast)"""
        path = os.path.join(os.path.dirname(__file__), "..", "index.html")
        with open(path, "r") as f:
            content = f.read()
        assert "alert(" not in content


class TestConfig:
    """Test configuration files"""

    def test_readme_exists(self):
        """Test README exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "README.md")
        assert os.path.exists(path)

    def test_changelog_exists(self):
        """Test CHANGELOG exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")
        assert os.path.exists(path)

    def test_requirements_exists(self):
        """Test requirements.txt exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        assert os.path.exists(path)

    def test_pyproject_exists(self):
        """Test pyproject.toml exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
        assert os.path.exists(path)


class TestInstallers:
    """Test installer files"""

    def test_install_sh_exists(self):
        """Test install.sh exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "install.sh")
        assert os.path.exists(path)

    def test_install_bat_exists(self):
        """Test install.bat exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "install.bat")
        assert os.path.exists(path)


class TestCoreFiles:
    """Test core Python files"""

    def test_main_files_exist(self):
        """Test main Python files exist"""
        files = [
            "neugi_swarm.py",
            "neugi_wizard.py",
            "neugi_assistant.py",
            "neugi_telegram.py",
            "neugi_security.py",
            "neugi_updater.py",
            "neugi_plugins.py",
            "neugi_swarm_browser.py",
            "neugi_swarm_agents.py",
            "neugi_swarm_memory.py",
            "neugi_swarm_tools.py",
        ]
        base = os.path.dirname(__file__)
        for f in files:
            path = os.path.join(base, "..", f)
            assert os.path.exists(path), f"Missing: {f}"


class TestBrowserAgent:
    """Test browser agent"""

    def test_browser_file_exists(self):
        """Test browser file exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "neugi_swarm_browser.py")
        assert os.path.exists(path)

    def test_has_duckduckgo(self):
        """Test DuckDuckGo is in browser"""
        path = os.path.join(os.path.dirname(__file__), "..", "neugi_swarm_browser.py")
        with open(path, "r") as f:
            content = f.read()
        assert "duckduckgo" in content.lower() or "DuckDuckGo" in content
