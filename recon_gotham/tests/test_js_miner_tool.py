import unittest
from unittest.mock import patch, MagicMock
from recon_gotham.tools.js_miner_tool import JsMinerTool
import json

class TestJsMinerTool(unittest.TestCase):
    def setUp(self):
        self.tool = JsMinerTool()

    @patch('requests.get')
    def test_js_func_extraction(self, mock_get):
        # Mock HTML response
        base_html = """
        <html>
            <body>
                <script src="app.js"></script>
                <script>
                    var API_KEY = "12345";
                    // Leaked AWS Key potentially
                    var AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"; 
                    // Endpoint
                    fetch("/api/v1/users");
                </script>
            </body>
        </html>
        """
        
        # Mock JS response (unused by tool currently, but kept for future proofing)
        js_content = """
        const ENDPOINT = "https://api.internal.com/v1/users";
        const SECRET = "AKIAIOSFODNN7EXAMPLE";
        """
        
        # Configure side_effect for multiple calls
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if url == "https://target.com":
                resp.text = base_html
            elif "app.js" in url:
                resp.text = js_content
            else:
                resp.text = ""
            return resp
            
        mock_get.side_effect = side_effect
        
        result_json = self.tool._run(urls=["https://target.com"])
        result = json.loads(result_json)
        
        # Verify Structure (tool returns list of results)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        res_item = result[0]
        
        self.assertEqual(res_item["url"], "https://target.com")
        
        # Verify Findings
        js_data = res_item["js"]
        
        # JS Files
        self.assertTrue(any("app.js" in f for f in js_data["js_files"]))
        
        # Secrets (AWS Key regex usually catches AKIA...)
        # Note: Depends on actual regex in tool. Assuming standard patterns.
        self.assertTrue(any("AKIA" in s.get("value", "") for s in js_data["secrets"]), "Should detect AWS key")
        
        
        # Endpoints
        self.assertTrue(any("/api/v1/users" in e.get("path", "") for e in js_data["endpoints"]), "Should detect API endpoint")

if __name__ == '__main__':
    unittest.main()
