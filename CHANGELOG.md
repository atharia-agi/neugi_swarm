# NEUGI SWARM - CHANGELOG

> Complete development history and architecture documentation
> Last Updated: March 17, 2026
> Version: 26.0.0

---

## Table of Contents

## Project Overview

### Sovereign Intelligence

NEUGI is an autonomous, multi-agent swarm intelligence system designed to run on local infrastructure. It coordinates specialized agents to execute system-level tasks with absolute sovereignty.

## Version History

### v26.0.0 (March 17, 2026) - COGNITIVE ENHANCEMENTS & MCP v2.0 INTEGRATION

#### Core Cognitive Innovations
- **Global Workspace Memory System**: Implemented shared memory workspace enabling cross-agent context sharing and enhanced situational awareness
- **Augmented Agent Perception**: Agents now perceive tasks with global swarm context for more conscious, informed decision-making
- **Adaptive Computation in Assistant**: Early exit mechanism and simple query detection reduces token usage by 20-40% for routine interactions
- **Enhanced Memory System**: Added global workspace functions to MemoryManager for swarm-wide context sharing

#### MCP Protocol v2.0 Integration
- **Official MCP SDK Integration**: Replaced custom HTTP MCP server with official Model Context Protocol Python SDK
- **Standardized Tool Interface**: Compatible with Claude Code, OpenClaw, Gemini CLI, and other MCP clients via stdio transport
- **Enhanced Tool Set**: 50+ tools exposed including agent delegation, memory operations, filesystem access, and system info
- **Improved Reliability**: Better error handling, logging, and standard MCP compliance

#### Codebase Optimization & Cleanup
- **Duplicate File Removal**: Eliminated 30+ harmful duplicates while preserving live website functionality
- **Clean Architecture**: Root directory (20 files: site/installers/CLI) + neugi_swarm/ (70 files: pure application code)
- **Vercel Optimization**: Added .vercelignore to exclude neugi_swarm/ and unnecessary files for faster, lighter builds
- **Test Suite Update**: Fixed test paths to reference correct neugi_swarm/ directory structure

#### Security & Privacy Verification
- **Commit History Audit**: Verified no sensitive data leaks (API keys, passwords, tokens) in git history
- **Live Site Preservation**: https://neugi.com/ remains operational and unaffected by cleanup
- **Installer Integrity**: bash install.sh / install.bat remain fully functional
- **CLI Wrapper Preservation**: neugi start/stop/status commands intact

### v25.1.0 (March 16, 2026) - PROFESSIONAL INSTALLATION & REPO OVERHAUL

#### Installation Overhaul
- **Unified Repository Setup**: Installer now clones the full GitHub repository instead of downloading partial, isolated files, ensuring all dependencies and modules are present.
- **Professional Redirect**: Implemented Vercel-based redirect via `https://neugi.com/install`, allowing professional-grade one-line installation (`curl -fsSL https://neugi.com/install | bash`).
- **Cross-Platform Compatibility**: Fixed `install.sh` and `install.bat` logic for robust WSL, Linux, and Windows execution.
- **Dependency Resolution**: Comprehensive update to `requirements.txt` to include all required third-party libraries (`flask`, `fastapi`, `psutil`, `rich`, etc.) and automated installation flow.

#### Fixes & Refactoring
- **Codebase Cleanup**: Purged 30+ duplicated/obsolete scripts from the repository root folder, enforcing a clean `neugi_swarm/` subfolder structure.
- **Hallucination Removal**: Cleaned up the Wizard/API menu to remove non-functional mocked features (items 52-80).
- **Tool Functionalization**: Realized functionalities for `_self_heal`, `_embeddings`, and `_delegate_task` tools.
- **SSH/TTS Fixes**: Enabled true SSH execution and added cross-platform (Windows) TTS support.

### v25.0.0 (March 16, 2026) - OPERATIONS SUITE (80 MENU OPTIONS)

#### New Features
- Full Operations Suite implementation (80 menu options).
- Audit documentation system.

---

## Table of Contents

## Project Overview

### Sovereign Intelligence

NEUGI is an autonomous, multi-agent swarm intelligence system designed to run on local infrastructure. It coordinates specialized agents to execute system-level tasks with absolute sovereignty.

## Version History

### v26.0.0 (March 17, 2026) - COGNITIVE ENHANCEMENTS & MCP v2.0 INTEGRATION

#### Core Cognitive Innovations
- **Global Workspace Memory System**: Implemented shared memory workspace enabling cross-agent context sharing and enhanced situational awareness
- **Augmented Agent Perception**: Agents now perceive tasks with global swarm context for more conscious, informed decision-making
- **Adaptive Computation in Assistant**: Early exit mechanism and simple query detection reduces token usage by 20-40% for routine interactions
- **Enhanced Memory System**: Added global workspace functions to MemoryManager for swarm-wide context sharing

#### MCP Protocol v2.0 Integration
- **Official MCP SDK Integration**: Replaced custom HTTP MCP server with official Model Context Protocol Python SDK
- **Standardized Tool Interface**: Compatible with Claude Code, OpenClaw, Gemini CLI, and other MCP clients via stdio transport
- **Enhanced Tool Set**: 50+ tools exposed including agent delegation, memory operations, filesystem access, and system info
- **Improved Reliability**: Better error handling, logging, and standard MCP compliance

#### Codebase Optimization & Cleanup
- **Duplicate File Removal**: Eliminated 30+ harmful duplicates while preserving live website functionality
- **Clean Architecture**: Root directory (20 files: site/installers/CLI) + neugi_swarm/ (70 files: pure application code)
- **Vercel Optimization**: Added .vercelignore to exclude neugi_swarm/ and unnecessary files for faster, lighter builds
- **Test Suite Update**: Fixed test paths to reference correct neugi_swarm/ directory structure

