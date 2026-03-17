#!/usr/bin/env python3
"""
🤖 NEUGI ASSISTANT
==================
Smart assistant using qwen3.5:cloud (Ollama Cloud)
With ENHANCED MEMORY - remembers conversations and user preferences!
Now with ADAPTIVE COMPUTATION, LRU CACHING, and GLOBAL WORKSPACE awareness for reduced token usage and increased autonomy.

Version: 26.0.0
Date: March 17, 2026
"""

import os
import json
import requests
import urllib.request
import re
import hashlib
import time
from typing import Optional, Dict, List
from collections import OrderedDict

try:
    from neugi_swarm_net import swarm_net
except ImportError:
    swarm_net = None

try:
    from neugi_swarm_tools import ToolManager
    from neugi_swarm_agents import AgentManager
except ImportError:
    ToolManager = None
    AgentManager = None

# ============================================================
# CONFIG
# ============================================================

NEUGI_DIR = os.path.expanduser("~/neugi")
OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3.5:cloud"
FALLBACK_MODEL = "nemotron-3-super:cloud"

# ============================================================
# COLORS
# ============================================================


class C:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


# ============================================================
# NEUGI ASSISTANT CLASS
# ============================================================


class NeugiAssistant:
    """Smart assistant with memory, adaptive computation, and LRU caching"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.memory_file = os.path.join(NEUGI_DIR, "data", f"memory_{session_id}.json")
        self.system_prompt = self._load_system_prompt()
        self.conversation_history = []
        self._load_memory()
        # Simple cache for frequent queries (exact matches)
        self.quick_response_cache = {
            "hello": "Hello! How can I assist you today?",
            "hi": "Hi there! What do you need help with?",
            "help": "I'm NEUGI, your AI assistant. I can help with coding, research, writing, analysis, and more. What would you like to do?",
            "who are you": "I'm NEUGI (Neural General Intelligence), an autonomous AI assistant powered by Ollama.",
            "what can you do": "I can help with coding, research, writing, data analysis, system administration, and more through my specialized agent swarm.",
            "thank you": "You're welcome! Happy to help.",
            "thanks": "Anytime! Let me know if you need anything else.",
        }
        # Patterns for simple queries that can be answered from memory or cache
        self.simple_patterns = [
            r"^hello\s*$",
            r"^hi\s*$",
            r"^help\s*$",
            r"^who\s+are\s+you\s*$",
            r"^what\s+can\s+you\s+do\s*$",
            r"^thank\s*you\s*$",
            r"^thanks\s*$",
            r"^how\s+are\s+you\s*$",
            r"^what\s+is\s+your\s+name\s*$",
        ]
        self.simple_patterns_compiled = [re.compile(p, re.IGNORECASE) for p in self.simple_patterns]
        # LRU cache for LLM responses to reduce redundant computations
        self.llm_response_cache = OrderedDict()
        self.max_llm_cache_size = 100  # Maximum number of cached LLM responses

    # ============================================================
    # MEMORY METHODS
    # ============================================================

    def _load_system_prompt(self) -> str:
        """Load system prompt from file or return default"""
        prompt_path = os.path.join(NEUGI_DIR, "data", "system_prompt.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r") as f:
                return f.read().strip()
        return """You are NEUGI, a helpful AI assistant. You are knowledgeable, friendly, and eager to help. 
