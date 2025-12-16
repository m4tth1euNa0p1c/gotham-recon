
import unittest
import json
import subprocess
from unittest.mock import MagicMock, patch, mock_open

# Recon Tools
from recon_gotham.tools.subfinder_tool import SubfinderTool
from recon_gotham.tools.dns_resolver_tool import DnsResolverTool
from recon_gotham.tools.asn_lookup_tool import ASNLookupTool

# Active Tools
from recon_gotham.tools.httpx_tool import HttpxTool
from recon_gotham.tools.html_crawler_tool import HtmlCrawlerTool
from recon_gotham.tools.wayback_tool import WaybackTool
from recon_gotham.tools.my_robots_tool import MyRobotsTool
from recon_gotham.tools.js_miner_tool import JsMinerTool

# Offensive Tools
from recon_gotham.tools.nuclei_tool import NucleiTool
from recon_gotham.tools.ffuf_tool import FfufTool

# Reporting
from recon_gotham.reporting.report_builder import ReportBuilder

class TestReconTools(unittest.TestCase):

    @patch('subprocess.run')
    def test_subfinder_tool(self, mock_run):
        tool = SubfinderTool()
        mock_output = json.dumps([
            {"host": "admin.target.com", "source": "archive"},
            {"host": "www.target.com", "source": "crtsh"}
        ]) + "\n"
        
        # Mock subprocess.run return value
        mock_proc = MagicMock()
        mock_proc.stdout = mock_output
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        result_json = tool._run("target.com")
        results = json.loads(result_json)
        
        # Test basic parsing
        self.assertEqual(results["count"], 2)
        self.assertEqual(results["subdomains"][0], "admin.target.com")
        
        # Test empty result
        mock_proc.stdout = ""
        result_empty = tool._run("target.com")
        self.assertEqual(json.loads(result_empty)["subdomains"], [])

    @patch('dns.resolver.Resolver')
    def test_dns_resolver_tool(self, MockResolver):
        tool = DnsResolverTool()
        
        # Mock resolver instance
        resolver_instance = MockResolver.return_value
        
        # Mock A record response
        mock_a_ans = MagicMock()
        mock_a_ans.rrset = [MagicMock(to_text=lambda: "1.2.3.4")]
        
        # Determine side effect for query (A vs MX vs others)
        def query_side_effect(qname, rdtype):
            if rdtype == 'A':
                return mock_a_ans
            raise Exception("No record")
            
        resolver_instance.query.side_effect = query_side_effect
        
        results_json = tool._run(["sub.target.com"])
        results = json.loads(results_json)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["subdomain"], "sub.target.com")
        self.assertIn("1.2.3.4", results[0]["a_records"])

    @patch('requests.post')
    def test_asn_lookup_tool(self, mock_post):
        tool = ASNLookupTool()
        
        mock_api_response = [
            {"query": "1.2.3.4", "status": "success", "as": "AS15169 Google LLC", "org": "Google"}
        ]
        mock_post.return_value.json.return_value = mock_api_response
        mock_post.return_value.status_code = 200
        
        results_json = tool._run(["1.2.3.4"])
        results = json.loads(results_json)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["ip"], "1.2.3.4")
        self.assertIn("Google", results[0]["org"])


class TestActiveTools(unittest.TestCase):

    @patch('subprocess.run')
    def test_httpx_tool(self, mock_run):
        tool = HttpxTool()
        mock_json_out = json.dumps({
            "input": "http://www.target.com",
            "url": "http://www.target.com",
            "status_code": 200,
            "tech": ["Nginx", "React"],
            "title": "Welcome"
        }) + "\n"
        
        mock_proc = MagicMock()
        mock_proc.stdout = mock_json_out
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        # Test valid input
        result_json = tool._run(["www.target.com"])
        results = json.loads(result_json)
        self.assertEqual(results["result_count"], 1)
        self.assertEqual(results["results"][0]["title"], "Welcome")
        
        # Test empty input
        result_empty = tool._run([])
        self.assertEqual(json.loads(result_empty)["result_count"], 0)

    @patch('requests.get')
    def test_html_crawler_tool(self, mock_get):
        tool = HtmlCrawlerTool()
        mock_html = '<html><a href="/login">Login</a></html>'
        
        mock_get.return_value.text = mock_html
        mock_get.return_value.status_code = 200
        
        result_json = tool._run(["http://target.com"])
        results = json.loads(result_json)
        
        self.assertTrue(any(r["path"] == "/login" for r in results))

    @patch('requests.get')
    def test_my_robots_tool(self, mock_get):
        tool = MyRobotsTool()
        mock_txt = "User-agent: *\nDisallow: /admin"
        
        mock_get.return_value.text = mock_txt
        mock_get.return_value.status_code = 200
        # Fail sitemap check gracefully
        mock_get.side_effect = [
            MagicMock(status_code=200, text=mock_txt),
            MagicMock(status_code=404)
        ]
        
        result_json = tool._run("https://target.com")
        data = json.loads(result_json)
        
        self.assertIn("/admin", [e["path"] for e in data["endpoints"]])


class TestOffensiveTools(unittest.TestCase):
    
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_nuclei_tool_fallback(self, mock_exists, mock_file, mock_run):
        # We assume Docker fallback or local binary. 
        # This test ensures correct command construction.
        tool = NucleiTool()
        
        # Mock successful subprocess result
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        # Mock file handling
        # We need OS path exists to return True for output file reading
        # But we also write to input file.
        def side_effect_exists(path):
            if "nuclei_results_tmp.json" in path:
                return True
            return False
        mock_exists.side_effect = side_effect_exists

        # Mock file read content (Nuclei returns JSON Lines)
        mock_json_line = json.dumps({
            "template-id": "cve-2021-1234",
            "info": {"severity": "critical", "name": "Fake CVE"},
            "matched-at": "http://target.com",
            "matcher-name": "test"
        })
        mock_file.return_value.__enter__.return_value.__iter__.return_value = [mock_json_line]
        
        result_json = tool._run(["http://target.com"])
        results = json.loads(result_json)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Fake CVE")
        self.assertEqual(results[0]["severity"], "CRITICAL")
        
    @patch('subprocess.run')
    def test_ffuf_tool(self, mock_run):
        tool = FfufTool()
        
        mock_out = json.dumps({
            "results": [
                {"url": "http://target.com/admin", "status": 200, "length": 500}
            ]
        })
        
        mock_proc = MagicMock()
        mock_proc.stdout = mock_out
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        # Test running with specific wordlist
        result_json = tool._run("http://target.com")
        results = json.loads(result_json)
        
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["endpoint"], "/admin")


class TestReporting(unittest.TestCase):
    
    def test_report_builder_markdown(self):
        builder = ReportBuilder()
        
        mock_graph_data = {
            "nodes": [
                {"type": "SUBDOMAIN", "id": "a.com"},
                {"type": "VULNERABILITY", "id": "vuln1", "properties": {"severity": "HIGH", "name": "SQLi", "confirmed": True}}
            ]
        }
        mock_plan = [{"subdomain": "a.com", "score": 10, "reason": "Test"}]
        mock_chains = []
        
        # Use valid method name _build_markdown (or verify public API)
        # Note: In report_builder.py it is _build_markdown(domain, graph_data, attack_plan, chains)
        md_content = builder._build_markdown("target.com", mock_graph_data, mock_plan, mock_chains)
        
        self.assertIn("# 🚩 Red Team Mission Report: target.com", md_content)
        self.assertIn("CRITICAL ISSUES FOUND", md_content)
        self.assertIn("SQLi", md_content)

if __name__ == '__main__':
    unittest.main()
