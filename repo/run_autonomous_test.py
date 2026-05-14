#!/usr/bin/env python
"""Run a quick test of the autonomous loop."""
import sys
import time
from pathlib import Path

# Add the repo root to the sys.path so we can import neugi_swarm_v2
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

from neugi_swarm_v2 import NeugiSwarmV2

def main():
    print("Starting NEUGI Swarm v2 with autonomous mode...")
    swarm = NeugiSwarmV2(autonomous=True)
    print(f"Autonomous running: {swarm.is_autonomous_running}")
    # Let it run for 10 seconds
    time.sleep(10)
    print("Stopping autonomous loop...")
    swarm.stop_autonomous()
    print(f"Autonomous running after stop: {swarm.is_autonomous_running}")
    print("Test completed.")

if __name__ == "__main__":
    main()