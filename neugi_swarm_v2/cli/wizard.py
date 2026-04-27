"""
NEUGI v2 Setup Wizard
=====================

Interactive setup wizard that guides users through initial configuration
of the NEUGI Swarm v2 framework. Supports multi-language, step skipping,
progress saving, and resume functionality.

Usage:
    from neugi_swarm_v2.cli.wizard import SetupWizard

    wizard = SetupWizard()
    wizard.run()
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.prompt import Prompt, Confirm
    from rich.prompt import IntPrompt
    from rich.columns import Columns
    from rich.text import Text
    from rich.rule import Rule
    from rich.box import ROUNDED, DOUBLE
    from rich.theme import Theme
    from rich.layout import Layout
except ImportError:
    print("Error: 'rich' library is required. Install with: pip install rich")
    sys.exit(1)


# -- Theme -------------------------------------------------------------------

WIZARD_THEME = Theme({
    "primary": "bold cyan",
    "secondary": "bold magenta",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "blue",
    "dim": "dim white",
    "accent": "bold bright_cyan",
    "step_title": "bold white on blue",
    "prompt": "cyan",
})

console = Console(theme=WIZARD_THEME)


# -- Internationalization ----------------------------------------------------

@dataclass
class Translations:
    """Translation strings for the wizard.

    Attributes:
        language_code: ISO language code.
        strings: Dictionary of translation keys to localized strings.
    """
    language_code: str
    strings: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        """Get a translated string."""
        return self.strings.get(key, default)


TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "welcome_title": "Welcome to NEUGI Swarm v2",
        "welcome_desc": "Autonomous Multi-Agent Framework Setup Wizard",
        "step": "Step",
        "of": "of",
        "skip": "Skip",
        "back": "Back",
        "next": "Next",
        "redo": "Redo",
        "quit": "Quit",
        "help": "Help",
        "select_option": "Select an option",
        "enter_value": "Enter value",
        "press_enter": "Press Enter to continue",
        "saving": "Saving progress...",
        "saved": "Progress saved",
        "step_welcome_title": "Welcome & System Check",
        "step_welcome_desc": "Verify your system meets the requirements for NEUGI.",
        "step_llm_title": "LLM Provider Setup",
        "step_llm_desc": "Configure your AI model provider (Ollama, OpenAI, Anthropic).",
        "step_model_title": "Model Selection & Testing",
        "step_model_desc": "Select a model and test the connection.",
        "step_channels_title": "Channel Configuration",
        "step_channels_desc": "Optionally connect messaging channels (Telegram, Discord, etc.).",
        "step_security_title": "Security Settings",
        "step_security_desc": "Configure access controls and security options.",
        "step_memory_title": "Memory Configuration",
        "step_memory_desc": "Set up memory system parameters and dreaming.",
        "step_plugins_title": "Plugin Selection",
        "step_plugins_desc": "Choose which plugins to enable.",
        "step_review_title": "Final Review & Start",
        "step_review_desc": "Review your configuration and start NEUGI.",
        "system_check": "Running system check...",
        "python_version": "Python Version",
        "platform": "Platform",
        "disk_space": "Available Disk Space",
        "memory_available": "System Memory",
        "status_ok": "OK",
        "status_warn": "Warning",
        "select_provider": "Select LLM Provider",
        "ollama": "Ollama (Local)",
        "openai": "OpenAI (Cloud)",
        "anthropic": "Anthropic (Cloud)",
        "api_key": "API Key",
        "base_url": "Base URL",
        "ollama_url": "Ollama URL",
        "testing_connection": "Testing connection...",
        "connection_success": "Connection successful!",
        "connection_failed": "Connection failed. Please check your settings.",
        "select_model": "Select a Model",
        "model_test": "Testing model...",
        "model_success": "Model test passed!",
        "model_failed": "Model test failed. Try a different model.",
        "configure_channels": "Configure Channels",
        "telegram": "Telegram",
        "discord": "Discord",
        "slack": "Slack",
        "whatsapp": "WhatsApp",
        "channel_token": "Bot Token",
        "channel_enabled": "Channel enabled",
        "security_level": "Security Level",
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "enable_auth": "Enable Authentication",
        "enable_encryption": "Enable Data Encryption",
        "memory_size": "Memory Size Limit",
        "enable_dreaming": "Enable Dreaming Consolidation",
        "dreaming_hour": "Dreaming Hour (0-23)",
        "ttl_days": "Memory TTL (days)",
        "select_plugins": "Select Plugins",
        "review_config": "Review Configuration",
        "provider": "Provider",
        "model": "Model",
        "channels": "Channels",
        "security": "Security",
        "memory": "Memory",
        "plugins": "Plugins",
        "start_neugi": "Start NEUGI now?",
        "setup_complete": "Setup Complete!",
        "setup_saved": "Configuration saved. Run 'neugi start' to begin.",
    },
    "id": {
        "welcome_title": "Selamat Datang di NEUGI Swarm v2",
        "welcome_desc": "Panduan Penyiapan Kerangka Multi-Agen Otonom",
        "step": "Langkah",
        "of": "dari",
        "skip": "Lewati",
        "back": "Kembali",
        "next": "Berikutnya",
        "redo": "Ulangi",
        "quit": "Keluar",
        "help": "Bantuan",
        "select_option": "Pilih opsi",
        "enter_value": "Masukkan nilai",
        "press_enter": "Tekan Enter untuk melanjutkan",
        "saving": "Menyimpan progres...",
        "saved": "Progres disimpan",
        "step_welcome_title": "Selamat Datang & Pemeriksaan Sistem",
        "step_welcome_desc": "Verifikasi sistem Anda memenuhi persyaratan NEUGI.",
        "step_llm_title": "Penyiapan Penyedia LLM",
        "step_llm_desc": "Konfigurasi penyedia model AI (Ollama, OpenAI, Anthropic).",
        "step_model_title": "Pemilihan & Pengujian Model",
        "step_model_desc": "Pilih model dan uji koneksi.",
        "step_channels_title": "Konfigurasi Saluran",
        "step_channels_desc": "Opsional: hubungkan saluran pesan (Telegram, Discord, dll).",
        "step_security_title": "Pengaturan Keamanan",
        "step_security_desc": "Konfigurasi kontrol akses dan opsi keamanan.",
        "step_memory_title": "Konfigurasi Memori",
        "step_memory_desc": "Atur parameter sistem memori dan dreaming.",
        "step_plugins_title": "Pemilihan Plugin",
        "step_plugins_desc": "Pilih plugin yang akan diaktifkan.",
        "step_review_title": "Tinjauan Akhir & Mulai",
        "step_review_desc": "Tinjau konfigurasi Anda dan mulai NEUGI.",
        "select_provider": "Pilih Penyedia LLM",
        "ollama": "Ollama (Lokal)",
        "openai": "OpenAI (Cloud)",
        "anthropic": "Anthropic (Cloud)",
        "api_key": "Kunci API",
        "connection_success": "Koneksi berhasil!",
        "connection_failed": "Koneksi gagal. Periksa pengaturan Anda.",
        "start_neugi": "Mulai NEUGI sekarang?",
        "setup_complete": "Penyiapan Selesai!",
        "setup_saved": "Konfigurasi disimpan. Jalankan 'neugi start' untuk memulai.",
    },
    "es": {
        "welcome_title": "Bienvenido a NEUGI Swarm v2",
        "welcome_desc": "Asistente de Configuración del Framework Multi-Agente Autónomo",
        "step": "Paso",
        "of": "de",
        "skip": "Saltar",
        "back": "Atrás",
        "next": "Siguiente",
        "redo": "Rehacer",
        "quit": "Salir",
        "help": "Ayuda",
        "select_option": "Seleccionar una opción",
        "enter_value": "Ingrese valor",
        "press_enter": "Presione Enter para continuar",
        "select_provider": "Seleccionar Proveedor LLM",
        "ollama": "Ollama (Local)",
        "openai": "OpenAI (Cloud)",
        "anthropic": "Anthropic (Cloud)",
        "api_key": "Clave API",
        "connection_success": "¡Conexión exitosa!",
        "connection_failed": "Conexión fallida. Verifique su configuración.",
        "start_neugi": "¿Iniciar NEUGI ahora?",
        "setup_complete": "¡Configuración Completa!",
        "setup_saved": "Configuración guardada. Ejecute 'neugi start' para comenzar.",
    },
    "fr": {
        "welcome_title": "Bienvenue dans NEUGI Swarm v2",
        "welcome_desc": "Assistant de Configuration du Framework Multi-Agent Autonome",
        "step": "Étape",
        "of": "sur",
        "skip": "Passer",
        "back": "Précédent",
        "next": "Suivant",
        "redo": "Refaire",
        "quit": "Quitter",
        "help": "Aide",
        "select_option": "Sélectionner une option",
        "enter_value": "Entrer une valeur",
        "press_enter": "Appuyez sur Entrée pour continuer",
        "select_provider": "Sélectionner le Fournisseur LLM",
        "ollama": "Ollama (Local)",
        "openai": "OpenAI (Cloud)",
        "anthropic": "Anthropic (Cloud)",
        "api_key": "Clé API",
        "connection_success": "Connexion réussie !",
        "connection_failed": "Échec de la connexion. Vérifiez vos paramètres.",
        "start_neugi": "Démarrer NEUGI maintenant ?",
        "setup_complete": "Configuration Terminée !",
        "setup_saved": "Configuration sauvegardée. Exécutez 'neugi start' pour commencer.",
    },
    "de": {
        "welcome_title": "Willkommen bei NEUGI Swarm v2",
        "welcome_desc": "Einrichtungsassistent für das Autonome Multi-Agenten-Framework",
        "step": "Schritt",
        "of": "von",
        "skip": "Überspringen",
        "back": "Zurück",
        "next": "Weiter",
        "redo": "Wiederholen",
        "quit": "Beenden",
        "help": "Hilfe",
        "select_option": "Option auswählen",
        "enter_value": "Wert eingeben",
        "press_enter": "Drücken Sie Enter zum Fortfahren",
        "select_provider": "LLM-Anbieter auswählen",
        "ollama": "Ollama (Lokal)",
        "openai": "OpenAI (Cloud)",
        "anthropic": "Anthropic (Cloud)",
        "api_key": "API-Schlüssel",
        "connection_success": "Verbindung erfolgreich!",
        "connection_failed": "Verbindung fehlgeschlagen. Überprüfen Sie Ihre Einstellungen.",
        "start_neugi": "NEUGI jetzt starten?",
        "setup_complete": "Einrichtung abgeschlossen!",
        "setup_saved": "Konfiguration gespeichert. Führen Sie 'neugi start' aus.",
    },
    "jp": {
        "welcome_title": "NEUGI Swarm v2 へようこそ",
        "welcome_desc": "自律型マルチエージェントフレームワーク セットアップウィザード",
        "step": "ステップ",
        "of": "/",
        "skip": "スキップ",
        "back": "戻る",
        "next": "次へ",
        "redo": "やり直し",
        "quit": "終了",
        "help": "ヘルプ",
        "select_option": "オプションを選択",
        "enter_value": "値を入力",
        "press_enter": "Enter キーを押して続行",
        "select_provider": "LLM プロバイダーを選択",
        "ollama": "Ollama（ローカル）",
        "openai": "OpenAI（クラウド）",
        "anthropic": "Anthropic（クラウド）",
        "api_key": "API キー",
        "connection_success": "接続成功！",
        "connection_failed": "接続に失敗しました。設定を確認してください。",
        "start_neugi": "今すぐ NEUGI を起動しますか？",
        "setup_complete": "セットアップ完了！",
        "setup_saved": "設定が保存されました。'neugi start' を実行して開始してください。",
    },
}


class Language(Enum):
    """Supported languages for the wizard."""
    ENGLISH = "en"
    INDONESIAN = "id"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    JAPANESE = "jp"

    @property
    def display_name(self) -> str:
        """Get the display name for the language."""
        names = {
            "en": "English",
            "id": "Bahasa Indonesia",
            "es": "Español",
            "fr": "Français",
            "de": "Deutsch",
            "jp": "日本語",
        }
        return names.get(self.value, self.value)


# -- Wizard State ------------------------------------------------------------

class WizardAction(Enum):
    """Actions that can be taken during wizard navigation."""
    NEXT = "next"
    BACK = "back"
    SKIP = "skip"
    REDO = "redo"
    QUIT = "quit"
    HELP = "help"
    COMPLETE = "complete"


@dataclass
class WizardState:
    """Tracks the current state of the wizard.

    Attributes:
        current_step: Index of the current step.
        completed_steps: Set of completed step indices.
        skipped_steps: Set of skipped step indices.
        config: Accumulated configuration data.
        language: Selected language code.
        action: Last navigation action taken.
    """
    current_step: int = 0
    completed_steps: set[int] = field(default_factory=set)
    skipped_steps: set[int] = field(default_factory=set)
    config: dict[str, Any] = field(default_factory=dict)
    language: str = "en"
    action: WizardAction = WizardAction.NEXT

    def mark_complete(self, step: int) -> None:
        """Mark a step as completed."""
        self.completed_steps.add(step)
        self.skipped_steps.discard(step)

    def mark_skip(self, step: int) -> None:
        """Mark a step as skipped."""
        self.skipped_steps.add(step)
        self.completed_steps.discard(step)

    def is_complete(self, step: int) -> bool:
        """Check if a step has been completed."""
        return step in self.completed_steps

    def is_skipped(self, step: int) -> bool:
        """Check if a step has been skipped."""
        return step in self.skipped_steps

    def progress_percent(self, total_steps: int) -> float:
        """Calculate completion percentage."""
        if total_steps == 0:
            return 0.0
        return len(self.completed_steps) / total_steps * 100


# -- Wizard Step -------------------------------------------------------------

@dataclass
class WizardStep:
    """Definition of a single wizard step.

    Attributes:
        id: Unique step identifier.
        title_key: Translation key for the step title.
        description_key: Translation key for the step description.
        renderer: Callable that renders the step UI.
        validator: Optional callable that validates step input.
        required: Whether the step can be skipped.
        help_text: Additional help text for the step.
    """
    id: str
    title_key: str
    description_key: str
    renderer: Callable[["SetupWizard", dict[str, Any]], WizardAction]
    validator: Optional[Callable[[dict[str, Any]], tuple[bool, str]]] = None
    required: bool = False
    help_text: str = ""


# -- Setup Wizard ------------------------------------------------------------

class SetupWizard:
    """Interactive setup wizard for NEUGI Swarm v2.

    Guides users through a multi-step configuration process with support
    for multi-language, step skipping, progress saving, and resume.

    Usage:
        wizard = SetupWizard()
        wizard.run()
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        language: str = "en",
    ) -> None:
        """Initialize the wizard.

        Args:
            base_dir: Root NEUGI directory. Defaults to ~/.neugi.
            language: Language code for translations.
        """
        self.base_dir = base_dir or Path.home() / ".neugi"
        self.state = WizardState(language=language)
        self._steps: list[WizardStep] = []
        self._progress_file = self.base_dir / "wizard_progress.json"
        self._register_steps()

    def run(self) -> dict[str, Any]:
        """Run the wizard from start to finish.

        Returns:
            Final configuration dictionary.
        """
        self._load_progress()
        self._show_welcome()

        while self.state.current_step < len(self._steps):
            step = self._steps[self.state.current_step]
            self._show_step_header(step)

            action = step.renderer(self, self.state.config)
            self.state.action = action

            if action == WizardAction.QUIT:
                self._save_progress()
                console.print("\n[warning]Setup cancelled. Progress saved.[/warning]")
                return self.state.config

            elif action == WizardAction.BACK:
                if self.state.current_step > 0:
                    self.state.current_step -= 1
                continue

            elif action == WizardAction.SKIP:
                if not step.required:
                    self.state.mark_skip(self.state.current_step)
                    self.state.current_step += 1
                    continue
                else:
                    console.print("[warning]This step cannot be skipped.[/warning]")
                    continue

            elif action == WizardAction.REDO:
                self.state.completed_steps.discard(self.state.current_step)
                continue

            elif action == WizardAction.HELP:
                self._show_help(step)
                continue

            elif action == WizardAction.COMPLETE:
                self.state.mark_complete(self.state.current_step)
                break

            if step.validator:
                valid, message = step.validator(self.state.config)
                if not valid:
                    console.print(f"[error]{message}[/error]")
                    continue

            self.state.mark_complete(self.state.current_step)
            self.state.current_step += 1
            self._save_progress()

        self._show_completion()
        self._save_config()
        return self.state.config

    def _register_steps(self) -> None:
        """Register all wizard steps."""
        self._steps = [
            WizardStep(
                id="welcome",
                title_key="step_welcome_title",
                description_key="step_welcome_desc",
                renderer=self._render_welcome,
                required=False,
            ),
            WizardStep(
                id="llm",
                title_key="step_llm_title",
                description_key="step_llm_desc",
                renderer=self._render_llm_setup,
                validator=self._validate_llm,
                required=True,
                help_text="Choose between local (Ollama) or cloud (OpenAI/Anthropic) providers.",
            ),
            WizardStep(
                id="model",
                title_key="step_model_title",
                description_key="step_model_desc",
                renderer=self._render_model_selection,
                validator=self._validate_model,
                required=True,
                help_text="Test the model connection to ensure it works before proceeding.",
            ),
            WizardStep(
                id="channels",
                title_key="step_channels_title",
                description_key="step_channels_desc",
                renderer=self._render_channels,
                required=False,
                help_text="You can always configure channels later with 'neugi channels'.",
            ),
            WizardStep(
                id="security",
                title_key="step_security_title",
                description_key="step_security_desc",
                renderer=self._render_security,
                required=False,
                help_text="Higher security levels add more protection but may require more setup.",
            ),
            WizardStep(
                id="memory",
                title_key="step_memory_title",
                description_key="step_memory_desc",
                renderer=self._render_memory,
                required=False,
                help_text="Dreaming consolidates memories during idle periods for better recall.",
            ),
            WizardStep(
                id="plugins",
                title_key="step_plugins_title",
                description_key="step_plugins_desc",
                renderer=self._render_plugins,
                required=False,
                help_text="Plugins can be enabled or disabled later with 'neugi plugins'.",
            ),
            WizardStep(
                id="review",
                title_key="step_review_title",
                description_key="step_review_desc",
                renderer=self._render_review,
                required=True,
                help_text="Review all settings before starting NEUGI.",
            ),
        ]

    def _t(self, key: str, default: str = "") -> str:
        """Get a translated string."""
        lang = TRANSLATIONS.get(self.state.language, TRANSLATIONS["en"])
        return lang.get(key, TRANSLATIONS["en"].get(key, default))

    def _show_welcome(self) -> None:
        """Display the welcome screen."""
        banner = Text()
        banner.append("\n", style="cyan")
        banner.append("  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗\n", style="bold cyan")
        banner.append("  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝\n", style="bold cyan")
        banner.append("  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗\n", style="bold cyan")
        banner.append("  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║\n", style="bold cyan")
        banner.append("  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║\n", style="bold cyan")
        banner.append("  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝\n", style="bold cyan")
        banner.append("\n", style="cyan")
        console.print(banner)

        console.print(Panel(
            f"[primary]{self._t('welcome_desc')}[/primary]\n\n"
            f"[dim]v2.0.0 | {platform.system()} | Python {platform.python_version()}[/dim]",
            title=self._t("welcome_title"),
            border_style="cyan",
        ))

        language_choice = Prompt.ask(
            "\n[primary]Language / Bahasa / Idioma / Langue / Sprache / 言語[/primary]",
            choices=["en", "id", "es", "fr", "de", "jp"],
            default=self.state.language,
        )
        self.state.language = language_choice

        console.print(Rule(style="cyan"))

    def _show_step_header(self, step: WizardStep) -> None:
        """Display the header for a wizard step."""
        total = len(self._steps)
        current = self.state.current_step + 1

        progress_bar = self._make_progress_bar(current, total)

        title = self._t(step.title_key, step.title_key)
        desc = self._t(step.description_key, step.description_key)

        console.print(Panel(
            f"{progress_bar}\n\n"
            f"[primary]{title}[/primary]\n"
            f"[dim]{desc}[/dim]",
            title=f"{self._t('step')} {current} {self._t('of')} {total}",
            border_style="cyan",
        ))

    def _make_progress_bar(self, current: int, total: int) -> str:
        """Create a text-based progress bar."""
        width = 40
        filled = int((current / total) * width)
        bar = "█" * filled + "░" * (width - filled)
        pct = int((current / total) * 100)
        return f"[dim]{bar}[/dim] [primary]{pct}%[/primary]"

    def _show_help(self, step: WizardStep) -> None:
        """Display help for the current step."""
        if step.help_text:
            console.print(Panel(
                f"[info]{step.help_text}[/info]",
                title=self._t("help"),
                border_style="blue",
            ))
        else:
            console.print(f"[dim]{self._t('help')}: No additional help available.[/dim]")

    def _show_navigation(self) -> str:
        """Show navigation options and get user input."""
        options = []
        options.append(f"[primary]n[/primary] - {self._t('next')}")
        options.append(f"[primary]b[/primary] - {self._t('back')}")
        if not self._steps[self.state.current_step].required:
            options.append(f"[primary]s[/primary] - {self._t('skip')}")
        if self.state.is_complete(self.state.current_step):
            options.append(f"[primary]r[/primary] - {self._t('redo')}")
        options.append(f"[primary]h[/primary] - {self._t('help')}")
        options.append(f"[primary]q[/primary] - {self._t('quit')}")

        console.print(Rule(style="dim"))
        console.print("  ".join(options))

        choice = Prompt.ask(
            f"\n{self._t('select_option')}",
            choices=["n", "b", "s", "r", "h", "q"],
            default="n",
            show_choices=False,
        )

        action_map = {
            "n": WizardAction.NEXT,
            "b": WizardAction.BACK,
            "s": WizardAction.SKIP,
            "r": WizardAction.REDO,
            "h": WizardAction.HELP,
            "q": WizardAction.QUIT,
        }
        return action_map.get(choice, WizardAction.NEXT)

    # -- Step Renderers ------------------------------------------------------

    def _render_welcome(self, config: dict[str, Any]) -> WizardAction:
        """Render the welcome and system check step."""
        console.print(f"\n[info]{self._t('system_check')}[/info]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[primary]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking...", total=4)

            progress.update(task, description=f"{self._t('python_version')}...")
            time.sleep(0.2)
            progress.advance(task)

            progress.update(task, description=f"{self._t('platform')}...")
            time.sleep(0.2)
            progress.advance(task)

            progress.update(task, description=f"{self._t('disk_space')}...")
            time.sleep(0.2)
            progress.advance(task)

            progress.update(task, description=f"{self._t('memory_available')}...")
            time.sleep(0.2)
            progress.advance(task)

        table = Table(box=ROUNDED, border_style="cyan")
        table.add_column("Check", style="primary")
        table.add_column("Value", style="dim")
        table.add_column("Status", style="dim")

        try:
            usage = __import__("shutil").disk_usage(self.base_dir)
            free_gb = usage.free / (1024 ** 3)
            disk_status = "[success]OK[/success]" if free_gb > 1 else "[warning]Low[/warning]"
        except OSError:
            free_gb = 0
            disk_status = "[warning]Unknown[/warning]"

        table.add_row(self._t("python_version"), platform.python_version(), "[success]OK[/success]")
        table.add_row(self._t("platform"), f"{platform.system()} {platform.release()}", "[success]OK[/success]")
        table.add_row(self._t("disk_space"), f"{free_gb:.1f} GB", disk_status)

        try:
            import psutil
            mem = psutil.virtual_memory()
            mem_gb = mem.available / (1024 ** 3)
            table.add_row(self._t("memory_available"), f"{mem_gb:.1f} GB available", "[success]OK[/success]")
        except ImportError:
            table.add_row(self._t("memory_available"), "N/A (install psutil)", "[dim]Info[/dim]")

        console.print(table)

        config["system_check_passed"] = True
        return self._show_navigation()

    def _render_llm_setup(self, config: dict[str, Any]) -> WizardAction:
        """Render the LLM provider setup step."""
        console.print(f"\n[primary]{self._t('select_provider')}:[/primary]\n")

        console.print("  [primary]1[/primary] - " + self._t("ollama"))
        console.print("  [primary]2[/primary] - " + self._t("openai"))
        console.print("  [primary]3[/primary] - " + self._t("anthropic"))
        console.print()

        choice = Prompt.ask(
            self._t("select_option"),
            choices=["1", "2", "3"],
            default="1",
        )

        provider_map = {"1": "ollama", "2": "openai", "3": "anthropic"}
        provider = provider_map[choice]
        config["llm"] = {"provider": provider}

        if provider == "ollama":
            ollama_url = Prompt.ask(
                self._t("ollama_url"),
                default="http://localhost:11434",
            )
            config["llm"]["ollama_url"] = ollama_url

        elif provider in ("openai", "anthropic"):
            api_key = Prompt.ask(
                self._t("api_key"),
                password=True,
            )
            config["llm"]["api_key"] = api_key

            if provider == "openai":
                base_url = Prompt.ask(
                    self._t("base_url"),
                    default="https://api.openai.com/v1",
                )
                config["llm"]["base_url"] = base_url

        return self._show_navigation()

    def _render_model_selection(self, config: dict[str, Any]) -> WizardAction:
        """Render the model selection and testing step."""
        provider = config.get("llm", {}).get("provider", "ollama")

        model_options = {
            "ollama": [
                "qwen2.5-coder:7b",
                "llama3.2:3b",
                "llama3.1:8b",
                "mistral:7b",
                "phi3:3.8b",
            ],
            "openai": [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-3.5-turbo",
            ],
            "anthropic": [
                "claude-sonnet-4-20250514",
                "claude-haiku-4-20250514",
                "claude-3-5-sonnet-20241022",
            ],
        }

        models = model_options.get(provider, [])

        console.print(f"\n[primary]{self._t('select_model')}:[/primary]\n")
        for i, model in enumerate(models, 1):
            console.print(f"  [primary]{i}[/primary] - {model}")
        console.print()

        choice = Prompt.ask(
            self._t("select_option"),
            choices=[str(i) for i in range(1, len(models) + 1)],
            default="1",
        )

        model = models[int(choice) - 1]
        config["llm"]["model"] = model

        console.print(f"\n[info]{self._t('model_test')} ({model})...[/info]")

        success = self._test_model_connection(config)

        if success:
            console.print(f"[success]{self._t('model_success')}[/success]")
        else:
            console.print(f"[warning]{self._t('model_failed')}[/warning]")
            custom = Confirm.ask("Enter custom model name?", default=False)
            if custom:
                config["llm"]["model"] = Prompt.ask("Model name")

        config["llm"]["tested"] = success
        return self._show_navigation()

    def _render_channels(self, config: dict[str, Any]) -> WizardAction:
        """Render the channel configuration step."""
        console.print(f"\n[primary]{self._t('configure_channels')}:[/primary]\n")

        channels = {}
        channel_options = [
            ("telegram", self._t("telegram")),
            ("discord", self._t("discord")),
            ("slack", self._t("slack")),
            ("whatsapp", self._t("whatsapp")),
        ]

        for key, label in channel_options:
            if Confirm.ask(f"  Enable {label}?", default=False):
                token = Prompt.ask(f"  {label} {self._t('channel_token')}", default="", password=True)
                channels[key] = {"enabled": True, "token": token}
                console.print(f"  [success]{self._t('channel_enabled')}: {label}[/success]")

        config["channels"] = channels
        return self._show_navigation()

    def _render_security(self, config: dict[str, Any]) -> WizardAction:
        """Render the security settings step."""
        console.print(f"\n[primary]{self._t('security_level')}:[/primary]\n")
        console.print(f"  [primary]1[/primary] - {self._t('low')}")
        console.print(f"  [primary]2[/primary] - {self._t('medium')}")
        console.print(f"  [primary]3[/primary] - {self._t('high')}")
        console.print()

        choice = Prompt.ask(
            self._t("select_option"),
            choices=["1", "2", "3"],
            default="2",
        )

        security_levels = {"1": "low", "2": "medium", "3": "high"}
        config["security"] = {"level": security_levels[choice]}

        enable_auth = Confirm.ask(f"\n{self._t('enable_auth')}?", default=True)
        config["security"]["authentication"] = enable_auth

        enable_encryption = Confirm.ask(f"{self._t('enable_encryption')}?", default=True)
        config["security"]["encryption"] = enable_encryption

        return self._show_navigation()

    def _render_memory(self, config: dict[str, Any]) -> WizardAction:
        """Render the memory configuration step."""
        console.print(f"\n[primary]{self._t('memory')}:[/primary]\n")

        ttl = Prompt.ask(
            f"  {self._t('ttl_days')}",
            default="30",
        )
        config["memory"] = {"daily_ttl_days": int(ttl)}

        enable_dreaming = Confirm.ask(f"\n{self._t('enable_dreaming')}?", default=True)
        config["memory"]["dreaming_enabled"] = enable_dreaming

        if enable_dreaming:
            hour = Prompt.ask(
                f"  {self._t('dreaming_hour')}",
                default="3",
            )
            config["memory"]["dreaming_hour"] = int(hour)

        return self._show_navigation()

    def _render_plugins(self, config: dict[str, Any]) -> WizardAction:
        """Render the plugin selection step."""
        console.print(f"\n[primary]{self._t('select_plugins')}:[/primary]\n")

        available_plugins = [
            ("web_search", "Web Search", "Search the web for information"),
            ("code_executor", "Code Executor", "Execute code snippets safely"),
            ("file_manager", "File Manager", "Read and write files"),
            ("image_gen", "Image Generator", "Generate images from text"),
            ("scheduler", "Scheduler", "Schedule recurring tasks"),
        ]

        selected_plugins = []
        for plugin_id, name, desc in available_plugins:
            console.print(f"  [primary]{name}[/primary] - [dim]{desc}[/dim]")
            if Confirm.ask(f"    Enable?", default=True):
                selected_plugins.append(plugin_id)

        config["plugins"] = {"enabled": selected_plugins}
        return self._show_navigation()

    def _render_review(self, config: dict[str, Any]) -> WizardAction:
        """Render the final review step."""
        console.print(f"\n[primary]{self._t('review_config')}:[/primary]\n")

        table = Table(box=ROUNDED, border_style="cyan")
        table.add_column("Setting", style="primary")
        table.add_column("Value", style="dim")

        llm = config.get("llm", {})
        table.add_row(self._t("provider"), llm.get("provider", "Not set"))
        table.add_row(self._t("model"), llm.get("model", "Not set"))

        channels = config.get("channels", {})
        enabled_channels = [k for k, v in channels.items() if v.get("enabled")]
        table.add_row(self._t("channels"), ", ".join(enabled_channels) if enabled_channels else "None")

        security = config.get("security", {})
        table.add_row(self._t("security"), security.get("level", "medium"))

        memory = config.get("memory", {})
        table.add_row(self._t("memory"), f"TTL: {memory.get('daily_ttl_days', 30)}d, Dreaming: {memory.get('dreaming_enabled', True)}")

        plugins = config.get("plugins", {})
        table.add_row(self._t("plugins"), ", ".join(plugins.get("enabled", [])) or "None")

        console.print(table)

        if Confirm.ask(f"\n{self._t('start_neugi')}", default=True):
            config["start_on_complete"] = True
            return WizardAction.COMPLETE
        else:
            config["start_on_complete"] = False
            return self._show_navigation()

    # -- Validators ----------------------------------------------------------

    def _validate_llm(self, config: dict[str, Any]) -> tuple[bool, str]:
        """Validate LLM configuration."""
        llm = config.get("llm", {})
        if not llm.get("provider"):
            return False, "LLM provider is required"

        if llm["provider"] in ("openai", "anthropic") and not llm.get("api_key"):
            return False, "API key is required for cloud providers"

        return True, ""

    def _validate_model(self, config: dict[str, Any]) -> tuple[bool, str]:
        """Validate model configuration."""
        llm = config.get("llm", {})
        if not llm.get("model"):
            return False, "Model name is required"

        return True, ""

    # -- Helpers -------------------------------------------------------------

    def _test_model_connection(self, config: dict[str, Any]) -> bool:
        """Test the model connection.

        Args:
            config: Current configuration with LLM settings.

        Returns:
            True if the connection test succeeded.
        """
        llm = config.get("llm", {})
        provider = llm.get("provider", "ollama")

        try:
            if provider == "ollama":
                import urllib.request
                url = llm.get("ollama_url", "http://localhost:11434")
                req = urllib.request.Request(f"{url}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status == 200
            else:
                return True
        except Exception:
            return False

    def _save_progress(self) -> None:
        """Save wizard progress to disk."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

        progress_data = {
            "current_step": self.state.current_step,
            "completed_steps": list(self.state.completed_steps),
            "skipped_steps": list(self.state.skipped_steps),
            "config": self.state.config,
            "language": self.state.language,
            "timestamp": time.time(),
        }

        with open(self._progress_file, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)

    def _load_progress(self) -> bool:
        """Load saved wizard progress.

        Returns:
            True if progress was loaded successfully.
        """
        if not self._progress_file.exists():
            return False

        try:
            with open(self._progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.state.current_step = data.get("current_step", 0)
            self.state.completed_steps = set(data.get("completed_steps", []))
            self.state.skipped_steps = set(data.get("skipped_steps", []))
            self.state.config = data.get("config", {})
            self.state.language = data.get("language", "en")

            if self.state.current_step > 0:
                console.print(f"[info]Resuming from step {self.state.current_step + 1}...[/info]")

            return True
        except (json.JSONDecodeError, OSError):
            return False

    def _save_config(self) -> None:
        """Save the final configuration to config.json."""
        config_path = self.base_dir / "config.json"

        neugi_config = {
            "llm": self.state.config.get("llm", {}),
            "memory": {
                "daily_ttl_days": self.state.config.get("memory", {}).get("daily_ttl_days", 30),
                "dreaming_enabled": self.state.config.get("memory", {}).get("dreaming_enabled", True),
                "dreaming_hour": self.state.config.get("memory", {}).get("dreaming_hour", 3),
            },
            "channels": self.state.config.get("channels", {}),
            "security": self.state.config.get("security", {}),
            "plugins": self.state.config.get("plugins", {}),
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(neugi_config, f, indent=2, ensure_ascii=False)

        console.print(f"\n[success]Configuration saved to: {config_path}[/success]")

    def _show_completion(self) -> None:
        """Display the completion screen."""
        console.print(Panel(
            f"[success]{self._t('setup_complete')}[/success]\n\n"
            f"[dim]{self._t('setup_saved')}[/dim]",
            title="NEUGI Setup",
            border_style="green",
        ))
