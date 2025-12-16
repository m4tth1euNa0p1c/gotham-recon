"""
Page Analyzer Tool - Phase 24
Comprehensive endpoint analysis with backend interaction detection.
Uses Ollama qwen2.5-coder:7b for code understanding.
"""

import requests
import json
import re
import os
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CODER_MODEL = os.getenv("OLLAMA_CODER_MODEL", "qwen2.5-coder:7b")


class PageAnalyzer:
    """
    Comprehensive page analyzer that extracts:
    - Forms and input fields
    - API endpoints from JavaScript
    - Backend interaction patterns
    - Authentication mechanisms
    - Data submission points
    """
    
    def __init__(self, timeout: int = 15, verify_ssl: bool = False):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    
    def analyze_url(self, url: str) -> Dict:
        """
        Perform comprehensive analysis of a URL.
        Returns detailed analysis including forms, APIs, and backend interactions.
        """
        result = {
            "url": url,
            "status": None,
            "reachable": False,
            "analysis": {
                "forms": [],
                "api_endpoints": [],
                "js_files": [],
                "input_fields": [],
                "auth_mechanisms": [],
                "backend_interactions": [],
                "technologies": [],
                "sensitive_data": [],
                "attack_surface": []
            },
            "code_analysis": None,
            "error": None
        }
        
        try:
            # Fetch page content
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=True
            )
            
            result["status"] = response.status_code
            result["reachable"] = True
            
            content_type = response.headers.get("Content-Type", "")
            
            if "text/html" in content_type:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract forms
                result["analysis"]["forms"] = self._extract_forms(soup, url)
                
                # Extract input fields
                result["analysis"]["input_fields"] = self._extract_inputs(soup)
                
                # Extract JS files
                result["analysis"]["js_files"] = self._extract_js_files(soup, url)
                
                # Detect auth mechanisms
                result["analysis"]["auth_mechanisms"] = self._detect_auth(soup, response.text)
                
                # Extract inline API calls
                result["analysis"]["api_endpoints"] = self._extract_api_calls(response.text)
                
                # Detect technologies
                result["analysis"]["technologies"] = self._detect_technologies(response, soup)
                
                # Detect sensitive data exposure
                result["analysis"]["sensitive_data"] = self._detect_sensitive_data(response.text)
                
                # Build attack surface
                result["analysis"]["attack_surface"] = self._build_attack_surface(result["analysis"])
                
                # Backend interactions
                result["analysis"]["backend_interactions"] = self._detect_backend_interactions(
                    soup, response.text, url
                )
                
            elif "application/json" in content_type:
                # JSON response - analyze API structure
                try:
                    json_data = response.json()
                    result["analysis"]["api_endpoints"].append({
                        "url": url,
                        "method": "GET",
                        "response_type": "JSON",
                        "keys": list(json_data.keys()) if isinstance(json_data, dict) else "array"
                    })
                except:
                    pass
                    
        except requests.exceptions.RequestException as e:
            result["error"] = str(e)[:200]
        
        return result
    
    def _extract_forms(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract all forms with their action, method, and fields."""
        forms = []
        for form in soup.find_all('form'):
            action = form.get('action', '')
            if action:
                action = urljoin(base_url, action)
            
            form_data = {
                "action": action,
                "method": form.get('method', 'GET').upper(),
                "id": form.get('id', ''),
                "enctype": form.get('enctype', 'application/x-www-form-urlencoded'),
                "fields": []
            }
            
            # Extract all input fields in this form
            for inp in form.find_all(['input', 'textarea', 'select']):
                field = {
                    "name": inp.get('name', ''),
                    "type": inp.get('type', 'text'),
                    "id": inp.get('id', ''),
                    "required": inp.has_attr('required'),
                    "value": inp.get('value', '')
                }
                if field["name"]:
                    form_data["fields"].append(field)
            
            forms.append(form_data)
        
        return forms
    
    def _extract_inputs(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract all input fields on the page."""
        inputs = []
        for inp in soup.find_all(['input', 'textarea', 'select']):
            field = {
                "name": inp.get('name', ''),
                "type": inp.get('type', 'text'),
                "id": inp.get('id', ''),
                "placeholder": inp.get('placeholder', ''),
                "autocomplete": inp.get('autocomplete', ''),
                "sensitive": self._is_sensitive_input(inp)
            }
            if field["name"] or field["id"]:
                inputs.append(field)
        return inputs
    
    def _is_sensitive_input(self, inp) -> bool:
        """Check if an input field is sensitive."""
        sensitive_patterns = [
            'password', 'passwd', 'pwd', 'secret', 'token', 'key', 'api',
            'auth', 'credit', 'card', 'cvv', 'ssn', 'social', 'private'
        ]
        name = (inp.get('name', '') + inp.get('id', '') + inp.get('type', '')).lower()
        return any(p in name for p in sensitive_patterns)
    
    def _extract_js_files(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract JavaScript file URLs."""
        js_files = []
        for script in soup.find_all('script', src=True):
            src = script.get('src', '')
            if src:
                js_files.append(urljoin(base_url, src))
        return js_files[:20]  # Limit to 20
    
    def _detect_auth(self, soup: BeautifulSoup, html: str) -> List[Dict]:
        """Detect authentication mechanisms."""
        auth_mechanisms = []
        
        # Check for login forms
        login_patterns = ['login', 'signin', 'auth', 'connect']
        for form in soup.find_all('form'):
            action = form.get('action', '').lower()
            if any(p in action for p in login_patterns):
                auth_mechanisms.append({
                    "type": "LOGIN_FORM",
                    "action": form.get('action', ''),
                    "method": form.get('method', 'POST')
                })
        
        # Check for OAuth
        if 'oauth' in html.lower():
            auth_mechanisms.append({"type": "OAUTH", "detected_in": "page_content"})
        
        # Check for JWT
        if 'jwt' in html.lower() or 'bearer' in html.lower():
            auth_mechanisms.append({"type": "JWT", "detected_in": "page_content"})
        
        # Check for CSRF tokens
        csrf_inputs = soup.find_all('input', {'name': re.compile(r'csrf|token|_token', re.I)})
        if csrf_inputs:
            auth_mechanisms.append({
                "type": "CSRF_PROTECTION",
                "tokens": [inp.get('name') for inp in csrf_inputs]
            })
        
        return auth_mechanisms
    
    def _extract_api_calls(self, html: str) -> List[Dict]:
        """Extract API endpoints from JavaScript code."""
        api_endpoints = []
        
        # Pattern for fetch/axios calls
        patterns = [
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.(get|post|put|delete)\(["\']([^"\']+)["\']',
            r'\.ajax\(\{[^}]*url:\s*["\']([^"\']+)["\']',
            r'XMLHttpRequest.*open\(["\'](\w+)["\'],\s*["\']([^"\']+)["\']',
            r'/api/[a-zA-Z0-9_/]+',
            r'/v[0-9]+/[a-zA-Z0-9_/]+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    endpoint = match[-1] if len(match) > 1 else match[0]
                else:
                    endpoint = match
                
                if endpoint and not endpoint.startswith('data:'):
                    api_endpoints.append({
                        "endpoint": endpoint,
                        "source": "inline_js"
                    })
        
        return api_endpoints[:30]  # Limit
    
    def _detect_technologies(self, response, soup: BeautifulSoup) -> List[str]:
        """Detect technologies from headers and page content."""
        techs = []
        
        # Server header
        server = response.headers.get('Server', '')
        if server:
            techs.append(f"Server: {server}")
        
        # X-Powered-By
        powered_by = response.headers.get('X-Powered-By', '')
        if powered_by:
            techs.append(f"Powered-By: {powered_by}")
        
        # Framework detection from meta tags
        generators = soup.find_all('meta', {'name': 'generator'})
        for gen in generators:
            techs.append(f"Generator: {gen.get('content', '')}")
        
        # Common frameworks
        html = str(soup)
        framework_patterns = {
            'react': r'react|__NEXT_DATA__|_next/',
            'angular': r'ng-|angular',
            'vue': r'vue|__VUE__',
            'jquery': r'jquery',
            'wordpress': r'wp-content|wordpress',
            'drupal': r'drupal|sites/default',
            'laravel': r'laravel',
            'django': r'csrfmiddlewaretoken|django'
        }
        
        for tech, pattern in framework_patterns.items():
            if re.search(pattern, html, re.I):
                techs.append(tech.capitalize())
        
        return list(set(techs))
    
    def _detect_sensitive_data(self, html: str) -> List[Dict]:
        """Detect potential sensitive data exposure."""
        sensitive = []
        
        patterns = {
            "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            "api_key": r'(api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})',
            "aws_key": r'AKIA[0-9A-Z]{16}',
            "jwt_token": r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
            "private_ip": r'(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})'
        }
        
        for data_type, pattern in patterns.items():
            matches = re.findall(pattern, html)
            if matches:
                sensitive.append({
                    "type": data_type,
                    "count": len(matches),
                    "sample": str(matches[0])[:50] if matches else None
                })
        
        return sensitive
    
    def _build_attack_surface(self, analysis: Dict) -> List[Dict]:
        """Build attack surface summary from analysis."""
        attack_surface = []
        
        # Forms with POST -> potential injection points
        for form in analysis.get("forms", []):
            if form.get("method") == "POST":
                attack_surface.append({
                    "type": "POST_FORM",
                    "target": form.get("action"),
                    "fields": len(form.get("fields", [])),
                    "risk": "MEDIUM"
                })
        
        # API endpoints
        for api in analysis.get("api_endpoints", []):
            attack_surface.append({
                "type": "API_ENDPOINT",
                "target": api.get("endpoint"),
                "risk": "HIGH" if "/admin" in api.get("endpoint", "") else "MEDIUM"
            })
        
        # Sensitive inputs
        sensitive_inputs = [i for i in analysis.get("input_fields", []) if i.get("sensitive")]
        if sensitive_inputs:
            attack_surface.append({
                "type": "SENSITIVE_INPUTS",
                "count": len(sensitive_inputs),
                "risk": "HIGH"
            })
        
        return attack_surface
    
    def _detect_backend_interactions(self, soup: BeautifulSoup, html: str, base_url: str) -> List[Dict]:
        """Detect backend interaction patterns."""
        interactions = []
        
        # AJAX form submissions
        ajax_forms = soup.find_all('form', {'data-ajax': True})
        for form in ajax_forms:
            interactions.append({
                "type": "AJAX_FORM",
                "action": form.get('action', ''),
                "method": form.get('method', 'POST')
            })
        
        # WebSocket connections
        ws_patterns = re.findall(r'wss?://[^\s"\']+', html)
        for ws in ws_patterns:
            interactions.append({
                "type": "WEBSOCKET",
                "url": ws
            })
        
        # GraphQL
        if '/graphql' in html.lower():
            interactions.append({
                "type": "GRAPHQL",
                "detected": True
            })
        
        # REST API patterns
        rest_patterns = re.findall(r'/api/v?\d*/[a-zA-Z]+', html)
        for pattern in set(rest_patterns):
            interactions.append({
                "type": "REST_API",
                "pattern": pattern
            })
        
        return interactions

    def analyze_with_ollama(self, code: str, context: str = "") -> Optional[str]:
        """
        Use Ollama qwen2.5-coder to analyze code and provide insights.
        """
        try:
            prompt = f"""Analyze this code for security vulnerabilities and backend interactions:

Context: {context}

Code:
```
{code[:3000]}  # Limit code length
```

Provide a brief security analysis focusing on:
1. Potential vulnerabilities (XSS, SQLi, etc.)
2. API endpoints and their purpose
3. Authentication mechanisms
4. Data flow to backend

Be concise and actionable."""

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
            return f"Ollama analysis failed: {str(e)}"
        
        return None


def analyze_graph_endpoints(graph_path: str, max_endpoints: int = 10) -> Dict:
    """
    Analyze endpoints from an AssetGraph with comprehensive page analysis.
    """
    # Load graph
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    
    analyzer = PageAnalyzer()
    results = {
        "analyzed": [],
        "failed": [],
        "summary": {
            "total_forms": 0,
            "total_api_endpoints": 0,
            "total_auth_mechanisms": 0,
            "high_risk_targets": []
        }
    }
    
    # Get HTTP services to analyze
    http_services = [n for n in graph.get("nodes", []) if n["type"] == "HTTP_SERVICE"]
    
    print(f"[*] Analyzing {min(len(http_services), max_endpoints)} HTTP services...")
    
    for service in http_services[:max_endpoints]:
        url = service.get("properties", {}).get("url")
        if not url:
            continue
        
        print(f"    Analyzing: {url}")
        
        analysis = analyzer.analyze_url(url)
        
        if analysis["reachable"]:
            results["analyzed"].append(analysis)
            
            # Update summary
            results["summary"]["total_forms"] += len(analysis["analysis"]["forms"])
            results["summary"]["total_api_endpoints"] += len(analysis["analysis"]["api_endpoints"])
            results["summary"]["total_auth_mechanisms"] += len(analysis["analysis"]["auth_mechanisms"])
            
            # Track high-risk targets
            for surface in analysis["analysis"]["attack_surface"]:
                if surface.get("risk") == "HIGH":
                    results["summary"]["high_risk_targets"].append({
                        "url": url,
                        "type": surface["type"],
                        "target": surface.get("target", "")
                    })
        else:
            results["failed"].append({
                "url": url,
                "error": analysis["error"]
            })
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python page_analyzer.py <url_or_graph_path>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    if target.endswith('.json'):
        # Analyze graph file
        results = analyze_graph_endpoints(target)
        
        print(f"\n{'='*60}")
        print("PAGE ANALYSIS REPORT")
        print('='*60)
        print(f"\nAnalyzed: {len(results['analyzed'])} pages")
        print(f"Failed: {len(results['failed'])} pages")
        print(f"\nTotal Forms: {results['summary']['total_forms']}")
        print(f"Total API Endpoints: {results['summary']['total_api_endpoints']}")
        print(f"Auth Mechanisms: {results['summary']['total_auth_mechanisms']}")
        print(f"High-Risk Targets: {len(results['summary']['high_risk_targets'])}")
        
        # Save report
        report_path = target.replace("_asset_graph.json", "_page_analysis.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\n[+] Report saved: {report_path}")
    else:
        # Analyze single URL
        analyzer = PageAnalyzer()
        result = analyzer.analyze_url(target)
        print(json.dumps(result, indent=2))
