"""
NEUGI v2 Interactive Chat
=========================

Rich terminal-based interactive chat interface for NEUGI Swarm v2.
Features streaming responses, command palette, tab completion,
conversation history, multi-line input, and session management.

Usage:
    from neugi_swarm_v2.cli.interactive import InteractiveChat

    chat = InteractiveChat()
    chat.run()
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.rule import Rule
    from rich.box import ROUNDED
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.theme import Theme
    from rich.layout import Layout
    from rich.columns import Columns
    from rich.align import Align
except ImportError:
    print("Error: 'rich' library is required. Install with: pip install rich")
    sys.exit(1)


# -- Theme -------------------------------------------------------------------

CHAT_THEME = Theme({
    "user": "bold green",
    "assistant": "bold cyan",
    "system": "dim yellow",
    "error": "bold red",
    "warning": "yellow",
    "info": "blue",
    "command": "bold magenta",
    "dim": "dim white",
    "primary": "bold cyan",
    "success": "bold green",
    "token_usage": "dim cyan",
    "agent_name": "bold bright_cyan",
})

console = Console(theme=CHAT_THEME)


# -- Command Palette ---------------------------------------------------------

class CommandType(Enum):
    """Types of commands available in chat mode."""
    SESSION = "session"
    AGENT = "agent"
    SYSTEM = "system"
    MEMORY = "memory"
    EXPORT = "export"


@dataclass
class ChatCommand:
    """Definition of a chat command.

    Attributes:
        name: Command name (e.g. '/new').
        description: Short description for help.
        handler: Callable that executes the command.
        category: Command category for grouping.
        aliases: Alternative command names.
        requires_args: Whether the command requires arguments.
    """
    name: str
    description: str
    handler: Callable[["InteractiveChat", str], str]
    category: CommandType = CommandType.SYSTEM
    aliases: list[str] = field(default_factory=list)
    requires_args: bool = False


class CommandPalette:
    """Manages the command palette for interactive chat.

    Provides command registration, lookup, tab completion,
    and help display functionality.
    """

    def __init__(self) -> None:
        self._commands: dict[str, ChatCommand] = {}
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        """Register the default set of chat commands."""
        commands = [
            ChatCommand(
                name="/new",
                description="Start a new conversation",
                handler=lambda chat, args: chat._cmd_new(args),
                category=CommandType.SESSION,
            ),
            ChatCommand(
                name="/reset",
                description="Reset the current session",
                handler=lambda chat, args: chat._cmd_reset(args),
                category=CommandType.SESSION,
            ),
            ChatCommand(
                name="/export",
                description="Export the current conversation",
                handler=lambda chat, args: chat._cmd_export(args),
                category=CommandType.EXPORT,
                requires_args=False,
            ),
            ChatCommand(
                name="/agent",
                description="Switch to a different agent",
                handler=lambda chat, args: chat._cmd_agent(args),
                category=CommandType.AGENT,
                requires_args=True,
            ),
            ChatCommand(
                name="/agents",
                description="List available agents",
                handler=lambda chat, args: chat._cmd_agents_list(args),
                category=CommandType.AGENT,
            ),
            ChatCommand(
                name="/model",
                description="Show or change the current model",
                handler=lambda chat, args: chat._cmd_model(args),
                category=CommandType.SYSTEM,
            ),
            ChatCommand(
                name="/tokens",
                description="Show token usage for this session",
                handler=lambda chat, args: chat._cmd_tokens(args),
                category=CommandType.SYSTEM,
            ),
            ChatCommand(
                name="/memory",
                description="Show memory statistics",
                handler=lambda chat, args: chat._cmd_memory(args),
                category=CommandType.MEMORY,
            ),
            ChatCommand(
                name="/recall",
                description="Recall memories matching a query",
                handler=lambda chat, args: chat._cmd_recall(args),
                category=CommandType.MEMORY,
                requires_args=True,
            ),
            ChatCommand(
                name="/help",
                description="Show all available commands",
                handler=lambda chat, args: chat._cmd_help(args),
                category=CommandType.SYSTEM,
            ),
            ChatCommand(
                name="/clear",
                description="Clear the screen",
                handler=lambda chat, args: chat._cmd_clear(args),
                category=CommandType.SYSTEM,
            ),
            ChatCommand(
                name="/quit",
                description="Exit chat mode",
                handler=lambda chat, args: chat._cmd_quit(args),
                category=CommandType.SYSTEM,
            ),
        ]

        for cmd in commands:
            self.register(cmd)

    def register(self, command: ChatCommand) -> None:
        """Register a new command.

        Args:
            command: The command to register.
        """
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

    def get(self, name: str) -> Optional[ChatCommand]:
        """Get a command by name.

        Args:
            name: Command name (with or without leading /).

        Returns:
            The command if found, None otherwise.
        """
        if not name.startswith("/"):
            name = "/" + name
        return self._commands.get(name)

    def execute(self, chat: "InteractiveChat", input_text: str) -> Optional[str]:
        """Execute a command from user input.

        Args:
            chat: The InteractiveChat instance.
            input_text: Full user input text.

        Returns:
            Response message from command handler, or None.
        """
        parts = input_text.strip().split(None, 1)
        if not parts:
            return None

        cmd_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        command = self.get(cmd_name)
        if command is None:
            return f"[error]Unknown command: {cmd_name}[/error]\nType [command]/help[/command] for available commands."

        if command.requires_args and not args:
            return f"[warning]Command {cmd_name} requires arguments.[/warning]"

        return command.handler(chat, args)

    def get_completions(self, prefix: str) -> list[str]:
        """Get command completions for a given prefix.

        Args:
            prefix: The text prefix to match.

        Returns:
            List of matching command names.
        """
        if not prefix.startswith("/"):
            prefix = "/" + prefix

        return [
            name for name in self._commands
            if name.startswith(prefix)
        ]

    def show_help(self) -> str:
        """Generate help text for all commands.

        Returns:
            Formatted help string.
        """
        by_category: dict[CommandType, list[ChatCommand]] = {}
        for cmd in self._commands.values():
            if cmd not in by_category.setdefault(cmd.category, []):
                by_category[cmd.category].append(cmd)

        lines = ["[primary]Available Commands:[/primary]\n"]

        category_names = {
            CommandType.SESSION: "Session",
            CommandType.AGENT: "Agent",
            CommandType.SYSTEM: "System",
            CommandType.MEMORY: "Memory",
            CommandType.EXPORT: "Export",
        }

        for category, cmds in sorted(by_category.items(), key=lambda x: x[0].value):
            lines.append(f"\n[command]{category_names.get(category, category.value)}:[/command]")
            for cmd in sorted(cmds, key=lambda c: c.name):
                lines.append(f"  [primary]{cmd.name:<12}[/primary] {cmd.description}")

        return "\n".join(lines)


# -- Token Tracker -----------------------------------------------------------

@dataclass
class TokenUsage:
    """Tracks token usage for a chat session.

    Attributes:
        input_tokens: Total input tokens used.
        output_tokens: Total output tokens used.
        total_tokens: Combined token count.
        request_count: Number of API requests made.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0

    def add_request(self, input_tokens: int, output_tokens: int) -> None:
        """Record a new API request.

        Args:
            input_tokens: Tokens in the request.
            output_tokens: Tokens in the response.
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.request_count += 1

    def reset(self) -> None:
        """Reset all counters."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.request_count = 0

    def format_summary(self) -> str:
        """Format a human-readable token usage summary."""
        return (
            f"[token_usage]Tokens: {self.total_tokens:,} "
            f"(input: {self.input_tokens:,}, output: {self.output_tokens:,}) "
            f"| Requests: {self.request_count}[/token_usage]"
        )