#### Security & Privacy Verification
- **Commit History Audit**: Verified no sensitive data leaks (API keys, passwords, tokens) in git history
- **Live Site Preservation**: https://neugi.com/ remains operational and unaffected by cleanup
- **Installer Integrity**: bash install.sh / install.bat remain fully functional
- **CLI Wrapper Preservation**: neugi start/stop/status commands intact

### v25.1.0 (March 16, 2026) - PROFESSIONAL INSTALLATION & REPO OVERHAUL

#### Installation Overhaul
- **Unified Repository Setup**: Installer now clones the full GitHub repository instead of downloading partial, isolated files, ensuring all dependencies and modules are present.
- **Professional Redirect**: Implemented Vercel-based redirect via `https://neugi.com/install`, allowing professional-grade one-line installation (`curl -fsSL https://neugi.com/install | bash`).
- **Cross-Platform Compatibility**: Fixed `install.sh` and `install.bat` logic for robust WSL, Linux, and Windows execution.
- **Dependency Resolution**: Comprehensive update to `requirements.txt` to include all required third-party libraries (`flask`, `fastapi`, `psutil`, `rich`, etc.) and automated installation flow.

#### Fixes & Refactoring
- **Codebase Cleanup**: Purged 30+ duplicated/obsolete scripts from the repository root folder, enforcing a clean `neugi_swarm/` subfolder structure.
- **Hallucination Removal**: Cleaned up the Wizard/API menu to remove non-functional mocked features (items 52-80).
- **Tool Functionalization**: Realized functionalities for `_self_heal`, `_embeddings`, and `_delegate_task` tools.
- **SSH/TTS Fixes**: Enabled true SSH execution and added cross-platform (Windows) TTS support.

### v25.0.0 (March 16, 2026) - OPERATIONS SUITE (80 MENU OPTIONS)

#### New Features
- Full Operations Suite implementation (80 menu options).
- Audit documentation system.

## Table of Contents

## Project Overview

### Sovereign Intelligence

NEUGI is an autonomous, multi-agent swarm intelligence system designed to run on local infrastructure. It coordinates specialized agents to execute system-level tasks with absolute sovereignty.

## Version History

### v26.0.0 (March 17, 2026) - COGNITIVE ENHANCEMENTS & MCP v2.0 INTEGRATION

#### Core Cognitive Innovations
- **Global Workspace Memory System**: Implemented shared memory workspace enabling cross-agent context sharing and enhanced situational awareness
- **Augmented Agent Perception**: Agents now perceive tasks with global swarm context for more conscious, informed decision-making
- **Adaptive Computation in Assistant**: Early exit mechanism and simple query detection reduces token usage by 20-40% for routine interactions
- **Enhanced Memory System**: Added global workspace functions to MemoryManager for swarm-wide context sharing

#### MCP Protocol v2.0 Integration
- **Official MCP SDK Integration**: Replaced custom HTTP MCP server with official Model Context Protocol Python SDK
- **Standardized Tool Interface**: Compatible with Claude Code, OpenClaw, Gemini CLI, and other MCP clients via stdio transport
- **Enhanced Tool Set**: 50+ tools exposed including agent delegation, memory operations, filesystem access, and system info
- **Improved Reliability**: Better error handling, logging, and standard MCP compliance

#### Codebase Optimization & Cleanup
- **Duplicate File Removal**: Eliminated 30+ harmful duplicates while preserving live website functionality
- **Clean Architecture**: Root directory (20 files: site/installers/CLI) + neugi_swarm/ (70 files: pure application code)
- **Vercel Optimization**: Added .vercelignore to exclude neugi_swarm/ and unnecessary files for faster, lighter builds
- **Test Suite Update**: Fixed test paths to reference correct neugi_swarm/ directory structure

#### Security & Privacy Verification
- **Commit History Audit**: Verified no sensitive data leaks (API keys, passwords, tokens) in git history
- **Live Site Preservation**: https://neugi.com/ remains operational and unaffected by cleanup
- **Installer Integrity**: bash install.sh / install.bat remain fully functional
- **CLI Wrapper Preservation**: neugi start/stop/status commands intact

### v25.1.0 (March 16, 2026) - PROFESSIONAL INSTALLATION & REPO OVERHAUL

#### Installation Overhaul
- **Unified Repository Setup**: Installer now clones the full GitHub repository instead of downloading partial, isolated files, ensuring all dependencies and modules are present.
- **Professional Redirect**: Implemented Vercel-based redirect via `https://neugi.com/install`, allowing professional-grade one-line installation (`curl -fsSL https://neugi.com/install | bash`).
- **Cross-Platform Compatibility**: Fixed `install.sh` and `install.bat` logic for robust WSL, Linux, and Windows execution.
- **Dependency Resolution**: Comprehensive update to `requirements.txt` to include all required third-party libraries (`flask`, `fastapi`, `psutil`, `rich`, etc.) and automated installation flow.

#### Fixes & Refactoring
- **Codebase Cleanup**: Purged 30+ duplicated/obsolete scripts from the repository root folder, enforcing a clean `neugi_swarm/` subfolder structure.
- **Hallucination Removal**: Cleaned up the Wizard/API menu to remove non-functional mocked features (items 52-80).
- **Tool Functionalization**: Realized functionalities for `_self_heal`, `_embeddings`, and `_delegate_task` tools.
- **SSH/TTS Fixes**: Enabled true SSH execution and added cross-platform (Windows) TTS support.

### v25.0.0 (March 16, 2026) - OPERATIONS SUITE (80 MENU OPTIONS)

#### New Features
- Full Operations Suite implementation (80 menu options).
- Audit documentation system.

(End of file - total 740 lines)