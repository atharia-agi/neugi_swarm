#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - VOICE
=======================

Voice capabilities: TTS and STT

TTS Providers:
- pyttsx3 (offline)
- gtts (Google)
- elevenlabs (premium)

STT Providers:
- whisper
- google_stt
- sphinx

Usage:
    from neugi_swarm_voice import VoiceManager
    voice = VoiceManager()
    voice.speak("Hello!")
    text = voice.listen()
"""

import os
import json
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class TTSProvider(Enum):
    PYTTSX3 = "pyttsx3"
    GTTS = "gtts"
    ELEVENLABS = "elevenlabs"
    WEB = "web"

class STTProvider(Enum):
    WHISPER = "whisper"
    GOOGLE = "google_stt"
    SPHINX = "sphinx"

@dataclass
class VoiceConfig:
    """Voice configuration"""
    tts_provider: str = "auto"
    stt_provider: str = "auto"
    default_voice: str = "default"
    language: str = "en"
    speed: float = 1.0
    volume: float = 1.0

class VoiceManager:
    """Manages TTS and STT"""
    
    def __init__(self, config: VoiceConfig = None):
        self.config = config or VoiceConfig()
        
        self.tts_available = []
        self.stt_available = []
        
        self._detect_providers()
    
    def _detect_providers(self):
        """Detect available TTS/STT providers"""
        
        # TTS
        try:
            import pyttsx3
            self.tts_available.append("pyttsx3")
        except ImportError:
            pass
        
        try:
            import gtts
            self.tts_available.append("gtts")
        except ImportError:
            pass
        
        try:
            import elevenlabs
            self.tts_available.append("elevenlabs")
        except ImportError:
            pass
        
        # STT
        try:
            import whisper
            self.stt_available.append("whisper")
        except ImportError:
            pass
        
        # Always available
        self.tts_available.append("web")
        self.stt_available.append("simulated")
    
    def speak(self, text: str, provider: str = None, voice: str = None) -> Dict:
        """Text to Speech"""
        
        if provider is None:
            provider = self.config.tts_provider
        
        if provider == "auto":
            provider = self.tts_available[0] if self.tts_available else "none"
        
        if provider == "pyttsx3":
            return self._speak_pyttsx3(text, voice)
        elif provider == "gtts":
            return self._speak_gtts(text, voice)
        elif provider == "elevenlabs":
            return self._speak_elevenlabs(text, voice)
        elif provider == "web":
            return self._speak_web(text)
        else:
            return {"status": "error", "message": f"Provider {provider} not available"}
    
    def _speak_pyttsx3(self, text: str, voice: str = None) -> Dict:
        """Use pyttsx3"""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            if voice:
                voices = engine.getProperty('voices')
                for v in voices:
                    if voice.lower() in v.name.lower():
                        engine.setProperty('voice', v.id)
                        break
            
            engine.say(text)
            engine.runAndWait()
            
            return {"status": "success", "provider": "pyttsx3", "text": text[:50]}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _speak_gtts(self, text: str, voice: str = None) -> Dict:
        """Use Google TTS"""
        try:
            from gtts import gTTS
            
            lang = self.config.language
            tts = gTTS(text=text, lang=lang)
            
            output_file = "/tmp/neugi_tts.mp3"
            tts.save(output_file)
            
            # Play
            os.system(f"mpg123 -q {output_file} 2>/dev/null || afplay {output_file} 2>/dev/null")
            
            return {"status": "success", "provider": "gtts", "file": output_file}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _speak_elevenlabs(self, text: str, voice: str = None) -> Dict:
        """Use ElevenLabs"""
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        
        if not api_key:
            return {"status": "error", "message": "No API key"}
        
        try:
            import requests
            
            voice_id = voice or "21m00Tcm4TlvDq8ikWAM"  # Default voice
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            
            r = requests.post(url, json=data, headers=headers)
            
            if r.ok:
                output_file = "/tmp/neugi_tts.mp3"
                with open(output_file, 'wb') as f:
                    f.write(r.content)
                return {"status": "success", "provider": "elevenlabs", "file": output_file}
            
            return {"status": "error", "message": "API error"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _speak_web(self, text: str) -> Dict:
        """Web TTS (simulation)"""
        return {
            "status": "simulated",
            "provider": "web",
            "text": text[:100],
            "message": "Would use browser TTS"
        }
    
    def listen(self, audio_file: str = None, provider: str = None) -> str:
        """Speech to Text"""
        
        if provider is None:
            provider = self.config.stt_provider
        
        if provider == "auto":
            provider = self.stt_available[0] if self.stt_available else "simulated"
        
        if provider == "whisper":
            return self._listen_whisper(audio_file)
        elif provider == "google":
            return self._listen_google(audio_file)
        else:
            return "[Simulated STT] Would transcribe audio"
    
    def _listen_whisper(self, audio_file: str = None) -> str:
        """Use Whisper for STT"""
        try:
            import whisper
            
            model = whisper.load_model("base")
            
            if audio_file:
                result = model.transcribe(audio_file)
            else:
                # Would record first
                return "[Would record and transcribe]"
            
            return result.get("text", "")
        except Exception as e:
            return f"[Whisper error: {e}]"
    
    def _listen_google(self, audio_file: str = None) -> str:
        """Use Google STT"""
        return "[Google STT would transcribe]"
    
    def list_voices(self, provider: str = "pyttsx3") -> List[Dict]:
        """List available voices"""
        voices = []
        
        if provider == "pyttsx3":
            try:
                import pyttsx3
                engine = pyttsx3.init()
                for v in engine.getProperty('voices'):
                    voices.append({
                        "id": v.id,
                        "name": v.name,
                        "languages": v.languages
                    })
            except:
                pass
        
        return voices
    
    def status(self) -> Dict:
        """Get voice status"""
        return {
            "tts_available": self.tts_available,
            "stt_available": self.stt_available,
            "tts_provider": self.config.tts_provider,
            "stt_provider": self.config.stt_provider,
            "language": self.config.language
        }

# Main
if __name__ == "__main__":
    voice = VoiceManager()
    
    print("🤖 Neugi Swarm Voice")
    print("="*40)
    print(json.dumps(voice.status(), indent=2))
    
    print("\n🧪 Testing TTS...")
    result = voice.speak("Hello! I am Neugi.")
    print(f"Result: {result}")
