"""
Security Testing Module - Phase 25
Comprehensive vulnerability detection with Ollama CoderAgent integration.
"""

import requests
import json
import re
import os
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urljoin, parse_qs, urlencode
from dotenv import load_dotenv


load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CODER_MODEL = os.getenv("OLLAMA_CODER_MODEL", "qwen2.5-coder:7b")


class VulnerabilityTester:
    """
    Comprehensive vulnerability testing based on discovered endpoints.
    Integrates with Ollama qwen2.5-coder for intelligent analysis.
    """
    
    # Payloads for different vulnerability types
    PAYLOADS = {
        "sqli": [
            "'", "\"", "' OR '1'='1", "\" OR \"1\"=\"1", 
            "1' AND '1'='1", "1; DROP TABLE--", "' UNION SELECT NULL--"
        ],
        "xss": [
            "<script>alert(1)</script>", "<img src=x onerror=alert(1)>",
            "javascript:alert(1)", "'-alert(1)-'", "<svg/onload=alert(1)>"
        ],
        "lfi": [
            "../../../etc/passwd", "....//....//....//etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam", "file:///etc/passwd"
        ],
        "ssrf": [
            "http://localhost", "http://127.0.0.1", "http://169.254.169.254",
            "http://[::1]", "http://0.0.0.0"
        ],
        "open_redirect": [
            "//evil.com", "https://evil.com", "/\\evil.com", "//google.com%2F%2F"
        ],
        "rce": [
            ";id", "|id", "$(id)", "`id`", ";whoami", "|whoami"
        ]
    }
    
    # Parameter patterns indicating potential vulnerabilities
    PARAM_PATTERNS = {
        "sqli": ["id", "user", "uid", "name", "search", "query", "q", "order", "sort", "where"],
        "xss": ["msg", "message", "text", "input", "comment", "content", "value", "redirect_to"],
        "lfi": ["file", "path", "page", "document", "folder", "include", "template", "filename"],
        "ssrf": ["url", "uri", "host", "dest", "redirect", "next", "target", "fetch", "link"],
        "idor": ["id", "uid", "user_id", "account", "profile", "order_id", "doc_id"],
        "open_redirect": ["redirect", "url", "next", "return", "goto", "destination", "redir"]
    }
    
    def __init__(self, timeout: int = 10, verify_ssl: bool = False):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SecurityTester/1.0"
        }
        self.results = []
    
    def analyze_endpoint_for_vulns(self, endpoint: Dict) -> Dict:
        """
        Analyze a single endpoint for potential vulnerabilities.
        """
        path = endpoint.get("path", "")
        origin = endpoint.get("origin", "")
        method = endpoint.get("method", "GET")
        category = endpoint.get("category", "UNKNOWN")
        
        vulns = {
            "endpoint": path,
            "origin": origin,
            "potential_vulns": [],
            "high_priority": False,
            "suggested_tests": []
        }
        
        # Check based on path patterns
        path_lower = path.lower()
        
        # Admin/Auth endpoints - high priority
        if any(p in path_lower for p in ["/admin", "/login", "/auth", "/dashboard"]):
            vulns["high_priority"] = True
            vulns["potential_vulns"].append("AUTH_BYPASS")
            vulns["potential_vulns"].append("BRUTE_FORCE")
            vulns["suggested_tests"].extend(["nuclei_auth", "ffuf_login"])
        
        # API endpoints
        if "/api/" in path_lower or "/v1/" in path_lower or "/v2/" in path_lower:
            vulns["potential_vulns"].append("API_ABUSE")
            vulns["potential_vulns"].append("IDOR")
            vulns["suggested_tests"].extend(["ffuf_api", "nuclei_api"])
        
        # File handling endpoints
        if any(p in path_lower for p in ["file", "upload", "download", "document", "image"]):
            vulns["potential_vulns"].append("LFI")
            vulns["potential_vulns"].append("PATH_TRAVERSAL")
            vulns["suggested_tests"].append("ffuf_lfi")
        
        # Search/Query endpoints
        if any(p in path_lower for p in ["search", "query", "find", "filter"]):
            vulns["potential_vulns"].append("SQLI")
            vulns["potential_vulns"].append("XSS")
            vulns["suggested_tests"].extend(["sqlmap", "xss_probe"])
        
        # Redirect endpoints
        if any(p in path_lower for p in ["redirect", "goto", "return", "next"]):
            vulns["potential_vulns"].append("OPEN_REDIRECT")
            vulns["suggested_tests"].append("redirect_test")
        
        # PHP/ASP endpoints - often vulnerable
        if path.endswith(".php") or path.endswith(".asp"):
            vulns["potential_vulns"].append("CODE_INJECTION")
            vulns["high_priority"] = True
        
        # GraphQL
        if "graphql" in path_lower:
            vulns["potential_vulns"].append("GRAPHQL_INTROSPECTION")
            vulns["suggested_tests"].append("nuclei_graphql")
        
        return vulns

    def analyze_parameters(self, params: List[Dict]) -> List[Dict]:
        """
        Analyze parameters for potential vulnerability patterns.
        """
        param_vulns = []
        
        for param in params:
            name = param.get("name", "").lower()
            location = param.get("location", "query")
            
            param_vuln = {
                "name": param.get("name"),
                "location": location,
                "potential_vulns": [],
                "test_priority": "LOW"
            }
            
            # Check against patterns
            for vuln_type, patterns in self.PARAM_PATTERNS.items():
                if any(p in name for p in patterns):
                    param_vuln["potential_vulns"].append(vuln_type.upper())
                    param_vuln["test_priority"] = "HIGH" if vuln_type in ["sqli", "rce", "ssrf"] else "MEDIUM"
            
            if param_vuln["potential_vulns"]:
                param_vulns.append(param_vuln)
        
        return param_vulns

    def generate_test_cases(self, endpoint: Dict, params: List[Dict]) -> List[Dict]:
        """
        Generate specific test cases for an endpoint and its parameters.
        """
        test_cases = []
        origin = endpoint.get("origin", "")
        
        # For each vulnerable parameter, generate test payloads
        param_vulns = self.analyze_parameters(params)
        
        for pv in param_vulns:
            for vuln_type in pv["potential_vulns"]:
                vuln_key = vuln_type.lower()
                if vuln_key in self.PAYLOADS:
                    for payload in self.PAYLOADS[vuln_key][:3]:  # Limit to 3 payloads per type
                        test_cases.append({
                            "type": vuln_type,
                            "param": pv["name"],
                            "payload": payload,
                            "method": endpoint.get("method", "GET"),
                            "priority": pv["test_priority"]
                        })
        
        return test_cases

    def ask_coder_agent(self, context: str, question: str) -> Optional[str]:
        """
        Query Ollama qwen2.5-coder for intelligent analysis or script generation.
        """
        try:
            prompt = f"""You are a security testing expert. Analyze the following and provide actionable insights.

Context:
{context}

Question:
{question}

Provide concise, actionable output. If generating code, ensure it's complete and executable Python."""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_CODER_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
                
        except Exception as e:
            return f"CoderAgent Error: {str(e)}"
        
        return None

    def generate_recovery_script(self, error: str, context: Dict) -> Optional[str]:
        """
        Use CoderAgent to generate a recovery script when tools fail.
        """
        prompt_context = f"""
Tool Error: {error}
Target URL: {context.get('url', 'N/A')}
Endpoint Path: {context.get('path', 'N/A')}
Expected Action: {context.get('action', 'N/A')}
"""
        
        question = """Generate a Python script using 'requests' library to:
1. Handle this error gracefully
2. Extract the data we need
3. Return results in JSON format

The script should be minimal, focused, and include error handling."""

        return self.ask_coder_agent(prompt_context, question)


