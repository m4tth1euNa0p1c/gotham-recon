
import unittest
from recon_gotham.core.planner import find_top_paths

class TestPlannerOSINT(unittest.TestCase):
    
    def test_osint_chain_scoring(self):
        # Mock Graph Data
        graph_data = {
            "nodes": [
                {"id": "org:wayne", "type": "ORG", "properties": {"name": "Wayne Ent"}},
                {"id": "saas:salesforce", "type": "SAAS_APP", "properties": {"name": "Salesforce", "category": "CRM"}},
                {"id": "leak:123", "type": "LEAK", "properties": {"type": "API Key", "description": "Found on Pastebin"}}
            ],
            "edges": [
                {"from": "org:wayne", "to": "saas:salesforce", "relation": "ORG_USES_SAAS"},
                {"from": "leak:123", "to": "org:wayne", "relation": "LEAK_RELATES_TO_ORG"},
            ]
        }
        
        paths = find_top_paths(graph_data)
        
        # Expect 1 path for the org
        self.assertTrue(len(paths) >= 1)
        
        org_path = next((p for p in paths if p["subdomain"] == "org:wayne"), None)
        self.assertIsNotNone(org_path)
        
        # Check specific actions
        # SaaS (CRM) -> +3 Score, +phishing
        # Leak -> +5 Score, +credential_stuffing
        # Base SaaS -> +2 Score
        # Total expected: 2 + 3 + 5 = 10
        self.assertTrue(org_path["score"] >= 10)
        
        actions = org_path["next_actions"]
        self.assertIn("phishing_scenario_design", actions)
        self.assertIn("credential_stuffing_simulation", actions)

if __name__ == '__main__':
    unittest.main()
