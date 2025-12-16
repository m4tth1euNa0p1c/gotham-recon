
import unittest
import json
from recon_gotham.tools.python_script_executor_tool import PythonScriptExecutorTool

class TestPythonExecutor(unittest.TestCase):
    
    def setUp(self):
        self.tool = PythonScriptExecutorTool()

    def test_safe_execution(self):
        code = "import json; print(json.dumps({'foo': 'bar'}))"
        result_json = self.tool._run(code)
        result = json.loads(result_json)
        self.assertEqual(result["status"], "success")
        self.assertIn("bar", result["stdout"])

    def test_unsafe_import(self):
        code = "import os; print(os.system('ls'))"
        result_json = self.tool._run(code)
        result = json.loads(result_json)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("Safety Violation", result["error"])

    def test_syntax_error(self):
        code = "print('hello"
        result_json = self.tool._run(code)
        result = json.loads(result_json)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("Syntax Error", result["error"])

if __name__ == '__main__':
    unittest.main()
