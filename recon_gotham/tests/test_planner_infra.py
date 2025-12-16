
import unittest
from recon_gotham.core.planner import find_top_paths, score_path

class TestPlannerInfra(unittest.TestCase):
    def test_infra_only_target(self):
        """Test that a target with no HTTP but rich Infra data is scored correctly."""
        
        # Mock Graph Data
        # Subdomain: suivi.mailings.target.com
        # No HTTP Service
        # Has IP (OVH) -> ASN (OVH)
        # Has DNS Records (MX, SPF)
        
        nodes = [
            {"id": "suivi.mailings.target.com", "type": "SUBDOMAIN", "properties": {"priority": 0, "tag": "UNKNOWN"}},
            {"id": "ip:54.1.2.3", "type": "IP_ADDRESS", "properties": {"ip": "54.1.2.3"}},
            {"id": "asn:AS16276", "type": "ASN", "properties": {"org": "OVH SAS"}},
            {"id": "dns:MX:10.mail.com", "type": "DNS_RECORD", "properties": {"type": "MX", "value": "10 mail.com"}},
            {"id": "dns:TXT:spf", "type": "DNS_RECORD", "properties": {"type": "TXT", "value": "v=spf1 include:mail.com ~all"}}
        ]
        
        edges = [
            {"from": "suivi.mailings.target.com", "to": "ip:54.1.2.3", "relation": "RESOLVES_TO"},
            {"from": "ip:54.1.2.3", "to": "asn:AS16276", "relation": "BELONGS_TO"},
            {"from": "suivi.mailings.target.com", "to": "dns:MX:10.mail.com", "relation": "HAS_RECORD"},
            {"from": "suivi.mailings.target.com", "to": "dns:TXT:spf", "relation": "HAS_RECORD"}
        ]
        
        graph_data = {"nodes": nodes, "edges": edges}
        
        # Run Planner
        top_paths = find_top_paths(graph_data, k=5)
        
        # Assertions
        self.assertEqual(len(top_paths), 1, "Should find 1 path despite no HTTP")
        path = top_paths[0]
        self.assertEqual(path["subdomain"], "suivi.mailings.target.com")
        
        # Score Calculation:
        # Name "mail" -> +4 (Mailing System)
        # ASN "OVH" -> +3
        # DNS MX+SPF -> +2
        # TOTAL = 9
        self.assertEqual(path["score"], 9)
        
        # Check Actions
        print(f"Actions: {path['next_actions']}")
        self.assertIn("smtp_test", path["next_actions"])
        self.assertIn("dns_audit", path["next_actions"])
        
        # Check Reason
        print(f"Reason: {path['reason']}")
        self.assertIn("Mailing System (+4)", path["reason"])
        self.assertIn("OVH Backend (+3)", path["reason"])
        self.assertIn("Structured Emailing (+2)", path["reason"])

if __name__ == '__main__':
    unittest.main()
