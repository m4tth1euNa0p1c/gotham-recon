
import unittest
import json
from unittest.mock import MagicMock, patch
from recon_gotham.tools.python_script_executor_tool import PythonScriptExecutorTool

class TestCoderChain(unittest.TestCase):
    
    def test_coder_response_format_and_execution(self):
        # Simulate Agent Coder Output
        # The agent should return a JSON with "script_code"
        mock_agent_response = json.dumps({
            "script_code": "import json; print(json.dumps({'status': 'dynamic_success'}))",
            "description": "Test script"
        })
        
        # In main.py, we extract_json and then parse it
        # Let's verify that PythonScriptExecutorTool takes this code and runs it
        
        tool = PythonScriptExecutorTool()
        data = json.loads(mock_agent_response)
        code = data.get("script_code")
        
        self.assertIsNotNone(code)
        
        # Execute
        result_json = tool._run(code)
        result = json.loads(result_json)
        
        self.assertEqual(result["status"], "success")
        self.assertIn("dynamic_success", result["stdout"])

if __name__ == '__main__':
    unittest.main()
