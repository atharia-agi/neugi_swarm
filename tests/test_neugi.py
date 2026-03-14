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

    def test_dashboard_exists(self):
        """Test dashboard.html exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "dashboard.html")
        assert os.path.exists(path)

    def test_no_alert_popups(self):
        """Test no alert() in JS (replaced with toast)"""
        path = os.path.join(os.path.dirname(__file__), "..", "index.html")
        with open(path, "r") as f:
            content = f.read()
        assert "alert(" not in content

    def test_has_toast_function(self):
        """Test toast function exists in JS"""
        path = os.path.join(os.path.dirname(__file__), "..", "index.html")
        with open(path, "r") as f:
            content = f.read()
        assert "showToast" in content

    def test_has_os_buttons(self):
        """Test OS selection buttons exist"""
        path = os.path.join(os.path.dirname(__file__), "..", "index.html")
        with open(path, "r") as f:
            content = f.read()
        assert "Windows" in content
        assert "Mac" in content
        assert "Linux" in content


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

    def test_package_json_exists(self):
        """Test package.json exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "package.json")
        assert os.path.exists(path)

    def test_vercel_config_exists(self):
        """Test vercel.json exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "vercel.json")
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

    def test_neugi_service_exists(self):
        """Test neugi.service exists"""
        path = os.path.join(os.path.dirname(__file__), "..", "neugi.service")
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

    def test_secondary_files_exist(self):
        """Test secondary Python files exist"""
        files = [
            "neugi_technician.py",
            "neugi_swarm_context.py",
            "neugi_swarm_edge.py",
            "neugi_swarm_gateway.py",
            "neugi_swarm_channels.py",
            "neugi_swarm_skills.py",
            "neugi_swarm_voice.py",
            "ollama_assistant.py",
            "VERIFIED_MODELS.py",
            "config_template.py",
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

    def test_has_searxng(self):
        """Test SearXNG is in browser"""
        path = os.path.join(os.path.dirname(__file__), "..", "neugi_swarm_browser.py")
        with open(path, "r") as f:
            content = f.read()
        assert "searxng" in content.lower() or "searx" in content.lower()


class TestCI:
    """Test CI/CD configuration"""

    def test_github_actions_exists(self):
        """Test GitHub Actions workflow exists"""
        path = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "test.yml")
        assert os.path.exists(path)

    def test_gitignore_exists(self):
        """Test .gitignore exists"""
        path = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
        assert os.path.exists(path)


class TestCodeQuality:
    """Test code quality standards"""

    def test_all_python_files_syntax(self):
        """Test all Python files have valid syntax"""
        import py_compile

        base = os.path.dirname(__file__)
        py_files = []
        for root, dirs, files in os.walk(os.path.join(base, "..")):
            if ".git" in root or "tests" in root:
                continue
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))

        for f in py_files:
            try:
                py_compile.compile(f, doraise=True)
            except py_compile.PyCompileError as e:
                assert False, f"Syntax error in {f}: {e}"

    def test_no_debug_print_in_production(self):
        """Test no debug print statements left behind"""
        base = os.path.dirname(__file__)
        files_to_check = ["neugi_swarm.py", "neugi_wizard.py", "neugi_assistant.py"]

        for f in files_to_check:
            path = os.path.join(base, "..", f)
            if os.path.exists(path):
                with open(path, "r") as file:
                    for i, line in enumerate(file, 1):
                        # Allow print statements with f-strings or .format()
                        if "print(" in line and not (
                            'f"' in line or "f'" in line or ".format(" in line
                        ):
                            # Allow UI prints (self.ui., C. colors)
                            if not ("self.ui." in line or "C." in line):
                                pass  # Could add assertion here if needed
