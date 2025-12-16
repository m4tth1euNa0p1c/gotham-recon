
import unittest
import json
from unittest.mock import MagicMock, patch
from recon_gotham.tools.html_crawler_tool import HtmlCrawlerTool
from recon_gotham.tools.wayback_tool import WaybackTool
from recon_gotham.tools.robots_tool import RobotsTool
from recon_gotham.tools.js_miner_tool import JsMinerTool

class TestEndpointTools(unittest.TestCase):

    def test_html_crawler(self):
        tool = HtmlCrawlerTool()
        
        mock_html = """
        <html>
            <a href="/api/users">Users</a>
            <form action="/auth/login" method="POST"></form>
            <script src="/js/app.js"></script>
        </html>
        """
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.text = mock_html
            mock_get.return_value.status_code = 200
            
            result_json = tool._run(["https://target.com"])
            results = json.loads(result_json)
            
            self.assertTrue(len(results) >= 2)
            
            # Check Link
            link_ep = next((r for r in results if r["path"] == "/api/users"), None)
            self.assertIsNotNone(link_ep)
            self.assertEqual(link_ep["method"], "GET")
            
            # Check Form
            form_ep = next((r for r in results if r["path"] == "/auth/login"), None)
            self.assertIsNotNone(form_ep)
            self.assertEqual(form_ep["method"], "POST")

    def test_robots_tool_endpoints(self):
        tool = RobotsTool()
        mock_robots = """
        User-agent: *
        Disallow: /admin/
        Disallow: /private_api/
        Sitemap: https://target.com/sitemap.xml
        """
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.text = mock_robots
            mock_get.return_value.status_code = 200
            
            # Mock sitemap 404 to avoid second call noise
            mock_get.side_effect = [
                MagicMock(status_code=200, text=mock_robots), # robots.txt
                MagicMock(status_code=404) # sitemap.xml call
            ]
            
            result_json = tool._run("https://target.com")
            data = json.loads(result_json)
            
            self.assertEqual(data["disallow_count"], 2)
            self.assertTrue(len(data["endpoints"]) >= 2)
            self.assertTrue(any(e["path"] == "/admin/" for e in data["endpoints"]))

    def test_js_miner_regex(self):
        tool = JsMinerTool()
        mock_js = """
        axios.post('/api/v1/create');
        fetch("/api/data");
        """
        
        # JsMiner downloads the page to find JS files/inline
        with patch('requests.get') as mock_get:
            mock_get.return_value.text = mock_js
            mock_get.return_value.status_code = 200
            
            result_json = tool._run(["https://target.com"])
            results = json.loads(result_json)
            
            eps = results[0]["js"]["endpoints"]
            
            # Check axios POST
            post_ep = next((e for e in eps if e["path"] == "/api/v1/create"), None)
            self.assertIsNotNone(post_ep)
            self.assertEqual(post_ep["method"], "POST")
            
            # Check fetch GET
            get_ep = next((e for e in eps if e["path"] == "/api/data"), None)
            self.assertIsNotNone(get_ep)

    def test_wayback_tool(self):
        tool = WaybackTool()
        # Mock CDX output
        # Format: [["original",...], ["http://target.com/api/old", ...]]
        mock_cdx = [
            ["original", "timestamp"],
            ["https://target.com/api/v1/old_endpoint", "20210101"],
            ["https://target.com/image.jpg", "20210101"], # Should be ignored
            ["https://target.com/admin/login.php", "20210101"]
        ]
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = mock_cdx
            mock_get.return_value.status_code = 200
            
            result_json = tool._run(["target.com"])
            results = json.loads(result_json)
            
            self.assertEqual(len(results), 2) # /api/... and /admin/...
            self.assertTrue(any(r["path"] == "https://target.com/api/v1/old_endpoint" for r in results))

if __name__ == '__main__':
    unittest.main()
