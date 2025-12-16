"""
Reflection Architecture for Agent Result Validation and Enrichment.

This module provides:
1. ReflectorAgent - Analyzes tool results, identifies gaps, validates data
2. CoderAgent - Generates Python scripts to investigate leads and enrich data
3. ReflectionLoop - Orchestrates iterative refinement cycles

P0.6: Adds reasoning layer on top of tool execution for better accuracy.
"""

import json
import time
import asyncio
import httpx
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ReflectionType(Enum):
    """Types of reflection actions."""
    VALIDATE = "validate"           # Check if results are correct
    ENRICH = "enrich"               # Add missing data
    INVESTIGATE = "investigate"     # Deep dive on anomalies
    RECONCILE = "reconcile"         # Fix inconsistencies
    GENERATE_SCRIPT = "generate_script"  # Create investigation script


@dataclass
class ReflectionTask:
    """A task for the reflection loop to process."""
    task_id: str
    reflection_type: ReflectionType
    target_node_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, higher = more important
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    result: Optional[Dict] = None


@dataclass
class ReflectionResult:
    """Result of a reflection operation."""
    task_id: str
    success: bool
    findings: List[Dict] = field(default_factory=list)
    enrichments: List[Dict] = field(default_factory=list)
    scripts_generated: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    confidence: float = 0.0


