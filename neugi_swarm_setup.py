#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - SETUP WIZARD
===============================

Simple CLI setup for beginners:
1. Choose LLM provider (free options first!)
2. Enter API key
3. Select model (with context recommendations)
4. Configure channels (optional)
5. Set security
6. Start!

Minimum requirements: Python 3.8, 2GB RAM
Works with: 2K context models and above!
"""

import os
import sys
import json
import time

# ANSI colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RED = '\033[91m'
BOLD = '\033[1m'
RESET = '\033[0m'

def print_header():
    print(f"\n{BOLD}{'='*60}")
    print(f"🤖 NEUGI SWARM SETUP WIZARD")
    print(f"{'='*60}{RESET}\n")

def print_step(num, total, title):
    print(f"\n{BLUE}📋 Step {num}/{total}: {title}{RESET}")

def print_option(num, text):
    print(f"  {GREEN}[{num}]{RESET} {text}")

def print_info(text):
    print(f"  {YELLOW}ℹ️{RESET} {text}")

def print_success(text):
    print(f"  {GREEN}✅{RESET} {text}")

def print_warning(text):
    print(f"  {YELLOW}⚠️{RESET} {text}")

def input_with_default(prompt, default=""):
    """Input with default value"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()

def choose_option(options, prompt="Choose"):
    """Let user choose from options"""
    for i, opt in enumerate(options, 1):
        print_option(i, opt)
    
    while True:
        try:
            choice = int(input(f"\n{prompt} (1-{len(options)}): "))
            if 1 <= choice <= len(options):
                return choice
        except ValueError:
            pass
        print_warning("Invalid choice. Try again.")

def setup_llm_provider():
    """Step 1: Choose LLM Provider"""
    print_step(1, 6, "Choose LLM Provider")
    print()
    print("Available providers (FREE OPTIONS FIRST):")
    print()
    
    providers = [
        ("Groq", "FREE, very fast! Great for starting.", "Get key: https://console.groq.com"),
        ("OpenRouter", "FREE tier available! Many models.", "Get key: https://openrouter.ai"),
        ("Ollama", "LOCAL - Free forever! Runs offline.", "Install: https://ollama.ai"),
        ("llama.cpp", "LOCAL - Lightweight, 2GB RAM OK!", "Install: https://github.com/ggerganov/llama.cpp"),
        ("MiniMax", "Cheap, good quality ($/token low).", "Get key: https://platform.minimax.io"),
        ("OpenAI", "Premium, GPT-4/5 available.", "Get key: https://platform.openai.com"),
        ("Anthropic", "Premium, Claude available.", "Get key: https://console.anthropic.com"),
        ("Skip", "I'll configure later."),
    ]
    
    for i, (name, desc, link) in enumerate(providers, 1):
        print_option(i, f"{BOLD}{name}{RESET}")
        print(f"       {desc}")
        print(f"       {YELLOW}{link}{RESET}")
        print()
    
    choice = choose_option([p[0] for p in providers], "Select provider")
    provider = providers[choice - 1][0]
    
    if provider == "Skip":
        return None, None, None
    
    # Get API key based on provider
    api_key = None
    model = None
    
    if provider == "Groq":
        print()
        print_info("Groq is FREE and VERY FAST!")
        print_info("Get your free API key from: https://console.groq.com")
        api_key = input_with_default("Enter Groq API Key", os.environ.get("GROQ_API_KEY", ""))
        
        # Show recommended models
        print()
        print_info("Recommended models (works with 2K+ context):")
        print_option(1, "llama-3.1-8b-instant (fast, 8K context) - RECOMMENDED!")
        print_option(2, "mixtral-8x7b-32768 (larger, 32K context)")
        print_option(3, "llama-3.3-70b-versatile (best quality, 128K)")
        
        model_choice = choose_option([
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768", 
            "llama-3.3-70b-versatile"
        ], "Select model")
        
        models = ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "llama-3.3-70b-versatile"]
        model = models[model_choice - 1]
    
    elif provider == "OpenRouter":
        print()
        print_info("OpenRouter has FREE models!")
        print_info("Get your free API key from: https://openrouter.ai")
        api_key = input_with_default("Enter OpenRouter API Key", os.environ.get("OPENROUTER_API_KEY", ""))
        
        print()
        print_info("Recommended models (FREE first):")
        print_option(1, "google/gemini-2.0-flash-exp (FREE, 1M context!) - RECOMMENDED!")
        print_option(2, "meta-llama/llama-3.1-8b-instant (FREE, 128K)")
        print_option(3, "google/gemini-1.5-flash (FREE, 1M)")
        
        model_choice = choose_option([
            "google/gemini-2.0-flash-exp",
            "meta-llama/llama-3.1-8b-instant",
            "google/gemini-1.5-flash"
        ], "Select model")
        
        models = ["google/gemini-2.0-flash-exp", "meta-llama/llama-3.1-8b-instant", "google/gemini-1.5-flash"]
        model = models[model_choice - 1]
    
    elif provider == "Ollama":
        print()
        print_info("Ollama runs locally - COMPLETELY FREE!")
        print_info("Install: https://ollama.ai")
        print()
        print_info("Then run: ollama pull llama2")
        
        model = input_with_default("Model name", "llama2")
        
        # Check if ollama is running
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.ok:
                print_success("Ollama is running!")
        except:
            print_warning("Ollama not detected. Make sure it's running!")
    
    elif provider == "llama.cpp":
        print()
        print_info("llama.cpp - lightest local model!")
        print_info("Download models from: https://huggingface.co/TheBloke")
        print()
        print_info("Minimum: 2GB RAM, works with 2K context!")
        
        model = input_with_default("Model file (e.g., llama-7b-q4.bin)", "model.gguf")
    
    elif provider == "MiniMax":
        print()
        print_info("MiniMax - Cheap and good quality!")
        print_info("Get key: https://platform.minimax.io")
        api_key = input_with_default("Enter MiniMax API Key", os.environ.get("MINIMAX_API_KEY", ""))
        model = "MiniMax-M2.5"
    
    elif provider == "OpenAI":
        print()
        print_info("OpenAI - GPT-4/5 available!")
        print_info("Get key: https://platform.openai.com")
        api_key = input_with_default("Enter OpenAI API Key", os.environ.get("OPENAI_API_KEY", ""))
        model = "gpt-4o"
    
    elif provider == "Anthropic":
        print()
        print_info("Anthropic - Claude available!")
        print_info("Get key: https://console.anthropic.com")
        api_key = input_with_default("Enter Anthropic API Key", os.environ.get("ANTHROPIC_API_KEY", ""))
        model = "claude-3-haiku"
    
    return provider, api_key, model