# -- Chat History ------------------------------------------------------------

class ChatHistory:
    """Manages conversation history with navigation support.

    Stores user inputs and assistant responses, supports
    up/down arrow navigation through previous inputs.
    """

    def __init__(self, max_entries: int = 1000) -> None:
        """Initialize the chat history.

        Args:
            max_entries: Maximum number of entries to retain.
        """
        self.entries: list[dict[str, Any]] = []
        self.input_history: list[str] = []
        self._input_index: int = -1
        self._max_entries = max_entries

    def add_user(self, message: str) -> None:
        """Add a user message to history.

        Args:
            message: The user's message text.
        """
        self.entries.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        self.input_history.append(message)
        self._input_index = -1
        self._trim()

    def add_assistant(self, message: str, token_usage: Optional[dict] = None) -> None:
        """Add an assistant response to history.

        Args:
            message: The assistant's response text.
            token_usage: Optional token usage data.
        """
        entry: dict[str, Any] = {
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
        if token_usage:
            entry["tokens"] = token_usage
        self.entries.append(entry)
        self._trim()

    def add_system(self, message: str) -> None:
        """Add a system message to history.

        Args:
            message: The system message text.
        """
        self.entries.append({
            "role": "system",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        self._trim()

    def get_previous_input(self) -> Optional[str]:
        """Get the previous user input (up arrow).

        Returns:
            Previous input string, or None if at start.
        """
        if not self.input_history:
            return None

        if self._input_index == -1:
            self._input_index = len(self.input_history) - 1
        elif self._input_index > 0:
            self._input_index -= 1

        return self.input_history[self._input_index]

    def get_next_input(self) -> Optional[str]:
        """Get the next user input (down arrow).

        Returns:
            Next input string, or None if at end.
        """
        if not self.input_history:
            return None

        if self._input_index == -1:
            return None

        if self._input_index < len(self.input_history) - 1:
            self._input_index += 1
            return self.input_history[self._input_index]
        else:
            self._input_index = -1
            return None

    def export(self, format: str = "json") -> str:
        """Export the conversation history.

        Args:
            format: Export format ('json' or 'markdown').

        Returns:
            Formatted conversation string.
        """
        if format == "json":
            return json.dumps(self.entries, indent=2, ensure_ascii=False)

        elif format == "markdown":
            lines = ["# Conversation Export\n"]
            lines.append(f"Exported: {datetime.now().isoformat()}\n")
            lines.append(f"Messages: {len(self.entries)}\n")
            lines.append("---\n")

            for entry in self.entries:
                role = entry.get("role", "unknown").title()
                content = entry.get("content", "")
                lines.append(f"## {role}\n\n{content}\n")

            return "\n".join(lines)

        return str(self.entries)

    def clear(self) -> None:
        """Clear all history."""
        self.entries.clear()
        self.input_history.clear()
        self._input_index = -1

    def _trim(self) -> None:
        """Trim history to max_entries."""
        if len(self.entries) > self._max_entries:
            self.entries = self.entries[-self._max_entries:]


# -- Chat UI -----------------------------------------------------------------

class ChatUI:
    """Renders the chat interface components.

    Provides methods for displaying messages, status bars,
    and other UI elements in the terminal.
    """

    def __init__(self, console: Optional[Console] = None) -> None:
        """Initialize the chat UI.

        Args:
            console: Rich console instance. Uses global console if None.
        """
        self.console = console or Console(theme=CHAT_THEME)

    def show_banner(self) -> None:
        """Display the NEUGI chat banner."""
        banner = Text()
        banner.append("\n", style="cyan")
        banner.append("  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗\n", style="bold cyan")
        banner.append("  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝\n", style="bold cyan")
        banner.append("  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗\n", style="bold cyan")
        banner.append("  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║\n", style="bold cyan")
        banner.append("  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║\n", style="bold cyan")
        banner.append("  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝\n", style="bold cyan")
        banner.append("\n", style="cyan")
        self.console.print(banner)

    def show_status_bar(
        self,
        agent: str = "Aurora",
        model: str = "qwen2.5-coder:7b",
        session_id: str = "default",
        token_usage: Optional[TokenUsage] = None,
    ) -> None:
        """Display the status bar at the top of the chat.

        Args:
            agent: Current agent name.
            model: Current model name.
            session_id: Current session identifier.
            token_usage: Token usage tracker.
        """
        parts = [
            f"[agent_name]{agent}[/agent_name]",
            f"[dim]|[/dim]",
            f"[dim]{model}[/dim]",
            f"[dim]|[/dim]",
            f"[dim]session: {session_id[:8]}[/dim]",
        ]

        if token_usage:
            parts.append(f"[dim]|[/dim]")
            parts.append(token_usage.format_summary())

        self.console.print(Rule(" ".join(parts), style="dim"))

    def show_user_message(self, message: str) -> None:
        """Display a user message.

        Args:
            message: The user's message text.
        """
        self.console.print(Panel(
            message,
            title="[user]You[/user]",
            border_style="green",
            title_align="left",
        ))

    def show_assistant_message(self, message: str, agent: str = "Aurora") -> None:
        """Display an assistant response.

        Args:
            message: The assistant's response text.
            agent: The agent name that responded.
        """
        if message.strip().startswith("```"):
            self.console.print(Panel(
                Syntax(message, "python", theme="monokai", word_wrap=True),
                title=f"[assistant]{agent}[/assistant]",
                border_style="cyan",
                title_align="left",
            ))
        else:
            self.console.print(Panel(
                message,
                title=f"[assistant]{agent}[/assistant]",
                border_style="cyan",
                title_align="left",
            ))

    def show_system_message(self, message: str) -> None:
        """Display a system message.

        Args:
            message: The system message text.
        """
        self.console.print(f"[system]⚙ {message}[/system]")

    def show_error(self, message: str) -> None:
        """Display an error message.

        Args:
            message: The error message text.
        """
        self.console.print(f"[error]✗ {message}[/error]")

    def show_streaming_indicator(self) -> None:
        """Show a streaming response indicator."""
        self.console.print("[dim]NEUGI is thinking...[/dim]", end="\r")

    def clear_streaming_indicator(self) -> None:
        """Clear the streaming indicator."""
        self.console.print(" " * 50, end="\r")

    def show_tool_usage(self, tool_name: str, args: str) -> None:
        """Display tool usage information.

        Args:
            tool_name: Name of the tool being used.
            args: Tool arguments.
        """
        self.console.print(f"[dim]🔧 Using tool: {tool_name}({args[:80]})[/dim]")

    def show_welcome(self) -> None:
        """Display the chat welcome message."""
        self.console.print(Panel(
            "[dim]Type your message and press Enter to chat.\n"
            "Use [command]/help[/command] to see all commands.\n"
            "Use [command]/quit[/command] to exit.\n"
            "Press [primary]Ctrl+P[/primary] for command palette.\n"
            "Use [primary]↑/↓[/primary] for input history.\n"
            "[primary]Shift+Enter[/primary] for multi-line input.[/dim]",
            title="[primary]NEUGI Interactive Chat[/primary]",
            border_style="cyan",
        ))


# -- Interactive Chat --------------------------------------------------------

class InteractiveChat:
    """Interactive chat mode for NEUGI Swarm v2.

    Provides a rich terminal-based chat interface with streaming
    responses, command palette, tab completion, conversation history,
    and session management.

    Usage:
        chat = InteractiveChat()
        chat.run()
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        agent: str = "Aurora",
        model: str = "qwen2.5-coder:7b",
    ) -> None:
        """Initialize the interactive chat.

        Args:
            base_dir: Root NEUGI directory. Defaults to ~/.neugi.
            agent: Default agent name.
            model: Default model name.
        """
        self.base_dir = base_dir or Path.home() / ".neugi"
        self.agent = agent
        self.model = model
        self.session_id = self._generate_session_id()
        self.ui = ChatUI(console)
        self.commands = CommandPalette()
        self.history = ChatHistory()
        self.token_usage = TokenUsage()
        self._running = False
        self._multimode = False
        self._buffer: list[str] = []

    def run(self) -> None:
        """Run the interactive chat loop."""
        self._running = True
        self.ui.show_banner()
        self.ui.show_welcome()
        self._show_status()

        try:
            while self._running:
                self._show_status()

                try:
                    user_input = self._get_input()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[warning]Use /quit to exit.[/warning]")
                    continue

                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    result = self.commands.execute(self, user_input)
                    if result:
                        console.print(result)
                    continue

                self._handle_message(user_input)

        except Exception as e:
            console.print(f"\n[error]Chat error: {e}[/error]")
        finally:
            self._running = False
            console.print("\n[info]Chat session ended.[/info]")

    def _get_input(self) -> str:
        """Get user input with history navigation.

        Returns:
            User input string.
        """
        if self._multimode:
            return self._get_multiline_input()

        try:
            user_input = Prompt.ask(
                f"\n[primary]You[/primary] ({self.agent})",
            )
            return user_input
        except (KeyboardInterrupt, EOFError):
            raise

    def _get_multiline_input(self) -> str:
        """Get multi-line input (Shift+Enter mode).

        Returns:
            Combined multi-line input string.
        """
        console.print("[dim]Multi-line mode. Type /send on a new line to submit.[/dim]")
        lines = []

        while True:
            try:
                line = input("... ")
                if line.strip() == "/send":
                    break
                lines.append(line)
            except (KeyboardInterrupt, EOFError):
                break

        return "\n".join(lines)

    def _handle_message(self, message: str) -> None:
        """Handle a user message.

        Args:
            message: The user's message text.
        """
        self.history.add_user(message)
        self.ui.show_user_message(message)

        self.ui.show_streaming_indicator()

        try:
            response = self._generate_response(message)
            self.ui.clear_streaming_indicator()

            self.history.add_assistant(response)
            self.ui.show_assistant_message(response, self.agent)

        except Exception as e:
            self.ui.clear_streaming_indicator()
            self.ui.show_error(f"Failed to get response: {e}")

    def _generate_response(self, message: str) -> str:
        """Generate a response from NEUGI.

        Args:
            message: The user's message.

        Returns:
            Generated response text.
        """
        try:
            from neugi_swarm_v2 import NeugiSwarmV2

            swarm = NeugiSwarmV2(base_dir=str(self.base_dir))
            response = swarm.chat(message, session_id=self.session_id)
            text = response.text if hasattr(response, "text") else str(response)

            self.token_usage.add_request(
                input_tokens=len(message) // 4,
                output_tokens=len(text) // 4,
            )

            return text

        except ImportError:
            return (
                f"[dim]NEUGI core not available. This is a demo response.\n\n"
                f"You said: {message}\n\n"
                f"Agent: {self.agent} | Model: {self.model}[/dim]"
            )
        except Exception as e:
            return f"[error]Error generating response: {e}[/error]"

    def _show_status(self) -> None:
        """Show the current status bar."""
        self.ui.show_status_bar(
            agent=self.agent,
            model=self.model,
            session_id=self.session_id,
            token_usage=self.token_usage,
        )

    def _generate_session_id(self) -> str:
        """Generate a new session ID.

        Returns:
            Unique session identifier.
        """
        import uuid
        return str(uuid.uuid4())[:8]

    # -- Command Handlers ----------------------------------------------------

    def _cmd_new(self, args: str) -> str:
        """Start a new conversation."""
        self.session_id = self._generate_session_id()
        self.history.clear()
        self.token_usage.reset()
        return f"[success]New session started: {self.session_id}[/success]"

    def _cmd_reset(self, args: str) -> str:
        """Reset the current session."""
        self.history.clear()
        self.token_usage.reset()
        return "[success]Session reset. History cleared.[/success]"

    def _cmd_export(self, args: str) -> str:
        """Export the current conversation."""
        fmt = args.strip() if args.strip() else "markdown"
        exported = self.history.export(format=fmt)

        export_path = self.base_dir / "exports"
        export_path.mkdir(parents=True, exist_ok=True)

        filename = f"session_{self.session_id}.{fmt}"
        filepath = export_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(exported)

        return f"[success]Conversation exported to: {filepath}[/success]"

    def _cmd_agent(self, args: str) -> str:
        """Switch to a different agent."""
        agent_name = args.strip()
        if not agent_name:
            return "[warning]Usage: /agent <name>[/warning]"

        self.agent = agent_name
        return f"[success]Switched to agent: {agent_name}[/success]"

    def _cmd_agents_list(self, args: str) -> str:
        """List available agents."""
        agents = [
            "Aurora", "Cipher", "Nova", "Pulse", "Quark",
            "Shield", "Spark", "Ink", "Nexus",
        ]
        agent_list = ", ".join(f"[primary]{a}[/primary]" for a in agents)
        return f"Available agents: {agent_list}"

    def _cmd_model(self, args: str) -> str:
        """Show or change the current model."""
        if args.strip():
            self.model = args.strip()
            return f"[success]Model changed to: {self.model}[/success]"
        return f"Current model: [primary]{self.model}[/primary]"

    def _cmd_tokens(self, args: str) -> str:
        """Show token usage."""
        return self.token_usage.format_summary()

    def _cmd_memory(self, args: str) -> str:
        """Show memory statistics."""
        memory_dir = self.base_dir / "data" / "memory"
        if memory_dir.exists():
            total_size = sum(
                f.stat().st_size for f in memory_dir.rglob("*") if f.is_file()
            )
            size_str = _format_size(total_size)
            return f"Memory storage: [primary]{size_str}[/primary] at {memory_dir}"
        return "Memory directory not found. Run setup first."

    def _cmd_recall(self, args: str) -> str:
        """Recall memories matching a query."""
        query = args.strip()
        if not query:
            return "[warning]Usage: /recall <query>[/warning]"
        return f"[info]Searching memory for: {query}[/info]\n[dim]Memory recall requires active NEUGI instance.[/dim]"

    def _cmd_help(self, args: str) -> str:
        """Show all available commands."""
        return self.commands.show_help()

    def _cmd_clear(self, args: str) -> str:
        """Clear the screen."""
        os.system("cls" if platform.system() == "Windows" else "clear")
        return ""

    def _cmd_quit(self, args: str) -> str:
        """Exit chat mode."""
        self._running = False
        return "[info]Goodbye![/info]"


# -- Helpers -----------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.1f} GB"


# -- Entry Point -------------------------------------------------------------

def main() -> None:
    """Main entry point for interactive chat."""
    chat = InteractiveChat()
    chat.run()


if __name__ == "__main__":
    main()
