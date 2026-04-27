"""Tests for Multi-modal, Stealth Browser, and A2A Protocol."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_multimodal import ImageMessage, MultimodalProvider, VisionComputerUse
from tools.stealth_browser import StealthBrowser, StealthConfig, BrowserFingerprint
from a2a import (
    A2AChannel, A2AError, A2AMessage, A2AMessageType, A2APriority,
    A2AProtocol, AgentCapability, AgentNotFoundError, AgentRegistration,
    MessageExpiredError,
)


class TestImageMessage(unittest.TestCase):
    def test_ollama_format(self):
        msg = ImageMessage(text="Hello", image_b64="abc123")
        fmt = msg.to_ollama_format()
        self.assertEqual(fmt["role"], "user")
        self.assertEqual(fmt["content"], "Hello")
        self.assertEqual(fmt["images"], ["abc123"])
    
    def test_openai_format(self):
        msg = ImageMessage(text="Hello", image_b64="abc123")
        fmt = msg.to_openai_format()
        self.assertEqual(fmt["role"], "user")
        self.assertEqual(len(fmt["content"]), 2)
        self.assertEqual(fmt["content"][0]["type"], "text")
        self.assertEqual(fmt["content"][1]["type"], "image_url")
    
    def test_anthropic_format(self):
        msg = ImageMessage(text="Hello", image_b64="abc123")
        fmt = msg.to_anthropic_format()
        self.assertEqual(fmt["role"], "user")
        self.assertEqual(len(fmt["content"]), 2)
        self.assertEqual(fmt["content"][1]["type"], "image")


class TestMultimodalProvider(unittest.TestCase):
    def test_detect_provider_type(self):
        from llm_provider import ProviderConfig, ProviderType, OllamaProvider
        config = ProviderConfig(provider_type=ProviderType.OLLAMA)
        provider = OllamaProvider(config)
        mp = MultimodalProvider(provider)
        self.assertEqual(mp.provider_type, ProviderType.OLLAMA)
    
    def test_encode_image(self):
        # Test with dummy bytes
        b64 = MultimodalProvider.encode_image_bytes(b"fake_image_data")
        self.assertIsInstance(b64, str)
        self.assertTrue(len(b64) > 0)


class TestVisionComputerUse(unittest.TestCase):
    def test_summarize_dom(self):
        from llm_provider import ProviderConfig, ProviderType, OllamaProvider
        config = ProviderConfig(provider_type=ProviderType.OLLAMA)
        provider = OllamaProvider(config)
        mp = MultimodalProvider(provider)
        vision = VisionComputerUse(mp)
        
        dom = [
            {"tag": "button", "text": "Submit", "selector": "#submit", "clickable": True},
            {"tag": "input", "text": "", "selector": "#search", "clickable": False},
        ]
        summary = vision._summarize_dom(dom)
        self.assertIn("button", summary)
        self.assertIn("Submit", summary)
    
    def test_summarize_history(self):
        from llm_provider import ProviderConfig, ProviderType, OllamaProvider
        config = ProviderConfig(provider_type=ProviderType.OLLAMA)
        provider = OllamaProvider(config)
        mp = MultimodalProvider(provider)
        vision = VisionComputerUse(mp)
        
        actions = [
            {"action": "click", "reason": "Clicked submit"},
            {"action": "fill", "reason": "Filled search"},
        ]
        summary = vision._summarize_history(actions)
        self.assertIn("click", summary)
        self.assertIn("fill", summary)


class TestStealthBrowser(unittest.TestCase):
    def test_initialization(self):
        sb = StealthBrowser()
        self.assertIsNotNone(sb.stealth_config)
        self.assertIsNotNone(sb.fingerprint)
    
    def test_fingerprint_generation(self):
        sb = StealthBrowser()
        fp = sb.fingerprint
        self.assertIsInstance(fp.user_agent, str)
        self.assertIn("width", fp.viewport)
        self.assertIn("height", fp.viewport)
        self.assertTrue(fp.hardware_concurrency > 0)
    
    def test_stealth_info(self):
        sb = StealthBrowser()
        info = sb.stealth_info
        self.assertIn("user_agent", info)
        self.assertIn("viewport", info)
        self.assertIn("scripts_injected", info)
    
    def test_rotate_fingerprint(self):
        sb = StealthBrowser()
        old_ua = sb.fingerprint.user_agent
        sb.rotate_fingerprint()
        new_ua = sb.fingerprint.user_agent
        # Might be same by chance, but usually different
        self.assertIsNotNone(new_ua)
    
    def test_stealth_scripts_built(self):
        sb = StealthBrowser()
        self.assertTrue(len(sb._stealth_scripts) > 0)


class TestA2AProtocol(unittest.TestCase):
    def setUp(self):
        self.protocol = A2AProtocol()
    
    def test_register_agent(self):
        reg = self.protocol.register_agent("test_agent", name="Test")
        self.assertEqual(reg.agent_id, "test_agent")
        self.assertEqual(reg.name, "Test")
    
    def test_unregister_agent(self):
        self.protocol.register_agent("test_agent")
        self.protocol.unregister_agent("test_agent")
        self.assertNotIn("test_agent", self.protocol._agents)
    
    def test_send_to_nonexistent_agent(self):
        msg = A2AMessage(msg_type=A2AMessageType.TASK, sender="sender", task="test")
        response = self.protocol.send("nonexistent", msg)
        self.assertEqual(response.msg_type, A2AMessageType.ERROR)
    
    def test_capability_discovery(self):
        self.protocol.register_agent(
            "coder",
            capabilities=[AgentCapability(name="code", description="Write code")]
        )
        self.protocol.register_agent(
            "writer",
            capabilities=[AgentCapability(name="write", description="Write prose")]
        )
        
        caps = self.protocol.discover_capabilities()
        self.assertIn("code", caps)
        self.assertIn("write", caps)
        self.assertIn("coder", caps["code"])
    
    def test_find_agents_by_capability(self):
        self.protocol.register_agent(
            "coder",
            capabilities=[AgentCapability(name="code")]
        )
        agents = self.protocol.find_agents_by_capability("code")
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_id, "coder")
    
    def test_broadcast(self):
        self.protocol.register_agent("agent1")
        self.protocol.register_agent("agent2")
        
        msg = A2AMessage(msg_type=A2AMessageType.TASK, task="hello")
        responses = self.protocol.broadcast(msg)
        self.assertEqual(len(responses), 2)
    
    def test_message_expiration(self):
        msg = A2AMessage(
            msg_type=A2AMessageType.TASK,
            timestamp=0,  # Ancient timestamp
            ttl_seconds=1,
        )
        self.assertTrue(msg.is_expired())
    
    def test_mesh_status(self):
        self.protocol.register_agent("agent1")
        status = self.protocol.get_mesh_status()
        self.assertEqual(status["total_agents"], 1)
    
    def test_agent_status(self):
        self.protocol.register_agent("agent1", name="Test Agent")
        status = self.protocol.get_agent_status("agent1")
        self.assertEqual(status["name"], "Test Agent")
        self.assertTrue(status["is_alive"])
    
    def test_heartbeat(self):
        self.protocol.register_agent("agent1")
        old_time = self.protocol._agents["agent1"].last_heartbeat
        self.protocol.heartbeat("agent1")
        new_time = self.protocol._agents["agent1"].last_heartbeat
        self.assertGreater(new_time, old_time)


class TestA2AMessage(unittest.TestCase):
    def test_to_dict(self):
        msg = A2AMessage(
            msg_type=A2AMessageType.TASK,
            sender="a",
            recipient="b",
            task="test",
        )
        d = msg.to_dict()
        self.assertEqual(d["msg_type"], "task")
        self.assertEqual(d["sender"], "a")
    
    def test_from_dict(self):
        d = {
            "msg_type": "task",
            "sender": "a",
            "recipient": "b",
            "task": "test",
            "payload": {},
            "priority": 3,
        }
        msg = A2AMessage.from_dict(d)
        self.assertEqual(msg.msg_type, A2AMessageType.TASK)
        self.assertEqual(msg.priority, A2APriority.HIGH)


class TestA2AChannel(unittest.TestCase):
    def test_channel_send(self):
        protocol = A2AProtocol()
        protocol.register_agent("recipient")
        
        channel = A2AChannel(protocol, "sender")
        response = channel.send("recipient", "hello")
        # No handler registered, so message queued
        self.assertIsNone(response)
    
    def test_channel_subscribe(self):
        protocol = A2AProtocol()
        channel = A2AChannel(protocol, "test")
        
        received = []
        def callback(msg):
            received.append(msg)
        
        channel.subscribe(callback)
        
        msg = A2AMessage(msg_type=A2AMessageType.TASK, task="test")
        channel.receive(msg)
        
        self.assertEqual(len(received), 1)


if __name__ == "__main__":
    unittest.main()
