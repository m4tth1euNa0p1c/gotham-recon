import unittest
from unittest.mock import patch, MagicMock
from recon_gotham.tools.httpx_tool import HttpxTool
import json

class TestHttpxTool(unittest.TestCase):
    def setUp(self):
        self.tool = HttpxTool()

    def test_run_with_empty_list_returns_empty_json(self):
        result = self.tool._run(subdomains=[])
        data = json.loads(result)
        self.assertEqual(data["results"], [])

    def test_run_with_none_returns_empty_json(self):
        result = self.tool._run(subdomains=[]) # Tool expects list, None might crash or handle it. main.py handles it? 
        # HttpxTool signature: subdomains: List[str]. Passing None technically violates type hint but runtime python allows.
        # Guard clause in `httpx_tool.py`: `if not subdomains:` handles None.
        result = self.tool._run(subdomains=None) # type: ignore
        data = json.loads(result)
        self.assertEqual(data["results"], [])

    @patch('subprocess.run')
    def test_run_parsing_mock_output(self, mock_run):
        # Mock subprocess to return a JSONL string simulation httpx output
        # Httpx -json output is actually a JSON list or JSONL depending on flags.
        # Our tool implementation uses `-json` which usually outputs a JSON object per line (JSONL) 
        # OR a single JSON array if valid. Httpx default is JSONL.
        # Let's check httpx_tool.py implementation. 
        # It reads stdout.
        
        mock_stdout = '''
        {"url": "https://example.com", "status_code": 200, "tech": ["Nginx"], "title": "Example"}
        {"url": "https://api.example.com", "status_code": 403, "tech": ["Cloudflare"]}
        '''
        
        mock_proc = MagicMock()
        mock_proc.stdout = mock_stdout
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc
        
        result_json = self.tool._run(subdomains=["example.com"])
        result = json.loads(result_json)
        
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["url"], "https://example.com")
        self.assertEqual(result["results"][1]["status_code"], 403)

if __name__ == '__main__':
    unittest.main()
