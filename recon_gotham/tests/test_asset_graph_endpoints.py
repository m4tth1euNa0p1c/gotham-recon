
import unittest
from recon_gotham.core.asset_graph import AssetGraph

class TestAssetGraphEndpoints(unittest.TestCase):
    def test_add_endpoint_normalization(self):
        graph = AssetGraph()
        
        # Test Normalization
        # Input: /api/v1/users?id=123
        # Expected: /api/v1/users
        graph.add_endpoint("/api/v1/users?id=123", "GET", "JS", "https://target.com/app.js")
        
        node = graph.nodes[0] # First node might be the service or the endpoint depending on order, let's check by ID
        
        # Check if Service Node created
        service_node = next((n for n in graph.nodes if n["type"] == "HTTP_SERVICE"), None)
        self.assertIsNotNone(service_node)
        self.assertEqual(service_node["id"], "http:https://target.com")
        
        # Check Endpoint Node
        ep_node = next((n for n in graph.nodes if n["type"] == "ENDPOINT"), None)
        self.assertIsNotNone(ep_node)
        self.assertEqual(ep_node["properties"]["path"], "/api/v1/users")
        self.assertEqual(ep_node["properties"]["method"], "GET")
        
        # Check Edge
        edge = graph.edges[0]
        self.assertEqual(edge["relation"], "EXPOSES_ENDPOINT")
        self.assertEqual(edge["from"], "http:https://target.com")
        self.assertEqual(edge["to"], ep_node["id"])

    def test_add_endpoint_relative(self):
        graph = AssetGraph()
        # Input: api/v2/login (no slash)
        graph.add_endpoint("api/v2/login", "POST", "HTML", "https://target.com/login")
        
        ep_node = next((n for n in graph.nodes if n["type"] == "ENDPOINT"), None)
        self.assertEqual(ep_node["properties"]["path"], "/api/v2/login")

if __name__ == '__main__':
    unittest.main()
