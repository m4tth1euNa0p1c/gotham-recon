
import unittest
import json
from unittest.mock import MagicMock, patch
from recon_gotham.core.asset_graph import AssetGraph
from recon_gotham.core.planner import find_top_paths, score_osint_chain

class TestMissionOSINT(unittest.TestCase):
    """
    Simulates a full OSINT investigation loop scenario without running live tools.
    Verifies that OSINT data leads to correct Planner/Strategic decisions.
    """
    
    def setUp(self):
        self.graph = AssetGraph()
        
    def test_phishing_chain_scenario(self):
        # 1. Simulate OSINT Phase Results
        # Org Profiler found "Wayne Enterprises"
        org_id = self.graph.add_org("Wayne Enterprises", "Gotham", "Defense")
        
        # SaaS Intel found "MessageBusiness" (Email Provider)
        saas_id = self.graph.add_saas_app("MessageBusiness", "Email Marketing", "msg.biz")
        self.graph.link_org_saas(org_id, saas_id)
        
        # 2. Simulate Recon Phase
        # Subdomain enumeration found "mail.wayne.com" pointing to "msg.biz"
        self.graph.add_subdomain_with_http({
            "subdomain": "mail.wayne.com",
            "priority": 8,
            "tag": "MAIL",
            "http": {"url": "https://mail.wayne.com"}
        })
        
        # Link SaaS to Subdomain (This logic usually happens if we analyze CNAMEs or explicit links)
        # For this test, we assume the graph builder or manual logic linked them
        # Let's manually link for the test scenario
        ep_id = "endpoint:http:https://mail.wayne.com/"
        self.graph.add_endpoint("/", "GET", "CRAWL", "https://mail.wayne.com")
        self.graph.link_saas_endpoint(saas_id, ep_id)
        
        # 3. Running Planner Logic
        graph_data = {"nodes": self.graph.nodes, "edges": self.graph.edges}
        
        # We expect the planner to find the OSINT chain
        # ORG -> SAAS
        top_paths = find_top_paths(graph_data)
        
        # Filter for our Org path
        org_paths = [p for p in top_paths if p["subdomain"] == org_id]
        self.assertTrue(len(org_paths) > 0, "Planner failed to identify OSINT chain for Organization")
        
        path = org_paths[0]
        print(f"DEBUG: Path Actions: {path['next_actions']}")
        
        # Assertions
        # 1. Score should be boosted by SaaS presence
        self.assertTrue(path["score"] >= 2)
        # 2. Action 'phishing_scenario_design' should be recommended due to 'Email' category
        self.assertIn("phishing_scenario_design", path["next_actions"])
        
    def test_leak_impact_scenario(self):
        # 1. Org and Leak
        org_id = self.graph.add_org("Target Corp")
        leak_id = self.graph.add_leak("AWS Key", "Github", "AKIA...", 0.9)
        self.graph.link_leak_org(leak_id, org_id)
        
        # 2. Run Planner
        graph_data = {"nodes": self.graph.nodes, "edges": self.graph.edges}
        top_paths = find_top_paths(graph_data)
        
        org_path = [p for p in top_paths if p["subdomain"] == org_id][0]
        
        # Assertions
        self.assertTrue(org_path["score"] >= 5)
        self.assertIn("credential_stuffing_simulation", org_path["next_actions"])

if __name__ == '__main__':
    unittest.main()