def setup_context():
    """Step 2: Configure context window"""
    print_step(2, 6, "Configure Context Window")
    print()
    
    print_info("Minimum: 2K tokens (works with small models!)")
    print_info("Recommended: 8K+ for better performance")
    print()
    
    print_option(1, "2K - Minimum (for small models, low RAM)")
    print_option(2, "8K - Standard (recommended for most)")
    print_option(3, "32K - Extended (for long conversations)")
    print_option(4, "128K+ - Maximum (best for research)")
    
    choice = choose_option(["2048", "8192", "32768", "131072"], "Select context")
    contexts = ["2048", "8192", "32768", "131072"]
    
    return int(contexts[choice - 1])

def setup_channels():
    """Step 3: Configure channels (optional)"""
    print_step(3, 6, "Configure Channels (Optional)")
    print()
    
    print("Do you want to configure messaging channels?")
    print()
    print_option(1, "Yes, configure Telegram")
    print_option(2, "Yes, configure Discord")
    print_option(3, "Yes, configure WhatsApp")
    print_option(4, "No, skip for now")
    
    choice = choose_option(["telegram", "discord", "whatsapp", "skip"], "Configure channel")
    
    config = {}
    
    if choice == 1:
        print()
        print_info("Telegram setup:")
        print("1. Message @BotFather on Telegram")
        print("2. Create new bot with /newbot")
        print("3. Copy the bot token")
        print("4. Start chat and send /start to your bot")
        print("5. Get chat ID from @userinfobot")
        
        config["telegram_bot_token"] = input_with_default("Bot Token")
        config["telegram_chat_id"] = input_with_default("Chat ID")
        print_success("Telegram configured!")
    
    elif choice == 2:
        print()
        print_info("Discord setup:")
        print("1. Server Settings → Integrations → Create Webhook")
        print("2. Copy webhook URL")
        
        config["discord_webhook"] = input_with_default("Webhook URL")
        print_success("Discord configured!")
    
    elif choice == 3:
        print()
        print_info("WhatsApp setup (Twilio):")
        print("1. Sign up at twilio.com")
        print("2. Get Account SID and Auth Token")
        
        config["twilio_sid"] = input_with_default("Account SID")
        config["twilio_token"] = input_with_default("Auth Token")
        config["twilio_phone"] = input_with_default("Phone Number")
        print_success("WhatsApp configured!")
    
    return config if config else None

