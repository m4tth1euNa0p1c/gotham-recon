
import unittest
from recon_gotham.core.planner import find_top_paths

class TestPlannerEndpoints(unittest.TestCase):
    def test_planner_endpoint_scoring(self):
        graph_data = {
            "nodes": [
                {"id": "sub.target.com", "type": "SUBDOMAIN", "properties": {"priority": 5, "tag": "API"}},
                {"id": "http://sub.target.com", "type": "HTTP_SERVICE", "properties": {"url": "https://sub.target.com"}},
                {"id": "ep1", "type": "ENDPOINT", "properties": {"path": "/api/v1/users", "method": "GET", "source": "HTML_FORM"}},
                {"id": "ep2", "type": "ENDPOINT", "properties": {"path": "/admin/config", "method": "POST", "source": "WAYBACK"}}
            ],
            "edges": [
                {"from": "sub.target.com", "to": "http://sub.target.com", "relation": "EXPOSES_HTTP"},
                {"from": "http://sub.target.com", "to": "ep1", "relation": "EXPOSES_ENDPOINT"},
                {"from": "http://sub.target.com", "to": "ep2", "relation": "EXPOSES_ENDPOINT"}
            ]
        }
        
        paths = find_top_paths(graph_data)
        
        self.assertEqual(len(paths), 1)
        path = paths[0]
        
        # Check Base Score
        # Priority (5) + API Tag? (No explicit tag bonus for API in sub, but endpoint bonus)
        
        # Check Endpoint Bonuses
        # /api/v1/users -> +1 (API Endpoint)
        # /admin/config -> +3 (Admin Endpoint)
        # WAYBACK Source -> +2 (Historical)
        # POST Method -> +1 (State Changing)
        # Count Bonus -> +2 (Count=2)
        # Total expected >= 5 + 1 + 3 + 2 + 1 + 2 = 14
        
        self.assertTrue(path["score"] >= 14, f"Score {path['score']} too low")
        
        # Check Actions
        actions = path["next_actions"]
        self.assertIn("ffuf_api_fuzz", actions)
        self.assertIn("nuclei_auth_scan", actions) # from /admin

if __name__ == "__main__":
    unittest.main()