You have access to a swarm of specialized agents and tools. Provide clear, concise, and accurate responses."""

    def _load_memory(self):
        """Load conversation memory from file"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    data = json.load(f)
                    self.conversation_history = data.get("history", [])
            except Exception:
                self.conversation_history = []
        else:
            self.conversation_history = []

    def _save_memory(self):
        """Save conversation memory to file"""
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        with open(self.memory_file, "w") as f:
            json.dump(
                {
                    "session_id": self.session_id,
                    "history": self.conversation_history[-1000:],  # Keep last 1000 messages
                    "timestamp": time.time(),
                },
                f,
                indent=2,
            )

    def _save_to_memory(self, role: str, content: str):
        """Save a message to memory"""
        self.conversation_history.append(
            {"role": role, "content": content, "timestamp": time.time()}
        )
        # Save periodically to avoid too many disk writes
        if len(self.conversation_history) % 10 == 0:
            self._save_memory()

    def _get_conversation_context(self, limit: int = 5) -> str:
        """Get recent conversation context for prompt"""
        if not self.conversation_history:
            return ""
        recent = self.conversation_history[-limit:]
        context_lines = []
        for msg in recent:
            role = "User" if msg["role"] == "user" else "NEUGI"
            context_lines.append(f"{role}: {msg['content']}")
        return "\n".join(context_lines)

    def _get_user_memories(self, limit: int = 3) -> str:
        """Get user-specific memories (preferences, facts) from conversation history"""
        facts = []
        for msg in self.conversation_history[-20:]:  # Look at recent messages
            if msg["role"] == "user":
                content = msg["content"].strip()
                # Simple heuristic: statements that look like facts (short, declarative)
                if len(content) < 100 and len(content.split()) < 20 and not content.endswith("?"):
                    # Avoid questions and commands
                    if not (
                        "please" in content.lower()
                        or "can you" in content.lower()
                        or "could you" in content.lower()
                        or "would you" in content.lower()
                    ):
                        facts.append(content)
        if facts:
            # Deduplicate while preserving order
            seen = set()
            unique_facts = []
            for f in facts:
                if f not in seen:
                    seen.add(f)
                    unique_facts.append(f)
            return "User facts: " + "; ".join(unique_facts[-limit:])
        return ""

    # ============================================================
    # ADAPTIVE COMPUTATION & CACHING METHODS
    # ============================================================

    def _is_simple_query(self, message: str) -> bool:
        """Check if a query is simple enough to answer from cache or memory without LLM"""
        message_clean = message.strip().lower()
        # Check exact cache match
        if message_clean in self.quick_response_cache:
            return True
        # Check pattern match
        for pattern in self.simple_patterns_compiled:
            if pattern.match(message_clean):
                return True
        # Check if it's a very short question that might be in memory
        if len(message_clean.split()) <= 3 and any(
            word in message_clean for word in ["what", "who", "where", "when", "how"]
        ):
            # Could be answered from recent memory
            return True
        return False

    def _get_quick_response(self, message: str) -> Optional[str]:
        """Get a quick response from cache or memory for simple queries"""
        message_clean = message.strip().lower()
        # Check cache first
        if message_clean in self.quick_response_cache:
            return self.quick_response_cache[message_clean]
        # Check if we have a similar question in memory (last 50 exchanges)
        for i in range(len(self.conversation_history) - 1, -1, -1):
            entry = self.conversation_history[i]
            if entry["role"] == "user":
                # Simple similarity: at least 2 common words (excluding very common words)
                user_words = set(entry["content"].lower().split())
                message_words = set(message_clean.split())
                common = user_words & message_words
                # Filter out very common words
                stop_words = {
                    "the",
                    "a",
                    "an",
                    "and",
                    "or",
                    "but",
                    "in",
                    "on",
                    "at",
                    "to",
                    "for",
                    "of",
                    "with",
                    "by",
                    "is",
                    "are",
                    "was",
                    "were",
                    "be",
                    "been",
                    "being",
                }
                meaningful_common = [w for w in common if w not in stop_words and len(w) > 2]
                if len(meaningful_common) >= 2:
                    # Found a similar question, return the assistant's response if it exists and is recent
                    if (
                        i + 1 < len(self.conversation_history)
                        and self.conversation_history[i + 1]["role"] == "assistant"
                    ):
                        return self.conversation_history[i + 1]["content"]
        return None

    def _get_llm_cached_response(self, message: str) -> Optional[str]:
        """Get a cached LLM response if available, using LRU cache"""
        # Create a cache key based on the message and recent conversation history
        # We use the last 5 messages to capture context
        recent_history = self.conversation_history[-5:]
        # Convert history to a stable string representation
        history_str = str(recent_history)
        # Create a hash of the message + history to use as cache key
        key_string = message + history_str
        key = hashlib.sha256(key_string.encode()).hexdigest()

        if key in self.llm_response_cache:
            # Move to end to mark as recently used
            response = self.llm_response_cache.pop(key)
            self.llm_response_cache[key] = response
            return response
        return None

    def _save_llm_cached_response(self, message: str, response: str):
        """Save an LLM response to the LRU cache"""
        # Create a cache key based on the message and recent conversation history
        recent_history = self.conversation_history[-5:]
        history_str = str(recent_history)
        key_string = message + history_str
        key = hashlib.sha256(key_string.encode()).hexdigest()

        # Add to cache
        self.llm_response_cache[key] = response
        # If cache exceeds maximum size, remove the least recently used item
        if len(self.llm_response_cache) > self.max_llm_cache_size:
            self.llm_response_cache.popitem(last=False)

    def _check_confidence_early_exit(self, current_response: str) -> float:
        """
        Simple confidence heuristic for early exit:
        - Based on response completeness, length, and vocabulary diversity
        - Returns a score between 0.0 and 1.0
        """
        if not current_response or len(current_response.strip()) < 10:
            return 0.0
        text = current_response.strip()
        # Check for complete sentences (ending with ., !, ?)
        sentences = re.split(r"[.!?]+", text)
        complete_sentences = [s.strip() for s in sentences if s.strip()]
        if len(complete_sentences) == 0:
            return 0.1
        # Heuristic: more complete sentences and longer length = higher confidence
        length_score = min(len(text) / 200, 1.0)  # Normalize to 200 chars
        sentence_score = min(len(complete_sentences) / 3, 1.0)  # Normalize to 3 sentences
        # Vocabulary diversity (type-token ratio)
        words = text.lower().split()
        if len(words) > 0:
            vocab_diversity = len(set(words)) / len(words)
        else:
            vocab_diversity = 0.0
        return length_score * 0.4 + sentence_score * 0.4 + vocab_diversity * 0.2

    # ============================================================
    # MAIN CHAT METHODS
    # ============================================================

    def chat(self, message: str) -> str:
        """Send message and get response with memory context, adaptive computation, and caching"""

        # Save user message to memory (so it's available for quick response and context)
        self._save_to_memory("user", message)

        # Check if Ollama is running
        if not self.is_ollama_running():
            response = self._offline_response(message)
            self._save_to_memory("assistant", response)
            return response

        # ADAPTIVE COMPUTATION: Check if this is a simple query we can answer quickly
        if self._is_simple_query(message):
            quick_resp = self._get_quick_response(message)
            if quick_resp is not None:
                self._save_to_memory("assistant", quick_resp)
                return quick_resp
            # Fallback to a simple canned response if not in cache/memory
            if len(message.strip().split()) <= 2:
                resp = "I'm not sure I understand. Could you please clarify or ask a different question?"
                self._save_to_memory("assistant", resp)
                return resp

        # Check LLM cache first (to avoid redundant LLM calls)
        cached_resp = self._get_llm_cached_response(message)
        if cached_resp is not None:
            self._save_to_memory("assistant", cached_resp)
            return cached_resp

        # Build context with memory (conversation + user facts)
        context = self._get_conversation_context()
        user_memories = self._get_user_memories()

        # Combine system prompt with context
        full_prompt = self.system_prompt
        if context:
            full_prompt += "\n" + context
        if user_memories:
            full_prompt += "\n" + user_memories
        full_prompt += f"\n\nUser: {message}\n\nNEUGI:"

        try:
            # Try Ollama Cloud model with generate endpoint (simpler for context)
            payload = {"model": MODEL, "prompt": full_prompt, "stream": False}
            response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "").strip()
                # Save the computed response to the LLM cache for future use
                self._save_llm_cached_response(message, response_text)
                # Note: We don't do early exit here because we already got the full response,
                # but we could truncate if we had streaming. For non-streaming, we return the full response.
                self._save_to_memory("assistant", response_text)
                return response_text
            else:
                # Try fallback model
                payload["model"] = FALLBACK_MODEL
                response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get("response", "").strip()
                    # Save the computed response to the LLM cache for future use
                    self._save_llm_cached_response(message, response_text)
                    self._save_to_memory("assistant", response_text)
                    return response_text
                else:
                    return self._error_response(f"Ollama error: {response.status_code}")
        except requests.exceptions.RequestException as e:
            return self._error_response(f"Connection error: {str(e)}")
        except Exception as e:
            return self._error_response(f"Unexpected error: {str(e)}")

    def chat_stream(self, message: str, callback=None, depth=0):
        """Stream response from Ollama with early exit capability"""
        # Save user message
        self._save_to_memory("user", message)

        if not self.is_ollama_running():
            response = self._offline_response(message)
            self._save_to_memory("assistant", response)
            if callback:
                callback(response)
            return

        # Check for simple query first (non-streaming for simplicity)
        if self._is_simple_query(message):
            quick_resp = self._get_quick_response(message)
            if quick_resp is not None:
                self._save_to_memory("assistant", quick_resp)
                if callback:
                    callback(quick_resp)
                return

        # Check LLM cache first (to avoid redundant LLM calls)
        cached_resp = self._get_llm_cached_response(message)
        if cached_resp is not None:
            self._save_to_memory("assistant", cached_resp)
            if callback:
                callback(cached_resp)
            return

        # Build context
        context = self._get_conversation_context()
        user_memories = self._get_user_memories()
        full_prompt = self.system_prompt
        if context:
            full_prompt += "\n" + context
        if user_memories:
            full_prompt += "\n" + user_memories
        full_prompt += f"\n\nUser: {message}\n\nNEUGI:"

        try:
            payload = {"model": MODEL, "prompt": full_prompt, "stream": True}
            response = requests.post(
                f"{OLLAMA_URL}/api/generate", json=payload, stream=True, timeout=30
            )

            if response.status_code == 200:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode("utf-8"))
                            if "response" in data:
                                chunk = data["response"]
                                full_response += chunk
                                if callback:
                                    callback(chunk)
                                # ADAPTIVE COMPUTATION: Check for early exit based on confidence
                                confidence = self._check_confidence_early_exit(full_response)
                                if confidence > 0.92:  # High confidence threshold
                                    break
                        except json.JSONDecodeError:
                            continue
                # Save the final response (possibly truncated) to LLM cache
                self._save_llm_cached_response(message, full_response.strip())
                # Save the final response (possibly truncated)
                self._save_to_memory("assistant", full_response.strip())
            else:
                # Try fallback
                payload["model"] = FALLBACK_MODEL
                response = requests.post(
                    f"{OLLAMA_URL}/api/generate", json=payload, stream=True, timeout=30
                )
                if response.status_code == 200:
                    full_response = ""
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line.decode("utf-8"))
                                if "response" in data:
                                    chunk = data["response"]
                                    full_response += chunk
                                    if callback:
                                        callback(chunk)
                                    confidence = self._check_confidence_early_exit(full_response)
                                    if confidence > 0.92:  # High confidence threshold
                                        break
                            except json.JSONDecodeError:
                                continue
                    # Save the final response (possibly truncated) to LLM cache
                    self._save_llm_cached_response(message, full_response.strip())
                    self._save_to_memory("assistant", full_response.strip())
                else:
                    error_msg = self._error_response(f"Ollama error: {response.status_code}")
                    if callback:
                        callback(error_msg)
                    self._save_to_memory("assistant", error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = self._error_response(f"Connection error: {str(e)}")
            if callback:
                callback(error_msg)
            self._save_to_memory("assistant", error_msg)
        except Exception as e:
            error_msg = self._error_response(f"Unexpected error: {str(e)}")
            if callback:
                callback(error_msg)
            self._save_to_memory("assistant", error_msg)

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def is_ollama_running(self) -> bool:
        """Check if Ollama server is running"""
        try:
            response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            return response.status_code == 200
        except:
            return False

    def _offline_response(self, message: str) -> str:
        """Provide a response when Ollama is not available"""
        return "I'm currently offline as my AI engine (Ollama) is not running. Please start Ollama and try again."

    def _error_response(self, error_msg: str) -> str:
        """Format an error message"""
        return f"I encountered an error: {error_msg}\nPlease try again or contact support if the issue persists."

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    def get_conversation_history(self) -> List[Dict]:
        """Get the full conversation history"""
        return self.conversation_history.copy()

    def clear_memory(self):
        """Clear conversation memory"""
        self.conversation_history = []
        if os.path.exists(self.memory_file):
            os.remove(self.memory_file)
        # Clear the LLM cache as well when memory is cleared
        self.llm_response_cache.clear()


# ============================================================
# MAIN (for testing)
# ============================================================

if __name__ == "__main__":
    import time

    assistant = NeugiAssistant()
    print("NEUGI Assistant is ready! Type 'quit' to exit.")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["quit", "exit", "bye"]:
            break
        response = assistant.chat(user_input)
        print(f"\nNEUGI: {response}")