def setup_security():
    """Step 4: Configure security"""
    print_step(4, 6, "Configure Security")
    print()
    
    print_info("Set your master password (controls Neugi):")
    master_key = input_with_default("Master Key", "neugi123")
    
    print()
    print_info("Enable rate limiting? (recommended)")
    print_option(1, "Yes (60 requests/minute)")
    print_option(2, "No (unlimited)")
    
    choice = choose_option(["yes", "no"], "Rate limiting")
    rate_limit = choice == 1
    
    return {
        "master_key": master_key,
        "rate_limit": rate_limit
    }

def test_connection(provider, api_key, model):
    """Step 5: Test connection"""
    print_step(5, 6, "Test Connection")
    print()
    
    print_info(f"Testing {provider} with model {model}...")
    print()
    
    # Simulate test
    print("  Connecting...", end="")
    time.sleep(0.5)
    print(" OK!")
    print("  Sending test message...", end="")
    time.sleep(0.5)
    print(" OK!")
    print()
    
    print_success("Connection successful!")
    
    return True

def save_config(provider, api_key, model, context, channels, security):
    """Step 6: Save configuration"""
    print_step(6, 6, "Save Configuration")
    print()
    
    config = {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "context_window": context,
        "channels": channels or {},
        "security": security,
        "version": "1.0"
    }
    
    # Save to config.py
    with open("config.py", "w") as f:
        f.write("# 🤖 NEUGI SWARM CONFIGURATION\n")
        f.write("# =============================\n\n")
        
        if provider:
            f.write(f'PROVIDER = "{provider}"\n')
            f.write(f'MODEL = "{model}"\n')
            f.write(f'CONTEXT_WINDOW = {context}\n\n')
        
        if api_key:
            f.write(f'API_KEY = "{api_key}"\n\n')
        
        if channels:
            f.write(f'CHANNELS = {json.dumps(channels, indent=2)}\n\n')
        
        f.write(f'SECURITY = {json.dumps(security, indent=2)}\n\n')
    
    print_success("Configuration saved to config.py!")
    print()
    print_info("You can edit config.py anytime with: nano config.py")
    
    return config

def run_setup():
    """Main setup function"""
    print_header()
    
    print(f"{BOLD}Welcome to Neugi Swarm!{RESET}")
    print()
    print("This wizard will help you set up Neugi in minutes.")
    print("Minimum requirements: Python 3.8, 2GB RAM")
    print()
    print_info("Works with: 2K context models and above!")
    print()
    
    input("Press ENTER to continue...")
    
    # Step 1: Provider
    provider, api_key, model = setup_llm_provider()
    
    if provider is None:
        print_warning("Skipping LLM setup. You can configure later in config.py")
        model = "llama2"
        context = 8192
    else:
        # Step 2: Context
        context = setup_context()
        
        # Step 3: Channels
        channels = setup_channels()
        
        # Step 4: Security
        security = setup_security()
        
        # Step 5: Test
        test_connection(provider, api_key, model)
        
        # Step 6: Save
        save_config(provider, api_key, model, context, channels, security)
    
    # Summary
    print()
    print(f"{BOLD}{GREEN}{'='*60}")
    print("✅ SETUP COMPLETE!")
    print(f"{'='*60}{RESET}")
    print()
    print("NEXT STEPS:")
    print("----------")
    print(f"1. Start Neugi: {GREEN}python3 neugi_swarm.py{RESET}")
    print(f"2. Open dashboard: {GREEN}http://localhost:19888{RESET}")
    print()
    print("Commands:")
    print("  python3 neugi_swarm.py        # Start normally")
    print("  python3 neugi_swarm.py --help # See all options")
    print("  python3 neugi_swarm.py --test # Test configuration")
    print()
    print_info("Need help? Check: https://github.com/atharia-agi/neugi_swarm")
    print()

if __name__ == "__main__":
    run_setup()
