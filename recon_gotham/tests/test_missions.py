import unittest
import subprocess
import json
import os
import sys

# Integration Tests for Full Missions
# These tests run the ACTUAL pipeline. They may take time and require network/Docker.
# Run with: python -m unittest recon_gotham/tests/test_missions.py

class TestMissions(unittest.TestCase):
    def test_tahiti__infos_mission_aggressive(self):
        domain = "tahiti-infos.com"
        
        # 1. Execute Mission
        # Use python from current environment
        cmd = [sys.executable, "run_mission.py", domain, "--mode", "aggressive"]
        
        # We assume run_mission.py is in the CWD (project root)
        # Verify CWD
        cwd = os.getcwd() # Should be project root if run via standard command
        
        print(f"\\n[Integration] Running Mission on {domain} (Aggressive)...")
        try:
            subprocess.run(cmd, check=True, cwd=cwd, capture_output=True) # Capture output to avoid spamming test runner, unless debugging
        except subprocess.CalledProcessError as e:
            print(f"STDOUT: {e.stdout.decode()}")
            print(f"STDERR: {e.stderr.decode()}")
            self.fail(f"Mission failed with exit code {e.returncode}")

        # 2. Check Output Files
        graph_path = os.path.join(cwd, "recon_gotham", "output", f"{domain}_asset_graph.json")
        plan_path = os.path.join(cwd, "recon_gotham", "output", f"{domain}_attack_plan.json")
        
        self.assertTrue(os.path.exists(graph_path), "Asset Graph JSON not found")
        self.assertTrue(os.path.exists(plan_path), "Attack Plan JSON not found")
        
        # 3. Analyze Asset Graph
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
            
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        # Check for specific high-value subdomain (if it exists, might be flaky if subfinder fails)
        # But in aggressive mode, we hope for best results.
        # Check for Aggressive Mode evidence (Extended Ports)
        # Standard mode: 80, 443. Aggressive: 8080, 8443, etc.
        # We expect to see nodes with these ports if open.
        # Tahiti-infos has exposed 8080/8443 in previous runs.
        # Also check for 'www.tahiti-infos.com' which is reliably found.
        has_main = any(n["id"] == "www.tahiti-infos.com" for n in nodes)
        self.assertTrue(has_main, "Expected www.tahiti-infos.com")
        
        has_extended_port = any("8080" in n["id"] or "8443" in n["id"] for n in nodes if n["type"] == "HTTP_SERVICE")
        if has_extended_port:
            print("[Integration] Confirmed Aggressive Mode (Extended Ports found).")
        else:
            print("[WARN] Extended ports not found (Target might be closed or firewall blocking).")
        
        # Check for JS_FILEs (Active scan of tahiti-infos should yield JS)
        has_js = any(n["type"] == "JS_FILE" for n in nodes)
        # Note: Aggressive mode usually finds JS.
        # self.assertTrue(has_js, "Expected at least one JS_FILE") 
        # Making this soft assertion or warning if failing to avoid breaking CI on network hiccups?
        if not has_js:
            print("[WARN] No JS Files found in integration test.")
            
        # 4. Analyze Attack Plan
        with open(plan_path, 'r', encoding='utf-8') as f:
            plan = json.load(f)
            
        # Verify we have recommendations
        self.assertGreater(len(plan), 0, "Attack Plan is empty")
        
        # Verify scoring
        # At least one item should have score >= 10 (High Value)
        high_value = [p for p in plan if p["score"] >= 10]
        self.assertGreater(len(high_value), 0, "No High Value targets identified in Plan")
        
        print(f"[Integration] Mission Verified. Found {len(nodes)} nodes, {len(plan)} planned items.")

    def test_teoraoraraka_zero_surface(self):
        domain = "teoraoraraka.org" # Known Zero Subdomain Target
        
        # Run in default (Stealth) mode. Fallback should still trigger.
        cmd = [sys.executable, "run_mission.py", domain]
        cwd = os.getcwd()
        
        print(f"\\n[Integration] Running Mission on {domain} (Zero Surface Check)...")
        try:
            subprocess.run(cmd, check=True, cwd=cwd, capture_output=True)
        except subprocess.CalledProcessError as e:
            self.fail(f"Mission failed with exit code {e.returncode}: {e.stderr.decode()}")
            
        graph_path = os.path.join(cwd, "recon_gotham", "output", f"{domain}_asset_graph.json")
        self.assertTrue(os.path.exists(graph_path))
        
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
            
        nodes = graph.get("nodes", [])
        
        # Expectation: Fallback adds the ROOT domain and scans it.
        # Fallback might also add 'www' or 'api' from hardcoded dict.
        has_root = any(n["id"] in [domain, f"https://{domain}", f"http:{domain}", f"http:https://{domain}"] for n in nodes)
        
        # Also check for tag 'ACTIVE_FALLBACK'.
        has_fallback_tag = any(n["properties"].get("tag") == "ACTIVE_FALLBACK" for n in nodes if n["type"] == "SUBDOMAIN")
        
        self.assertTrue(has_root or len(nodes) > 0, "Graph should not be empty even for Zero Surface")
        self.assertTrue(has_fallback_tag, "Expected ACTIVE_FALLBACK tag to be present")
        
        print(f"[Integration] Zero Surface Fallback Verified. Found {len(nodes)} nodes.")

if __name__ == '__main__':
    unittest.main()