def analyze_graph_for_security(graph_path: str) -> Dict:
    """
    Analyze an AssetGraph for security vulnerabilities and generate test plan.
    """
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    
    tester = VulnerabilityTester()
    
    results = {
        "high_priority_targets": [],
        "endpoint_analysis": [],
        "parameter_analysis": [],
        "test_cases": [],
        "suggested_nuclei_templates": [],
        "summary": {}
    }
    
    # Get endpoints and parameters
    endpoints = [n for n in graph.get("nodes", []) if n["type"] == "ENDPOINT"]
    parameters = [n for n in graph.get("nodes", []) if n["type"] == "PARAMETER"]
    
    print(f"[*] Analyzing {len(endpoints)} endpoints and {len(parameters)} parameters...")
    
    # Analyze each endpoint
    for ep in endpoints:
        props = ep.get("properties", {})
        analysis = tester.analyze_endpoint_for_vulns(props)
        results["endpoint_analysis"].append(analysis)
        
        if analysis["high_priority"]:
            results["high_priority_targets"].append({
                "endpoint": analysis["endpoint"],
                "vulns": analysis["potential_vulns"]
            })
    
    # Analyze parameters
    param_list = [p.get("properties", {}) for p in parameters]
    results["parameter_analysis"] = tester.analyze_parameters(param_list)
    
    # Generate Nuclei template suggestions
    all_vulns = set()
    for ea in results["endpoint_analysis"]:
        all_vulns.update(ea["potential_vulns"])
    
    nuclei_mapping = {
        "SQLI": ["sqli", "sql-injection"],
        "XSS": ["xss", "reflected-xss", "stored-xss"],
        "LFI": ["lfi", "file-inclusion"],
        "SSRF": ["ssrf"],
        "AUTH_BYPASS": ["auth-bypass", "default-credentials"],
        "OPEN_REDIRECT": ["open-redirect"],
        "API_ABUSE": ["api", "improper-api"],
        "IDOR": ["idor"]
    }
    
    for vuln in all_vulns:
        if vuln in nuclei_mapping:
            results["suggested_nuclei_templates"].extend(nuclei_mapping[vuln])
    
    results["suggested_nuclei_templates"] = list(set(results["suggested_nuclei_templates"]))
    
    # Summary
    results["summary"] = {
        "total_endpoints": len(endpoints),
        "high_priority_count": len(results["high_priority_targets"]),
        "vulnerable_params": len(results["parameter_analysis"]),
        "unique_vuln_types": len(all_vulns),
        "nuclei_templates": len(results["suggested_nuclei_templates"])
    }
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python security_tester.py <graph_path>")
        sys.exit(1)
    
    graph_path = sys.argv[1]
    results = analyze_graph_for_security(graph_path)
    
    print("\n" + "=" * 60)
    print("SECURITY ANALYSIS REPORT")
    print("=" * 60)
    
    print(f"\n📊 Summary:")
    print(f"   Total Endpoints: {results['summary']['total_endpoints']}")
    print(f"   High Priority Targets: {results['summary']['high_priority_count']}")
    print(f"   Vulnerable Parameters: {results['summary']['vulnerable_params']}")
    print(f"   Unique Vuln Types: {results['summary']['unique_vuln_types']}")
    
    print(f"\n🎯 High Priority Targets:")
    for target in results["high_priority_targets"][:10]:
        print(f"   {target['endpoint']}: {', '.join(target['vulns'])}")
    
    print(f"\n🔧 Suggested Nuclei Templates:")
    print(f"   {', '.join(results['suggested_nuclei_templates'])}")
    
    # Save report
    report_path = graph_path.replace("_asset_graph.json", "_security_analysis.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Report saved: {report_path}")
