import unittest
from recon_gotham.core.asset_graph import AssetGraph

class TestAssetGraph(unittest.TestCase):
    def setUp(self):
        self.graph = AssetGraph()

    def test_add_subdomain_with_http_creates_nodes_and_edge(self):
        item = {
            "subdomain": "dev.example.com",
            "priority": 9,
            "tag": "DEV_API",
            "category": "APP_BACKEND",
            "http": {
                "url": "https://dev.example.com",
                "status_code": 200,
                "technologies": ["nginx"],
                "ip": "1.2.3.4",
                "title": "Dev Portal"
            }
        }
        self.graph.add_subdomain_with_http(item)

        # Verify Nodes
        sub_node = next((n for n in self.graph.nodes if n["id"] == "dev.example.com"), None)
        http_node = next((n for n in self.graph.nodes if n["id"].startswith("http:https://dev.example.com")), None)
        
        self.assertIsNotNone(sub_node)
        self.assertIsNotNone(http_node)
        
        self.assertEqual(sub_node["type"], "SUBDOMAIN")
        self.assertEqual(http_node["type"], "HTTP_SERVICE")
        self.assertEqual(sub_node["properties"]["tag"], "DEV_API")
        self.assertIn("nginx", http_node["properties"]["technologies"])

        # Verify Edge
        edge = next((e for e in self.graph.edges if e["from"] == "dev.example.com" and e["to"] == http_node["id"]), None)
        self.assertIsNotNone(edge)
        self.assertEqual(edge["relation"], "EXPOSES_HTTP")

    def test_add_subdomain_idempotency(self):
        item = {
            "subdomain": "idempotent.example.com",
            "priority": 5,
            "http": {"url": "http://idempotent.example.com"}
        }
        
        # Add twice
        self.graph.add_subdomain_with_http(item)
        self.graph.add_subdomain_with_http(item)
        
        # Count nodes with this ID
        count = len([n for n in self.graph.nodes if n["id"] == "idempotent.example.com"])
        self.assertEqual(count, 1, "Duplicate subdomain nodes created")

    def test_add_js_analysis(self):
        # Setup parent http service first (implicit requirement usually, or handled gracefully)
        # Assuming URL maps to a node. The graph helper might need the parent to exist or it creates links loosely?
        # Let's check asset_graph.py logic if I see it, but usually standard graph approach.
        
        js_data = {
            "js_files": ["https://target.com/app.js"],
            "endpoints": [{"path": "/api/v1/login", "method": "GET", "source_js": "app.js"}],
            "secrets": []
        }
        parent_url = "https://target.com"
        
        # We need to ensure the parent HTTP node exists for the edge to likely make sense, 
        # but add_js_analysis might just find the node by URL property.
        # Let's verify behavior. For now, I'll add the parent first.
        self.graph.add_subdomain_with_http({
            "subdomain": "target.com", 
            "http": {"url": parent_url}
        })
        
        self.graph.add_js_analysis(js_data, parent_url)
        
        # Verify JS Node
        js_node = next((n for n in self.graph.nodes if n["type"] == "JS_FILE" and "app.js" in n["id"]), None)
        self.assertIsNotNone(js_node)
        self.assertEqual(js_node["properties"]["url"], "https://target.com/app.js")
        
        # Verify Edge from HTTP -> JS
        # We need to find the HTTP node ID for 'https://target.com'
        http_node = next(n for n in self.graph.nodes if n["type"] == "HTTP_SERVICE" and n["properties"]["url"] == parent_url)
        
        edge = next((e for e in self.graph.edges if e["from"] == http_node["id"] and e["to"] == js_node["id"]), None)
        self.assertIsNotNone(edge)
        self.assertEqual(edge["relation"], "LOADS_JS")

if __name__ == '__main__':
    unittest.main()