class ResultAnalyzer:
    """
    Analyzes tool results to identify gaps, errors, and enrichment opportunities.
    """

    def __init__(self, llm_client=None, ollama_url: str = "http://host.docker.internal:11434"):
        self.llm_client = llm_client
        self.ollama_url = ollama_url
        self.model = "qwen2.5:14b"

    async def analyze_tool_result(
        self,
        tool_name: str,
        result: Any,
        expected_schema: Optional[Dict] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze a tool's result for completeness, validity, and enrichment opportunities.

        Returns:
            {
                "valid": bool,
                "completeness_score": float (0-1),
                "issues": [...],
                "enrichment_opportunities": [...],
                "suggested_actions": [...]
            }
        """
        analysis = {
            "valid": True,
            "completeness_score": 1.0,
            "issues": [],
            "enrichment_opportunities": [],
            "suggested_actions": []
        }

        # Basic validation
        if result is None:
            analysis["valid"] = False
            analysis["completeness_score"] = 0.0
            analysis["issues"].append({
                "type": "null_result",
                "severity": "critical",
                "message": f"Tool {tool_name} returned null result"
            })
            analysis["suggested_actions"].append({
                "action": "retry",
                "reason": "Null result indicates tool failure"
            })
            return analysis

        # Tool-specific analysis
        if tool_name == "subfinder":
            analysis = await self._analyze_subfinder_result(result, context)
        elif tool_name == "httpx":
            analysis = await self._analyze_httpx_result(result, context)
        elif tool_name == "dns_resolver":
            analysis = await self._analyze_dns_result(result, context)
        elif tool_name == "wayback":
            analysis = await self._analyze_wayback_result(result, context)
        else:
            # Generic analysis for unknown tools
            analysis = self._generic_analysis(tool_name, result)

        return analysis

    async def _analyze_subfinder_result(self, result: Any, context: Optional[Dict]) -> Dict:
        """Analyze subfinder subdomain enumeration results."""
        analysis = {
            "valid": True,
            "completeness_score": 0.5,
            "issues": [],
            "enrichment_opportunities": [],
            "suggested_actions": []
        }

        subdomains = []
        if isinstance(result, list):
            subdomains = result
        elif isinstance(result, dict):
            subdomains = result.get("subdomains", [])
        elif isinstance(result, str):
            subdomains = [s.strip() for s in result.split("\n") if s.strip()]

        target_domain = context.get("target_domain", "") if context else ""

        # Check for common issues
        if len(subdomains) == 0:
            analysis["valid"] = False
            analysis["completeness_score"] = 0.0
            analysis["issues"].append({
                "type": "no_subdomains",
                "severity": "warning",
                "message": "No subdomains found - may indicate tool failure or rate limiting"
            })
            analysis["suggested_actions"].extend([
                {"action": "retry_with_delay", "reason": "Possible rate limiting"},
                {"action": "try_alternative_sources", "reason": "Subfinder may be blocked"},
                {"action": "generate_script", "script_type": "dns_bruteforce", "reason": "Try DNS bruteforce"}
            ])

        # Check for out-of-scope results
        out_of_scope = [s for s in subdomains if target_domain and not s.endswith(target_domain)]
        if out_of_scope:
            analysis["issues"].append({
                "type": "out_of_scope",
                "severity": "warning",
                "message": f"Found {len(out_of_scope)} out-of-scope subdomains",
                "data": out_of_scope[:5]
            })

        # Enrichment opportunities
        if len(subdomains) > 0:
            analysis["enrichment_opportunities"].extend([
                {"type": "dns_resolution", "targets": subdomains, "reason": "Resolve IPs for all subdomains"},
                {"type": "http_probe", "targets": subdomains, "reason": "Check HTTP services"},
                {"type": "certificate_check", "targets": subdomains[:10], "reason": "Extract cert info for top subdomains"}
            ])
            analysis["completeness_score"] = min(1.0, len(subdomains) / 50)  # Expect ~50 subs for good coverage

        return analysis

    async def _analyze_httpx_result(self, result: Any, context: Optional[Dict]) -> Dict:
        """Analyze httpx HTTP probe results."""
        analysis = {
            "valid": True,
            "completeness_score": 0.5,
            "issues": [],
            "enrichment_opportunities": [],
            "suggested_actions": []
        }

        services = []
        if isinstance(result, list):
            services = result
        elif isinstance(result, dict):
            services = result.get("services", []) or result.get("results", [])

        # Check for response issues
        failed_probes = [s for s in services if s.get("status_code", 0) == 0]
        if failed_probes:
            analysis["issues"].append({
                "type": "failed_probes",
                "severity": "info",
                "message": f"{len(failed_probes)} hosts didn't respond",
                "data": [f.get("host") for f in failed_probes[:5]]
            })

        # Check for interesting status codes
        redirects = [s for s in services if 300 <= s.get("status_code", 0) < 400]
        errors = [s for s in services if s.get("status_code", 0) >= 500]

        if redirects:
            analysis["enrichment_opportunities"].append({
                "type": "follow_redirects",
                "targets": [r.get("host") for r in redirects],
                "reason": "Follow redirects to find final destinations"
            })

        if errors:
            analysis["enrichment_opportunities"].append({
                "type": "investigate_errors",
                "targets": [e.get("host") for e in errors],
                "reason": "5xx errors may indicate misconfigurations"
            })

        # Check for missing tech detection
        no_tech = [s for s in services if not s.get("technologies")]
        if no_tech and len(services) > 0:
            analysis["suggested_actions"].append({
                "action": "generate_script",
                "script_type": "tech_fingerprint",
                "targets": [n.get("host") for n in no_tech[:10]],
                "reason": "Deeper tech fingerprinting needed"
            })

        analysis["completeness_score"] = 1.0 - (len(failed_probes) / max(len(services), 1))
        return analysis

    async def _analyze_dns_result(self, result: Any, context: Optional[Dict]) -> Dict:
        """Analyze DNS resolution results."""
        analysis = {
            "valid": True,
            "completeness_score": 0.7,
            "issues": [],
            "enrichment_opportunities": [],
            "suggested_actions": []
        }

        records = result if isinstance(result, list) else result.get("records", []) if isinstance(result, dict) else []

        # Check for NXDOMAIN or resolution failures
        failed = [r for r in records if r.get("error") or not r.get("ip")]
        if failed:
            analysis["issues"].append({
                "type": "resolution_failures",
                "severity": "info",
                "message": f"{len(failed)} domains failed to resolve"
            })

        # Check for interesting DNS patterns
        unique_ips = set()
        for r in records:
            if r.get("ip"):
                unique_ips.add(r.get("ip"))

        if len(unique_ips) < len(records) * 0.5:
            analysis["enrichment_opportunities"].append({
                "type": "shared_hosting_analysis",
                "reason": "Many domains share IPs - investigate hosting infrastructure"
            })

        return analysis

    async def _analyze_wayback_result(self, result: Any, context: Optional[Dict]) -> Dict:
        """Analyze Wayback Machine historical URL results."""
        analysis = {
            "valid": True,
            "completeness_score": 0.6,
            "issues": [],
            "enrichment_opportunities": [],
            "suggested_actions": []
        }

        urls = result if isinstance(result, list) else result.get("urls", []) if isinstance(result, dict) else []

        if len(urls) == 0:
            analysis["completeness_score"] = 0.0
            analysis["issues"].append({
                "type": "no_historical_data",
                "severity": "info",
                "message": "No historical URLs found"
            })
        else:
            # Look for interesting patterns
            api_endpoints = [u for u in urls if "/api/" in u.lower() or "api." in u.lower()]
            admin_paths = [u for u in urls if "/admin" in u.lower() or "/dashboard" in u.lower()]
            config_files = [u for u in urls if any(ext in u.lower() for ext in [".json", ".xml", ".yml", ".yaml", ".env", ".config"])]

            if api_endpoints:
                analysis["enrichment_opportunities"].append({
                    "type": "api_discovery",
                    "targets": api_endpoints[:20],
                    "reason": "Historical API endpoints found - check if still active"
                })

            if admin_paths:
                analysis["enrichment_opportunities"].append({
                    "type": "admin_discovery",
                    "targets": admin_paths[:10],
                    "reason": "Admin paths found historically - high value targets"
                })

            if config_files:
                analysis["enrichment_opportunities"].append({
                    "type": "config_exposure",
                    "targets": config_files[:10],
                    "reason": "Config files in history - check for exposure"
                })
                analysis["suggested_actions"].append({
                    "action": "generate_script",
                    "script_type": "config_checker",
                    "targets": config_files[:10],
                    "reason": "Check if config files are still accessible"
                })

        return analysis

    def _generic_analysis(self, tool_name: str, result: Any) -> Dict:
        """Generic analysis for unknown tools."""
        return {
            "valid": result is not None,
            "completeness_score": 0.5 if result else 0.0,
            "issues": [] if result else [{"type": "null_result", "severity": "warning", "message": f"{tool_name} returned no data"}],
            "enrichment_opportunities": [],
            "suggested_actions": []
        }


class ScriptGenerator:
    """
    Generates Python scripts for investigation and enrichment tasks.
    Uses LLM to create contextual scripts based on findings.
    """

    def __init__(self, ollama_url: str = "http://host.docker.internal:11434"):
        self.ollama_url = ollama_url
        self.model = "qwen2.5-coder:7b"

        # Pre-defined script templates for common tasks
        self.templates = {
            "dns_bruteforce": self._template_dns_bruteforce,
            "tech_fingerprint": self._template_tech_fingerprint,
            "config_checker": self._template_config_checker,
            "port_check": self._template_port_check,
            "header_analysis": self._template_header_analysis,
            "certificate_check": self._template_certificate_check,
        }

    async def generate_script(
        self,
        script_type: str,
        targets: List[str],
        context: Optional[Dict] = None,
        use_llm: bool = False
    ) -> Tuple[str, Dict]:
        """
        Generate a Python script for the given task.

        Returns:
            Tuple of (script_code, metadata)
        """
        metadata = {
            "script_type": script_type,
            "targets_count": len(targets),
            "generated_at": time.time(),
            "method": "template"
        }

        # Use template if available
        if script_type in self.templates:
            script = self.templates[script_type](targets, context)
            return script, metadata

        # Fall back to LLM generation for unknown types
        if use_llm:
            script = await self._generate_with_llm(script_type, targets, context)
            metadata["method"] = "llm"
            return script, metadata

        # Default: return a safe placeholder
        script = self._template_placeholder(script_type, targets)
        metadata["method"] = "placeholder"
        return script, metadata

    def _template_dns_bruteforce(self, targets: List[str], context: Optional[Dict]) -> str:
        """Generate DNS bruteforce script."""
        domain = targets[0] if targets else context.get("target_domain", "example.com")
        return f'''
# DNS Subdomain Bruteforce Script
# Generated by ReflectionAgent for domain: {domain}

import json
import socket

WORDLIST = [
    "www", "mail", "ftp", "admin", "blog", "dev", "staging", "api", "app",
    "portal", "secure", "vpn", "remote", "webmail", "m", "mobile", "test",
    "beta", "demo", "shop", "store", "support", "help", "docs", "wiki"
]

def resolve_subdomain(subdomain, domain):
    """Try to resolve a subdomain."""
    fqdn = f"{{subdomain}}.{{domain}}"
    try:
        ip = socket.gethostbyname(fqdn)
        return {{"subdomain": fqdn, "ip": ip, "status": "resolved"}}
    except socket.gaierror:
        return None

def main():
    domain = "{domain}"
    results = []

    for word in WORDLIST:
        result = resolve_subdomain(word, domain)
        if result:
            results.append(result)

    print(json.dumps({{"domain": domain, "discovered": results, "count": len(results)}}))

if __name__ == "__main__":
    main()
'''

    def _template_tech_fingerprint(self, targets: List[str], context: Optional[Dict]) -> str:
        """Generate technology fingerprinting script."""
        targets_json = json.dumps(targets[:10])
        return f'''
# Technology Fingerprinting Script
# Generated by ReflectionAgent

import json
import urllib.request
import re

TARGETS = {targets_json}

SIGNATURES = {{
    "WordPress": ["/wp-content/", "/wp-includes/", "wp-json"],
    "Drupal": ["/sites/default/", "Drupal.settings"],
    "Joomla": ["/administrator/", "/components/"],
    "Laravel": ["laravel_session", "XSRF-TOKEN"],
    "Django": ["csrftoken", "django"],
    "Rails": ["_session_id", "X-Request-Id"],
    "ASP.NET": ["__VIEWSTATE", "ASP.NET_SessionId"],
    "PHP": ["PHPSESSID", ".php"],
    "Node.js": ["X-Powered-By: Express", "connect.sid"],
}}

def fingerprint(url):
    """Fingerprint a single URL."""
    detected = []
    try:
        req = urllib.request.Request(url, headers={{"User-Agent": "Mozilla/5.0"}})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            headers = dict(resp.headers)

            for tech, sigs in SIGNATURES.items():
                for sig in sigs:
                    if sig in body or sig in str(headers):
                        detected.append(tech)
                        break
    except Exception as e:
        return {{"url": url, "error": str(e), "technologies": []}}

    return {{"url": url, "technologies": list(set(detected))}}

def main():
    results = []
    for target in TARGETS:
        url = target if target.startswith("http") else f"https://{{target}}"
        results.append(fingerprint(url))

    print(json.dumps({{"results": results, "count": len(results)}}))

if __name__ == "__main__":
    main()
'''

    def _template_config_checker(self, targets: List[str], context: Optional[Dict]) -> str:
        """Generate config file exposure checker."""
        targets_json = json.dumps(targets[:10])
        return f'''
# Configuration File Exposure Checker
# Generated by ReflectionAgent

import json
import urllib.request
import urllib.error

TARGETS = {targets_json}

CONFIG_PATHS = [
    "/.env", "/config.json", "/config.yml", "/settings.json",
    "/wp-config.php.bak", "/.git/config", "/database.yml",
    "/application.properties", "/appsettings.json"
]

def check_config(base_url, path):
    """Check if a config file is accessible."""
    url = base_url.rstrip("/") + path
    try:
        req = urllib.request.Request(url, headers={{"User-Agent": "Mozilla/5.0"}})
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.getcode()
            size = len(resp.read())
            if status == 200 and size > 0:
                return {{"url": url, "status": status, "size": size, "exposed": True}}
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return {{"url": url, "status": e.code, "exposed": False}}
    except Exception:
        pass
    return None

def main():
    findings = []
    for target in TARGETS:
        base = target if target.startswith("http") else f"https://{{target}}"
        for path in CONFIG_PATHS:
            result = check_config(base, path)
            if result and result.get("exposed"):
                findings.append(result)

    print(json.dumps({{"findings": findings, "exposed_count": len(findings)}}))

if __name__ == "__main__":
    main()
'''

    def _template_port_check(self, targets: List[str], context: Optional[Dict]) -> str:
        """Generate port scanning script."""
        targets_json = json.dumps(targets[:5])
        return f'''
# Port Check Script (Common Ports)
# Generated by ReflectionAgent

import json
import socket

TARGETS = {targets_json}
PORTS = [21, 22, 23, 25, 53, 80, 443, 445, 3306, 3389, 5432, 6379, 8080, 8443, 9200]

def check_port(host, port, timeout=2):
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def scan_host(host):
    """Scan common ports on a host."""
    # Extract hostname from URL if needed
    if "://" in host:
        host = host.split("://")[1].split("/")[0]

    open_ports = []
    for port in PORTS:
        if check_port(host, port):
            open_ports.append(port)

    return {{"host": host, "open_ports": open_ports}}

def main():
    results = []
    for target in TARGETS:
        results.append(scan_host(target))

    print(json.dumps({{"results": results}}))

if __name__ == "__main__":
    main()
'''

    def _template_header_analysis(self, targets: List[str], context: Optional[Dict]) -> str:
        """Generate HTTP header security analysis script."""
        targets_json = json.dumps(targets[:10])
        return f'''
# HTTP Security Header Analysis
# Generated by ReflectionAgent

import json
import urllib.request

TARGETS = {targets_json}

SECURITY_HEADERS = [
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "X-XSS-Protection",
    "Referrer-Policy",
    "Permissions-Policy"
]

def analyze_headers(url):
    """Analyze security headers of a URL."""
    try:
        req = urllib.request.Request(url, headers={{"User-Agent": "Mozilla/5.0"}})
        with urllib.request.urlopen(req, timeout=10) as resp:
            headers = dict(resp.headers)

            present = []
            missing = []
            for h in SECURITY_HEADERS:
                if h in headers or h.lower() in [k.lower() for k in headers]:
                    present.append(h)
                else:
                    missing.append(h)

            return {{
                "url": url,
                "present": present,
                "missing": missing,
                "score": len(present) / len(SECURITY_HEADERS),
                "server": headers.get("Server", "Unknown")
            }}
    except Exception as e:
        return {{"url": url, "error": str(e)}}

def main():
    results = []
    for target in TARGETS:
        url = target if target.startswith("http") else f"https://{{target}}"
        results.append(analyze_headers(url))

    print(json.dumps({{"results": results}}))

if __name__ == "__main__":
    main()
'''

    def _template_certificate_check(self, targets: List[str], context: Optional[Dict]) -> str:
        """Generate SSL certificate analysis script."""
        targets_json = json.dumps(targets[:10])
        return f'''
# SSL Certificate Analysis Script
# Generated by ReflectionAgent

import json
import ssl
import socket
from datetime import datetime

TARGETS = {targets_json}

def get_cert_info(hostname, port=443):
    """Get SSL certificate information."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

                # Parse dates
                not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
                not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")

                # Extract SANs
                sans = []
                for entry in cert.get("subjectAltName", []):
                    if entry[0] == "DNS":
                        sans.append(entry[1])

                return {{
                    "hostname": hostname,
                    "issuer": dict(x[0] for x in cert.get("issuer", [])),
                    "subject": dict(x[0] for x in cert.get("subject", [])),
                    "valid_from": not_before.isoformat(),
                    "valid_until": not_after.isoformat(),
                    "days_remaining": (not_after - datetime.now()).days,
                    "san_domains": sans
                }}
    except Exception as e:
        return {{"hostname": hostname, "error": str(e)}}

def main():
    results = []
    for target in TARGETS:
        # Extract hostname
        host = target
        if "://" in host:
            host = host.split("://")[1].split("/")[0]

        results.append(get_cert_info(host))

    # Find additional domains from SANs
    all_sans = set()
    for r in results:
        for san in r.get("san_domains", []):
            all_sans.add(san)

    print(json.dumps({{
        "results": results,
        "discovered_domains": list(all_sans)
    }}))

if __name__ == "__main__":
    main()
'''

    def _template_placeholder(self, script_type: str, targets: List[str]) -> str:
        """Placeholder for unknown script types."""
        return f'''
# Placeholder Script for: {script_type}
# Generated by ReflectionAgent
# Targets: {len(targets)}

import json

def main():
    print(json.dumps({{"status": "placeholder", "script_type": "{script_type}", "message": "Custom implementation needed"}}))

if __name__ == "__main__":
    main()
'''

    async def _generate_with_llm(self, script_type: str, targets: List[str], context: Optional[Dict]) -> str:
        """Generate script using LLM for custom tasks."""
        prompt = f"""Generate a Python script for the following security reconnaissance task:

Task Type: {script_type}
Targets: {json.dumps(targets[:5])}
Context: {json.dumps(context or {})}

Requirements:
1. Output must be valid JSON to stdout
2. Handle errors gracefully
3. Use only standard library (no pip packages)
4. Include timeout handling
5. Be safe and non-destructive

Return ONLY the Python code, no explanations."""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", self._template_placeholder(script_type, targets))
        except Exception:
            pass

        return self._template_placeholder(script_type, targets)


class ReflectionLoop:
    """
    Orchestrates the reflection process:
    1. Analyze tool results
    2. Identify gaps and opportunities
    3. Generate investigation scripts
    4. Execute scripts and collect results
    5. Enrich graph with findings
    """

    def __init__(
        self,
        graph_service_url: str = "http://graph-service:8001",
        ollama_url: str = "http://host.docker.internal:11434",
        max_iterations: int = 3,
        script_executor=None
    ):
        self.graph_service_url = graph_service_url
        self.analyzer = ResultAnalyzer(ollama_url=ollama_url)
        self.script_generator = ScriptGenerator(ollama_url=ollama_url)
        self.script_executor = script_executor
        self.max_iterations = max_iterations
        self.tasks: List[ReflectionTask] = []
        self.completed_tasks: List[ReflectionTask] = []

    async def reflect_on_tool_result(
        self,
        tool_name: str,
        result: Any,
        mission_id: str,
        context: Optional[Dict] = None
    ) -> ReflectionResult:
        """
        Main entry point: analyze a tool result and perform enrichment.
        """
        task_id = f"reflect-{tool_name}-{int(time.time())}"

        # Step 1: Analyze the result
        analysis = await self.analyzer.analyze_tool_result(
            tool_name, result, context=context
        )

        reflection_result = ReflectionResult(
            task_id=task_id,
            success=analysis["valid"],
            confidence=analysis["completeness_score"]
        )

        # Step 2: Process issues
        for issue in analysis.get("issues", []):
            reflection_result.findings.append({
                "type": "issue",
                "tool": tool_name,
                "issue": issue
            })

        # Step 3: Process enrichment opportunities
        for opportunity in analysis.get("enrichment_opportunities", []):
            reflection_result.findings.append({
                "type": "enrichment_opportunity",
                "tool": tool_name,
                "opportunity": opportunity
            })

        # Step 4: Generate and execute scripts if needed
        for action in analysis.get("suggested_actions", []):
            if action.get("action") == "generate_script" and self.script_executor:
                script_type = action.get("script_type", "unknown")
                targets = action.get("targets", [])

                # Generate script
                script_code, metadata = await self.script_generator.generate_script(
                    script_type, targets, context
                )
                reflection_result.scripts_generated.append(script_code[:200] + "...")

                # Execute script
                try:
                    exec_result = self.script_executor._run(script_code, timeout=30)
                    exec_data = json.loads(exec_result)

                    if exec_data.get("status") == "success":
                        # Parse stdout as JSON
                        try:
                            script_output = json.loads(exec_data.get("stdout", "{}"))
                            reflection_result.enrichments.append({
                                "source": f"script:{script_type}",
                                "data": script_output
                            })
                        except json.JSONDecodeError:
                            reflection_result.enrichments.append({
                                "source": f"script:{script_type}",
                                "raw_output": exec_data.get("stdout", "")
                            })
                    else:
                        reflection_result.errors.append(
                            f"Script {script_type} failed: {exec_data.get('error', 'Unknown')}"
                        )
                except Exception as e:
                    reflection_result.errors.append(f"Script execution error: {str(e)}")

        return reflection_result

    async def enrich_graph_with_findings(
        self,
        mission_id: str,
        findings: List[Dict]
    ) -> Dict[str, int]:
        """
        Push enrichment findings to the graph service.
        """
        stats = {"nodes_added": 0, "edges_added": 0, "nodes_updated": 0}

        async with httpx.AsyncClient(timeout=10.0) as client:
            for finding in findings:
                if finding.get("type") == "enrichment_opportunity":
                    continue  # These are suggestions, not data

                source = finding.get("source", "reflection")
                data = finding.get("data", {})

                # Handle different enrichment data types
                if "discovered" in data:  # DNS bruteforce results
                    for item in data.get("discovered", []):
                        try:
                            await client.post(
                                f"{self.graph_service_url}/api/v1/nodes",
                                json={
                                    "id": f"subdomain:{item['subdomain']}",
                                    "type": "SUBDOMAIN",
                                    "mission_id": mission_id,
                                    "properties": {
                                        "name": item["subdomain"],
                                        "ip": item.get("ip"),
                                        "source": source
                                    }
                                }
                            )
                            stats["nodes_added"] += 1
                        except Exception:
                            pass

                elif "results" in data:  # Generic results array
                    for item in data.get("results", []):
                        if item.get("technologies"):
                            # Tech fingerprint results - update existing nodes
                            try:
                                node_id = f"http_service:{item.get('url', item.get('host'))}"
                                await client.patch(
                                    f"{self.graph_service_url}/api/v1/nodes/{node_id}",
                                    json={
                                        "properties": {
                                            "technologies_enriched": item["technologies"],
                                            "enriched_by": source
                                        }
                                    }
                                )
                                stats["nodes_updated"] += 1
                            except Exception:
                                pass

                elif "findings" in data:  # Config checker results
                    for item in data.get("findings", []):
                        if item.get("exposed"):
                            try:
                                await client.post(
                                    f"{self.graph_service_url}/api/v1/nodes",
                                    json={
                                        "id": f"exposure:{item['url']}",
                                        "type": "EXPOSURE",
                                        "mission_id": mission_id,
                                        "properties": {
                                            "url": item["url"],
                                            "type": "config_file",
                                            "source": source,
                                            "severity": "high"
                                        }
                                    }
                                )
                                stats["nodes_added"] += 1
                            except Exception:
                                pass

        return stats


# Convenience function for integration
async def reflect_and_enrich(
    tool_name: str,
    result: Any,
    mission_id: str,
    context: Optional[Dict] = None,
    script_executor=None,
    graph_service_url: str = "http://graph-service:8001"
) -> Dict[str, Any]:
    """
    High-level function to analyze tool results and enrich the graph.

    Returns summary of reflection activities.
    """
    loop = ReflectionLoop(
        graph_service_url=graph_service_url,
        script_executor=script_executor
    )

    # Perform reflection
    result = await loop.reflect_on_tool_result(
        tool_name, result, mission_id, context
    )

    # Enrich graph if we have findings
    enrichment_stats = {"nodes_added": 0, "edges_added": 0, "nodes_updated": 0}
    if result.enrichments:
        enrichment_stats = await loop.enrich_graph_with_findings(
            mission_id, result.enrichments
        )

    return {
        "task_id": result.task_id,
        "success": result.success,
        "confidence": result.confidence,
        "findings_count": len(result.findings),
        "enrichments_count": len(result.enrichments),
        "scripts_executed": len(result.scripts_generated),
        "errors": result.errors,
        "graph_updates": enrichment_stats
    }
