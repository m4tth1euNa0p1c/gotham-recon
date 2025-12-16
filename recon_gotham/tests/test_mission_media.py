
import unittest
import subprocess
import os
import json
import time

class TestMissionMedia(unittest.TestCase):
    """
    Scenario 2: Media Site
    Target: tahiti-infos.com
    Goal: Verify Endpoint discovery, Infra mapping, and Plan generation.
    """
    
    TARGET = "tahiti-infos.com"
    
    def test_run_media_site(self):
        print(f"\n[Testing] Media Mission on {self.TARGET}...")
        
        # User requested: --mode aggressive
        cmd = [
            "python", "run_mission.py", 
            self.TARGET, 
            "--mode", "aggressive" 
        ]
        
        # Execute (Longer timeout for scanning)
        start = time.time()
        # Ensure we don't hang forever, but scanning takes time.
        # For a "Verification" test, we might normally mock, but here we run real.
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        duration = time.time() - start
        
        print(f"Mission finished in {duration:.2f}s")
        
        if result.returncode != 0:
            print("STDERR:", result.stderr)
            
        self.assertEqual(result.returncode, 0, "Mission crashed")
        
        # Assertions
        graph_file = f"output/{self.TARGET}_asset_graph.json"
        self.assertTrue(os.path.exists(graph_file))
        
        with open(graph_file, 'r') as f:
            data = json.load(f)
        nodes = data.get("nodes", [])
        
        # 1. Check Endpoints
        endpoints = [n for n in nodes if n["type"] == "ENDPOINT"]
        self.assertTrue(len(endpoints) > 0, "No endpoints found")
        
        # 2. Check for specific known endpoints (e.g., /admin from crawling or previous knowledge)
        # Note: This depends on the site's current state.
        
        # 3. Check Infra (Cloudflare/OVH)
        asns = [n for n in nodes if n["type"] == "ASN"]
        self.assertTrue(len(asns) > 0, "No ASN info found")
        
        # 4. Check Plan
        plan_file = f"output/{self.TARGET}_attack_plan.json"
        self.assertTrue(os.path.exists(plan_file))

if __name__ == '__main__':
    unittest.main()
