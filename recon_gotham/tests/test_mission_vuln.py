
import unittest
import subprocess
import os
import sys
import os
# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "../../src"))
sys.path.append(src_dir)

import json
import time
from recon_gotham.core.asset_graph import AssetGraph

class TestMissionVuln(unittest.TestCase):
    """
    Scenario 3: Vulnerable Lab
    Target: Simulated (since we might not have a live vuln lab accessible).
    Goal: Verify VULNERABILITY node creation and Exploit actions.
    
    Since we cannot easily spin up a docker lab from inside this python script 
    without complex setup, we will perform a 'Mocked Injection' run OR 
    rely on the 'verify_vuln_injection.py' logic but wrapped in a test.
    
    User approach: "Lance sur ton domaine de lab."
    Adaptation: We will trigger a run where we FORCE injection of a vulnerability 
    (e.g. using a flag or a special mock tool) effectively simulating a positive find.
    """
    
    TARGET = "vuln-lab.local"
    
    def test_logic_vuln_flow(self):
        # Instead of full subprocess, we verify the Logic Flow specifically:
        # AssetGraph -> Add Vuln -> Planner -> Suggest Exploit.
        # This is a functional integration test of the components.
        
        print(f"\n[Testing] Vuln Flow Simulation on {self.TARGET}...")
        
        # 1. Setup Graph
        graph = AssetGraph()
        sub_id = graph.add_subdomain(self.TARGET, "mock_source")
        ep_id = graph.add_endpoint(sub_id, "/api/login", "POST")
        
        # 2. Add Vulnerability
        vuln_id = graph.add_vulnerability(
            severity="critical",
            tool="Nuclei",
            name="SQL Injection",
            description="SQLi in login param",
            affected_node_id=ep_id
        )
        
        # 3. Serialize & Reload (Verify Persistence)
        data = graph.to_json()
        loaded_graph = AssetGraph()
        loaded_graph.load_from_dict(json.loads(data))
        
        # 4. Run Planner
        from recon_gotham.core.planner import find_top_paths
        
        graph_data = {"nodes": loaded_graph.nodes, "edges": loaded_graph.edges}
        top_paths = find_top_paths(graph_data)
        
        # 5. Asset Exploit Suggestion
        best_path = top_paths[0]
        self.assertGreater(best_path["score"], 10, "Critical vuln should yield high score")
        self.assertIn("exploit_lab", best_path["actions"], "Should suggest exploit_lab")
        self.assertIn("manual_validation", best_path["actions"])

if __name__ == '__main__':
    unittest.main()
