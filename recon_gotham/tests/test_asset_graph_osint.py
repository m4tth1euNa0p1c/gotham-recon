
import unittest
from recon_gotham.core.asset_graph import AssetGraph

class TestAssetGraphOSINT(unittest.TestCase):
    
    def test_osint_extensions(self):
        graph = AssetGraph()
        
        # 1. Org & Brand
        org_id = graph.add_org("Wayne Enterprises", "Gotham", "Defense", "Mega")
        brand_id = graph.add_brand("WayneTech", "tech.wayne.com")
        self.assertIn(org_id, [n["id"] for n in graph.nodes])
        
        # Link
        graph.link_org_domain(org_id, brand_id)
        # Check edge
        edges = [e for e in graph.edges if e["from"] == org_id and e["relation"] == "ORG_OWNS_DOMAIN"]
        self.assertEqual(len(edges), 1)
        
        # 2. SaaS
        saas_id = graph.add_saas_app("Salesforce", "CRM", "salesforce.com")
        graph.link_org_saas(org_id, saas_id)
        
        # 3. High Value Count
        # SAAS_APP is high value
        self.assertEqual(graph.count_highvalue_nodes(), 1)
        
        # 4. Leak
        leak_id = graph.add_leak("api_key", "github_search", "Found AWS Key", 0.9)
        graph.link_leak_org(leak_id, org_id)
        
        # Count should go up
        self.assertEqual(graph.count_highvalue_nodes(), 2)

    def test_hypothesis_chain(self):
        graph = AssetGraph()
        
        ep_id = graph.add_endpoint("/login", "GET", "CRAWL", "http://site.com")
        vuln_id = "hypo_vuln" # Fake support ID
        graph._add_node(vuln_id, "VULNERABILITY", {})
        
        hypo_id = graph.add_hypothesis(
            "Attack Chain Possible",
            "Credential Stuffing",
            0.8,
            [ep_id, vuln_id]
        )
        
        # Check edges
        edges = [e for e in graph.edges if e["from"] == hypo_id]
        self.assertEqual(len(edges), 2)
        
if __name__ == '__main__':
    unittest.main()
