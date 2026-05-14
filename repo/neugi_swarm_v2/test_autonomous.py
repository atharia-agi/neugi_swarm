#!/usr/bin/env python
"""Test the autonomous loop of NEUGI Swarm v2."""
import time
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