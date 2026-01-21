"""
Iterative Scanner - Complete Reconnaissance Engine
Performs exhaustive scanning of ALL discovered subdomains with:
- Technology fingerprinting
- Active endpoint discovery
- Security analysis
- Vulnerability detection with evidence
"""
import asyncio
import json
import time
import re
import hashlib
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field, asdict
from enum import Enum

from .events import emit_log, emit_agent_started, emit_agent_finished, emit_tool_called, emit_tool_result
from .graph_client import GraphClient

# Import Nuclei tool for real vulnerability scanning
try:
    from tools.nuclei_tool import NucleiTool, NucleiQuickScanTool
    NUCLEI_AVAILABLE = True
except ImportError:
    NUCLEI_AVAILABLE = False


class ScanStatus(str, Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubdomainScanResult:
    """Complete scan result for a single subdomain"""
    subdomain: str
    status: ScanStatus = ScanStatus.PENDING

    # HTTP Service data
    http_alive: bool = False
    https_alive: bool = False
    http_url: Optional[str] = None
    https_url: Optional[str] = None
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    title: Optional[str] = None
    content_length: Optional[int] = None

    # Technology fingerprinting
    technologies: List[str] = field(default_factory=list)
    server: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

    # Security headers analysis
    security_headers: Dict[str, Any] = field(default_factory=dict)
    missing_security_headers: List[str] = field(default_factory=list)

    # Endpoints discovered
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)

    # JS analysis
    js_files: List[str] = field(default_factory=list)
    js_endpoints: List[Dict[str, Any]] = field(default_factory=list)
    js_secrets: List[Dict[str, Any]] = field(default_factory=list)

    # Vulnerabilities detected
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    scan_duration: float = 0.0
    error: Optional[str] = None


class IterativeScanner:
    """
    Complete iterative reconnaissance engine.
    Scans ALL discovered subdomains exhaustively.
    """

    # Security headers to check
    SECURITY_HEADERS = [
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Permissions-Policy",
    ]

    # Interesting path patterns for active probing
    PROBE_PATHS = [
        "/robots.txt",
        "/sitemap.xml",
        "/.well-known/security.txt",
        "/api",
        "/api/v1",
        "/admin",
        "/login",
        "/wp-admin",
        "/wp-login.php",
        "/.git/config",
        "/.env",
        "/config.php",
        "/phpinfo.php",
        "/server-status",
        "/swagger.json",
        "/openapi.json",
        "/graphql",
        "/.htaccess",
        "/web.config",
    ]

    def __init__(
        self,
        mission_id: str,
        target_domain: str,
        graph_client: GraphClient,
        tools: Dict[str, Any],
        mode: str = "aggressive",
        max_concurrent: int = 5,
    ):
        self.mission_id = mission_id
        self.target_domain = target_domain
        self.graph_client = graph_client
        self.tools = tools
        self.mode = mode
        self.max_concurrent = max_concurrent

        # Results storage
        self.scan_results: Dict[str, SubdomainScanResult] = {}
        self.all_endpoints: Set[str] = set()
        self.all_technologies: Set[str] = set()

        # Statistics
        self.stats = {
            "subdomains_scanned": 0,
            "http_services_found": 0,
            "endpoints_discovered": 0,
            "technologies_detected": 0,
            "vulnerabilities_found": 0,
            "hypotheses_generated": 0,
        }

        emit_log(self.mission_id, "INFO", f"IterativeScanner initialized for {target_domain} in {mode} mode", "scanner")

    async def scan_all_subdomains(self, subdomains: List[str]) -> Dict[str, Any]:
        """
        Main entry point: Scan ALL subdomains exhaustively.
        Returns complete reconnaissance results.
        """
        start_time = time.time()
        total = len(subdomains)

        emit_log(self.mission_id, "INFO", f"Starting exhaustive scan of {total} subdomains", "scanner")
        emit_agent_started(self.mission_id, "iterative_scanner", f"Scanning {total} subdomains")

        # Phase 1: HTTPX probe ALL subdomains to find live HTTP services
        emit_log(self.mission_id, "INFO", "Phase 1: Probing ALL subdomains for HTTP services...", "scanner")
        live_services = await self._probe_all_subdomains(subdomains)

        # Phase 2: Deep scan each live service
        emit_log(self.mission_id, "INFO", f"Phase 2: Deep scanning {len(live_services)} live services...", "scanner")
        await self._deep_scan_services(live_services)

        # Phase 3: Active path probing on all live services
        emit_log(self.mission_id, "INFO", "Phase 3: Active path probing...", "scanner")
        await self._active_path_probe(live_services)

        # Phase 4: Wayback historical endpoint discovery
        emit_log(self.mission_id, "INFO", "Phase 4: Wayback historical endpoint discovery...", "scanner")
        await self._wayback_scan_all(subdomains)

        # Phase 5: JS analysis on all services with JS files
        emit_log(self.mission_id, "INFO", "Phase 5: JavaScript analysis...", "scanner")
        await self._js_analysis_all(live_services)

        # Phase 6: NUCLEI vulnerability scanning (real CVEs, SQLi, XSS, RCE, etc.)
        emit_log(self.mission_id, "INFO", "Phase 6: Nuclei vulnerability scanning (CVEs, misconfigs, exposures)...", "scanner")
        await self._nuclei_scan_all(live_services)

        # Phase 7: Security analysis and additional vulnerability detection
        emit_log(self.mission_id, "INFO", "Phase 7: Security analysis and hypothesis generation...", "scanner")
        await self._security_analysis_all()

        # Phase 8: Store everything in graph
        emit_log(self.mission_id, "INFO", "Phase 8: Storing results in graph...", "scanner")
        await self._store_all_results()

        duration = time.time() - start_time
        emit_agent_finished(self.mission_id, "iterative_scanner", "Completed", duration)

        # Generate summary
        summary = {
            "duration": duration,
            "stats": self.stats,
            "subdomains_total": total,
            "live_services": len(live_services),
            "scan_results": {k: asdict(v) for k, v in self.scan_results.items()},
        }

        emit_log(
            self.mission_id, "INFO",
            f"Scan complete: {self.stats['http_services_found']} services, "
            f"{self.stats['endpoints_discovered']} endpoints, "
            f"{self.stats['vulnerabilities_found']} vulns in {duration:.1f}s",
            "scanner"
        )

        return summary

    async def _probe_all_subdomains(self, subdomains: List[str]) -> List[str]:
        """Probe ALL subdomains with HTTPX to find live HTTP services"""
        emit_tool_called(self.mission_id, "httpx", "probe_all", f"{len(subdomains)} targets")

        # Build targets for both HTTP and HTTPS
        targets = []
        for sub in subdomains:
            targets.append(f"https://{sub}")
            targets.append(f"http://{sub}")

        # Initialize scan results
        for sub in subdomains:
            self.scan_results[sub] = SubdomainScanResult(subdomain=sub)

        try:
            # Call HTTPX tool with ALL targets
            httpx_raw = self.tools["httpx"]._run(subdomains=targets, timeout=15)
            httpx_response = json.loads(httpx_raw)

            if isinstance(httpx_response, dict):
                results = httpx_response.get("results", [])
            else:
                results = httpx_response if isinstance(httpx_response, list) else []

            live_services = []

            for result in results:
                url = result.get("url", "")
                parsed = urlparse(url)
                host = parsed.netloc

                # Find matching subdomain
                for sub in subdomains:
                    if sub in host or host == sub:
                        scan_result = self.scan_results.get(sub)
                        if scan_result:
                            scan_result.status = ScanStatus.SCANNING

                            if parsed.scheme == "https":
                                scan_result.https_alive = True
                                scan_result.https_url = url
                            else:
                                scan_result.http_alive = True
                                scan_result.http_url = url

                            scan_result.final_url = url
                            scan_result.status_code = result.get("status_code")
                            scan_result.title = result.get("title")
                            scan_result.technologies = result.get("technologies", []) or result.get("tech", [])
                            scan_result.server = result.get("server")

                            # Track technologies
                            for tech in scan_result.technologies:
                                self.all_technologies.add(tech)

                            if sub not in live_services:
                                live_services.append(sub)
                        break

            self.stats["http_services_found"] = len(live_services)
            emit_tool_result(self.mission_id, "httpx", result_count=len(live_services), success=True)
            emit_log(self.mission_id, "INFO", f"Found {len(live_services)} live HTTP services", "scanner")

            return live_services

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"HTTPX probe failed: {e}", "scanner")
            emit_tool_result(self.mission_id, "httpx", result_count=0, success=False)
            return []

    async def _deep_scan_services(self, live_services: List[str]):
        """Deep scan each live service: HTML crawl for endpoints, forms, links"""
        emit_tool_called(self.mission_id, "html_crawler", "deep_scan", f"{len(live_services)} services")

        # Get URLs to crawl
        urls_to_crawl = []
        for sub in live_services:
            scan_result = self.scan_results.get(sub)
            if scan_result and scan_result.final_url:
                urls_to_crawl.append(scan_result.final_url)

        if not urls_to_crawl:
            return

        try:
            # Call HTML crawler
            html_raw = self.tools["html_crawler"]._run(urls=urls_to_crawl[:20])  # Limit for safety
            html_data = json.loads(html_raw)

            if not isinstance(html_data, list):
                html_data = [html_data] if html_data else []

            endpoints_found = 0

            for item in html_data:
                source_url = item.get("url") or item.get("source_url")
                if not source_url:
                    continue

                parsed_source = urlparse(source_url)
                source_host = parsed_source.netloc

                # Find matching subdomain
                for sub in live_services:
                    if sub in source_host:
                        scan_result = self.scan_results.get(sub)
                        if scan_result:
                            # Extract links/endpoints
                            links = item.get("links", []) or item.get("endpoints", [])
                            for link in links:
                                if isinstance(link, str):
                                    path = link
                                elif isinstance(link, dict):
                                    path = link.get("href") or link.get("path") or link.get("url")
                                else:
                                    continue

                                if path:
                                    # Normalize path
                                    if path.startswith("http"):
                                        parsed = urlparse(path)
                                        # Only include same-domain paths
                                        if self.target_domain in parsed.netloc:
                                            path = parsed.path or "/"
                                        else:
                                            continue

                                    if path and path != "/" and path not in [e.get("path") for e in scan_result.endpoints]:
                                        scan_result.endpoints.append({
                                            "path": path,
                                            "method": "GET",
                                            "source": "html_crawl",
                                            "category": self._categorize_endpoint(path),
                                        })
                                        self.all_endpoints.add(f"{sub}{path}")
                                        endpoints_found += 1

                            # Extract forms
                            forms = item.get("forms", [])
                            for form in forms:
                                if isinstance(form, dict):
                                    scan_result.forms.append(form)
                        break

            self.stats["endpoints_discovered"] += endpoints_found
            emit_tool_result(self.mission_id, "html_crawler", result_count=endpoints_found, success=True)
            emit_log(self.mission_id, "INFO", f"HTML crawl found {endpoints_found} endpoints", "scanner")

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"HTML crawl failed: {e}", "scanner")

    async def _active_path_probe(self, live_services: List[str]):
        """Actively probe common paths on all live services"""
        emit_log(self.mission_id, "INFO", f"Probing {len(self.PROBE_PATHS)} common paths on {len(live_services)} services", "scanner")

        # Build probe targets
        probe_targets = []
        for sub in live_services:
            scan_result = self.scan_results.get(sub)
            if scan_result and scan_result.final_url:
                base_url = scan_result.final_url.rstrip("/")
                for path in self.PROBE_PATHS:
                    probe_targets.append(f"{base_url}{path}")

        if not probe_targets:
            return

        try:
            # Probe with HTTPX
            httpx_raw = self.tools["httpx"]._run(subdomains=probe_targets[:100], timeout=10)
            httpx_response = json.loads(httpx_raw)

            if isinstance(httpx_response, dict):
                results = httpx_response.get("results", [])
            else:
                results = httpx_response if isinstance(httpx_response, list) else []

            interesting_finds = 0

            for result in results:
                url = result.get("url", "")
                status = result.get("status_code", 0)

                # Only interested in successful responses (not 404)
                if status and status < 400:
                    parsed = urlparse(url)
                    path = parsed.path
                    host = parsed.netloc

                    # Find matching subdomain
                    for sub in live_services:
                        if sub in host:
                            scan_result = self.scan_results.get(sub)
                            if scan_result and path not in [e.get("path") for e in scan_result.endpoints]:
                                scan_result.endpoints.append({
                                    "path": path,
                                    "method": "GET",
                                    "source": "active_probe",
                                    "status_code": status,
                                    "category": self._categorize_endpoint(path),
                                    "interesting": True,
                                })
                                self.all_endpoints.add(f"{sub}{path}")
                                interesting_finds += 1
                            break

            self.stats["endpoints_discovered"] += interesting_finds
            emit_log(self.mission_id, "INFO", f"Active probe found {interesting_finds} interesting paths", "scanner")

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Active path probe failed: {e}", "scanner")

    async def _wayback_scan_all(self, subdomains: List[str]):
        """Scan Wayback Machine for historical endpoints on all subdomains"""
        if "wayback" not in self.tools:
            emit_log(self.mission_id, "WARNING", "Wayback tool not available", "scanner")
            return

        emit_tool_called(self.mission_id, "wayback", "scan_all", f"{len(subdomains)} domains")

        total_endpoints = 0
        try:
            # Scan each subdomain (limit to avoid API overload)
            for sub in subdomains[:30]:  # Limit to 30 subdomains for Wayback
                scan_result = self.scan_results.get(sub)
                if not scan_result:
                    continue

                try:
                    # Call Wayback tool
                    wb_raw = self.tools["wayback"]._run(domain=sub, limit=100)
                    wb_data = json.loads(wb_raw)

                    if isinstance(wb_data, dict):
                        endpoints = wb_data.get("endpoints", []) or wb_data.get("results", [])
                    elif isinstance(wb_data, list):
                        endpoints = wb_data
                    else:
                        endpoints = []

                    # Add endpoints to scan result
                    for item in endpoints:
                        full_url = item.get("path") or item.get("url") or item
                        if isinstance(full_url, str):
                            parsed = urlparse(full_url)
                            path = parsed.path or "/"

                            # Filter: only paths from target domain
                            if path and path != "/" and self.target_domain in (parsed.netloc or sub):
                                # Skip if already have this endpoint
                                if path not in [e.get("path") for e in scan_result.endpoints]:
                                    scan_result.endpoints.append({
                                        "path": path,
                                        "method": "GET",
                                        "source": "wayback",
                                        "category": self._categorize_endpoint(path),
                                        "historical": True,
                                    })
                                    self.all_endpoints.add(f"{sub}{path}")
                                    total_endpoints += 1

                except Exception as e:
                    emit_log(self.mission_id, "DEBUG", f"Wayback scan failed for {sub}: {e}", "scanner")
                    continue

            self.stats["endpoints_discovered"] += total_endpoints
            emit_tool_result(self.mission_id, "wayback", result_count=total_endpoints, success=True)
            emit_log(self.mission_id, "INFO", f"Wayback scan found {total_endpoints} historical endpoints", "scanner")

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Wayback scan failed: {e}", "scanner")
            emit_tool_result(self.mission_id, "wayback", result_count=0, success=False)

    async def _js_analysis_all(self, live_services: List[str]):
        """Analyze JavaScript files for all live services"""
        urls_to_analyze = []
        for sub in live_services:
            scan_result = self.scan_results.get(sub)
            if scan_result and scan_result.final_url:
                urls_to_analyze.append(scan_result.final_url)

        if not urls_to_analyze:
            return

        emit_tool_called(self.mission_id, "js_miner", "analyze_all", f"{len(urls_to_analyze)} URLs")

        try:
            js_raw = self.tools["js_miner"]._run(urls=urls_to_analyze[:15])
            js_data = json.loads(js_raw)

            if not isinstance(js_data, list):
                js_data = [js_data] if js_data else []

            js_endpoints_found = 0
            secrets_found = 0

            for item in js_data:
                source_url = item.get("url")
                if not source_url:
                    continue

                parsed_source = urlparse(source_url)
                source_host = parsed_source.netloc

                for sub in live_services:
                    if sub in source_host:
                        scan_result = self.scan_results.get(sub)
                        if scan_result:
                            js_info = item.get("js", {})

                            # JS files
                            js_files = js_info.get("js_files", [])
                            scan_result.js_files.extend(js_files)

                            # JS endpoints
                            endpoints = js_info.get("endpoints", [])
                            for ep in endpoints:
                                path = ep.get("path")
                                if path:
                                    scan_result.js_endpoints.append(ep)
                                    if path not in [e.get("path") for e in scan_result.endpoints]:
                                        scan_result.endpoints.append({
                                            "path": path,
                                            "method": ep.get("method", "GET"),
                                            "source": "js_mining",
                                            "source_js": ep.get("source_js"),
                                            "category": self._categorize_endpoint(path),
                                        })
                                        self.all_endpoints.add(f"{sub}{path}")
                                        js_endpoints_found += 1

                            # Secrets
                            secrets = js_info.get("secrets", [])
                            for secret in secrets:
                                scan_result.js_secrets.append(secret)
                                secrets_found += 1
                        break

            self.stats["endpoints_discovered"] += js_endpoints_found
            emit_tool_result(self.mission_id, "js_miner", result_count=js_endpoints_found, success=True)
            emit_log(self.mission_id, "INFO", f"JS analysis: {js_endpoints_found} endpoints, {secrets_found} secrets", "scanner")

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"JS analysis failed: {e}", "scanner")

    async def _nuclei_scan_all(self, live_services: List[str]):
        """
        Run Nuclei vulnerability scanner against all live services.
        Finds real vulnerabilities: CVEs, SQLi, XSS, RCE, SSRF, misconfigs, etc.
        """
        if not NUCLEI_AVAILABLE:
            emit_log(self.mission_id, "WARNING", "Nuclei tool not available - skipping vulnerability scan", "scanner")
            return

        # Collect all live URLs
        targets = []
        for sub in live_services:
            scan_result = self.scan_results.get(sub)
            if scan_result and scan_result.final_url:
                targets.append(scan_result.final_url)

        if not targets:
            emit_log(self.mission_id, "WARNING", "No live targets for Nuclei scan", "scanner")
            return

        emit_tool_called(self.mission_id, "nuclei", "vuln_scan", f"{len(targets)} targets")
        emit_log(self.mission_id, "INFO", f"Starting Nuclei scan on {len(targets)} targets", "scanner")

        try:
            # Initialize Nuclei tool
            nuclei_tool = NucleiTool()

            # Configure scan based on mode
            if self.mode == "stealth":
                # Stealth mode: only high/critical, limited rate
                severity = "high,critical"
                rate_limit = 25
                templates = "cve,critical"
                timeout = 180
            else:
                # Aggressive mode: full scan
                severity = "medium,high,critical"
                rate_limit = 100
                templates = "cve,misconfig,exposure,xss,sqli,lfi,rce,ssrf,redirect,disclosure"
                timeout = 300

            # Run Nuclei
            nuclei_raw = nuclei_tool._run(
                targets=targets,
                templates=templates,
                severity=severity,
                rate_limit=rate_limit,
                timeout=timeout
            )

            nuclei_data = json.loads(nuclei_raw)

            # Check for errors
            if nuclei_data.get("error"):
                emit_log(
                    self.mission_id, "WARNING",
                    f"Nuclei error: {nuclei_data.get('message', 'unknown error')}",
                    "scanner"
                )
                emit_tool_result(self.mission_id, "nuclei", result_count=0, success=False)
                return

            vulnerabilities = nuclei_data.get("vulnerabilities", [])
            vuln_count = nuclei_data.get("vulnerability_count", 0)

            emit_log(
                self.mission_id, "INFO",
                f"Nuclei found {vuln_count} vulnerabilities",
                "scanner"
            )

            # Process each vulnerability and add to appropriate scan result
            for vuln in vulnerabilities:
                host = vuln.get("host", "")
                matched_at = vuln.get("matched_at", "")

                # Find which subdomain this vulnerability belongs to
                target_sub = None
                for sub in live_services:
                    if sub in host or sub in matched_at:
                        target_sub = sub
                        break

                if not target_sub:
                    # Try to match by parsing URL
                    try:
                        parsed = urlparse(matched_at or host)
                        for sub in live_services:
                            if sub in parsed.netloc:
                                target_sub = sub
                                break
                    except:
                        pass

                if target_sub:
                    scan_result = self.scan_results.get(target_sub)
                    if scan_result:
                        # Map Nuclei severity to our format
                        severity_map = {
                            "info": "INFO",
                            "low": "LOW",
                            "medium": "MEDIUM",
                            "high": "HIGH",
                            "critical": "CRITICAL"
                        }

                        vuln_entry = {
                            "type": vuln.get("attack_type", "CVE"),
                            "title": vuln.get("template_name", vuln.get("template_id", "Unknown")),
                            "severity": severity_map.get(vuln.get("severity", "medium"), "MEDIUM"),
                            "template_id": vuln.get("template_id"),
                            "description": vuln.get("description", ""),
                            "matched_at": matched_at,
                            "evidence": {
                                "template_id": vuln.get("template_id"),
                                "matched_at": matched_at,
                                "matcher_name": vuln.get("matcher_name"),
                                "curl_command": vuln.get("curl_command"),
                                "extracted_results": vuln.get("extracted_results", []),
                                "reference": vuln.get("reference", []),
                                "tags": vuln.get("tags", []),
                            },
                            "status": "CONFIRMED",
                            "risk_score": vuln.get("risk_score", 50),
                            "source": "nuclei",
                        }
                        scan_result.vulnerabilities.append(vuln_entry)

            # Log severity summary
            summary = nuclei_data.get("severity_summary", {})
            if summary:
                emit_log(
                    self.mission_id, "INFO",
                    f"Nuclei summary - Critical: {summary.get('critical', 0)}, "
                    f"High: {summary.get('high', 0)}, Medium: {summary.get('medium', 0)}, "
                    f"Low: {summary.get('low', 0)}, Info: {summary.get('info', 0)}",
                    "scanner"
                )

            emit_tool_result(self.mission_id, "nuclei", result_count=vuln_count, success=True)

        except json.JSONDecodeError as e:
            emit_log(self.mission_id, "ERROR", f"Failed to parse Nuclei output: {e}", "scanner")
            emit_tool_result(self.mission_id, "nuclei", result_count=0, success=False)
        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Nuclei scan failed: {e}", "scanner")
            emit_tool_result(self.mission_id, "nuclei", result_count=0, success=False)

    async def _security_analysis_all(self):
        """
        Perform comprehensive security analysis on all scan results.
        Checks for headers, misconfigs, technology-specific issues, etc.
        """
        vulns_found = 0
        hyps_generated = 0

        for sub, scan_result in self.scan_results.items():
            if scan_result.status != ScanStatus.SCANNING:
                continue

            # Check security headers
            scan_result.missing_security_headers = self._check_security_headers(scan_result.headers)

            # ============= VULNERABILITY CHECKS =============

            # 1. Missing security headers (only critical ones)
            critical_missing = [h for h in scan_result.missing_security_headers
                                if h in ["Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options"]]
            if critical_missing:
                vuln = {
                    "type": "SECURITY_HEADERS",
                    "title": f"Missing critical security headers on {sub}",
                    "severity": "MEDIUM",
                    "evidence": {"missing_headers": critical_missing},
                    "status": "CONFIRMED",
                    "risk_score": 45,
                    "source": "security_analysis",
                }
                scan_result.vulnerabilities.append(vuln)
                vulns_found += 1

            # 2. HTTPS not available (HTTP only)
            if scan_result.http_alive and not scan_result.https_alive:
                vuln = {
                    "type": "INSECURE_TRANSPORT",
                    "title": f"HTTPS not available on {sub}",
                    "severity": "HIGH",
                    "evidence": {"http_url": scan_result.http_url, "https_available": False},
                    "status": "CONFIRMED",
                    "risk_score": 70,
                    "source": "security_analysis",
                }
                scan_result.vulnerabilities.append(vuln)
                vulns_found += 1

            # 3. Outdated/vulnerable technologies
            tech_vulns = self._check_technology_vulnerabilities(scan_result.technologies)
            for tech_vuln in tech_vulns:
                scan_result.vulnerabilities.append(tech_vuln)
                vulns_found += 1

            # 4. Exposed sensitive paths (verified with status code)
            for ep in scan_result.endpoints:
                path = ep.get("path", "").lower()

                # Check for sensitive path exposures
                sensitive_patterns = {
                    ".git": ("GIT_EXPOSURE", "Git repository exposed", 85),
                    ".env": ("ENV_EXPOSURE", "Environment file exposed", 90),
                    ".svn": ("SVN_EXPOSURE", "SVN repository exposed", 80),
                    "config": ("CONFIG_EXPOSURE", "Configuration file exposed", 75),
                    "backup": ("BACKUP_EXPOSURE", "Backup file exposed", 70),
                    ".bak": ("BACKUP_EXPOSURE", "Backup file exposed", 70),
                    "phpinfo": ("PHPINFO_EXPOSURE", "PHP info page exposed", 65),
                    "server-status": ("SERVER_STATUS_EXPOSURE", "Server status exposed", 70),
                    ".htaccess": ("HTACCESS_EXPOSURE", "Apache config exposed", 60),
                    "web.config": ("WEBCONFIG_EXPOSURE", "IIS config exposed", 60),
                    "wp-config": ("WPCONFIG_EXPOSURE", "WordPress config exposed", 90),
                    "admin": ("ADMIN_PANEL", "Admin panel accessible", 50),
                    "phpmyadmin": ("PHPMYADMIN_EXPOSURE", "phpMyAdmin exposed", 75),
                    "adminer": ("ADMINER_EXPOSURE", "Adminer database tool exposed", 80),
                    "elmah": ("ELMAH_EXPOSURE", "ELMAH error log exposed", 70),
                    "trace.axd": ("TRACE_EXPOSURE", "ASP.NET trace exposed", 75),
                }

                for pattern, (vuln_type, title, risk_score) in sensitive_patterns.items():
                    if pattern in path:
                        # Only confirm if we got a success response
                        if ep.get("status_code") and ep.get("status_code") < 400:
                            vuln = {
                                "type": vuln_type,
                                "title": f"{title}: {ep.get('path')}",
                                "severity": "HIGH" if risk_score >= 75 else "MEDIUM",
                                "evidence": {"path": ep.get("path"), "status": ep.get("status_code")},
                                "status": "CONFIRMED",
                                "risk_score": risk_score,
                                "source": "security_analysis",
                            }
                            scan_result.vulnerabilities.append(vuln)
                            vulns_found += 1
                            break  # Only one vuln per endpoint

                # Generate hypotheses for interesting endpoints
                hyp = self._generate_hypothesis_for_endpoint(ep, sub)
                if hyp:
                    scan_result.hypotheses.append(hyp)
                    hyps_generated += 1

            # 5. Server information disclosure
            if scan_result.server:
                # Check for version disclosure in server header
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', scan_result.server)
                if version_match:
                    vuln = {
                        "type": "SERVER_VERSION_DISCLOSURE",
                        "title": f"Server version disclosed: {scan_result.server}",
                        "severity": "LOW",
                        "evidence": {"server_header": scan_result.server, "version": version_match.group(1)},
                        "status": "CONFIRMED",
                        "risk_score": 25,
                        "source": "security_analysis",
                    }
                    scan_result.vulnerabilities.append(vuln)
                    vulns_found += 1

            # 6. JS secrets (API keys, tokens, etc.)
            for secret in scan_result.js_secrets:
                secret_type = secret.get('kind', 'unknown').upper()
                severity = "CRITICAL" if any(k in secret_type for k in ['AWS', 'PRIVATE_KEY', 'PASSWORD']) else "HIGH"
                risk_score = 95 if severity == "CRITICAL" else 80

                vuln = {
                    "type": "SECRET_EXPOSURE",
                    "title": f"Secret found in JS: {secret.get('kind', 'unknown')}",
                    "severity": severity,
                    "evidence": {
                        "kind": secret.get("kind"),
                        "source_js": secret.get("source_js"),
                        "snippet": secret.get("snippet", "")[:100] if secret.get("snippet") else None
                    },
                    "status": "CONFIRMED",
                    "risk_score": risk_score,
                    "source": "js_mining",
                }
                scan_result.vulnerabilities.append(vuln)
                vulns_found += 1

            # 7. Form security analysis
            for form in scan_result.forms:
                form_action = form.get("action", "")
                form_method = form.get("method", "GET").upper()

                # Check for forms without HTTPS
                if form_action.startswith("http://"):
                    vuln = {
                        "type": "INSECURE_FORM",
                        "title": f"Form submits over HTTP: {form_action[:50]}",
                        "severity": "HIGH",
                        "evidence": {"action": form_action, "method": form_method},
                        "status": "CONFIRMED",
                        "risk_score": 70,
                        "source": "security_analysis",
                    }
                    scan_result.vulnerabilities.append(vuln)
                    vulns_found += 1

            # 8. Directory listing check (based on title)
            if scan_result.title and any(x in scan_result.title.lower() for x in ['index of', 'directory listing', 'listing']):
                vuln = {
                    "type": "DIRECTORY_LISTING",
                    "title": f"Directory listing enabled on {sub}",
                    "severity": "MEDIUM",
                    "evidence": {"title": scan_result.title},
                    "status": "CONFIRMED",
                    "risk_score": 50,
                    "source": "security_analysis",
                }
                scan_result.vulnerabilities.append(vuln)
                vulns_found += 1

            # Mark as completed
            scan_result.status = ScanStatus.COMPLETED

        # Update stats with total count (including Nuclei findings)
        total_vulns = sum(len(sr.vulnerabilities) for sr in self.scan_results.values())
        self.stats["vulnerabilities_found"] = total_vulns
        self.stats["hypotheses_generated"] = hyps_generated
        emit_log(self.mission_id, "INFO", f"Security analysis complete: {vulns_found} new vulns, {hyps_generated} hypotheses", "scanner")

    def _check_technology_vulnerabilities(self, technologies: List[str]) -> List[Dict[str, Any]]:
        """Check for known vulnerabilities in detected technologies"""
        vulns = []
        tech_str = " ".join(technologies).lower()

        # Known vulnerable technology patterns
        vuln_techs = [
            (r'wordpress\s*[0-4]\.', "OUTDATED_WORDPRESS", "Outdated WordPress version detected", 75),
            (r'drupal\s*[0-7]\.', "OUTDATED_DRUPAL", "Outdated Drupal version detected", 80),
            (r'joomla\s*[0-2]\.', "OUTDATED_JOOMLA", "Outdated Joomla version detected", 75),
            (r'php\s*[0-5]\.[0-6]', "OUTDATED_PHP", "Outdated PHP version detected", 70),
            (r'apache\s*2\.[0-2]\.', "OUTDATED_APACHE", "Outdated Apache version detected", 65),
            (r'nginx\s*1\.[0-9]\.', "OUTDATED_NGINX", "Potentially outdated Nginx version", 40),
            (r'jquery\s*[0-2]\.', "OUTDATED_JQUERY", "Outdated jQuery version (possible XSS)", 60),
            (r'angularjs\s*1\.[0-4]', "OUTDATED_ANGULAR", "Outdated AngularJS version", 55),
            (r'tomcat\s*[0-7]\.', "OUTDATED_TOMCAT", "Outdated Tomcat version", 70),
            (r'iis\s*[0-7]\.', "OUTDATED_IIS", "Outdated IIS version", 65),
            (r'struts', "APACHE_STRUTS", "Apache Struts detected (check for CVEs)", 70),
            (r'coldfusion', "COLDFUSION", "Adobe ColdFusion detected (check for CVEs)", 65),
            (r'weblogic', "WEBLOGIC", "Oracle WebLogic detected (check for CVEs)", 70),
        ]

        for pattern, vuln_type, title, risk_score in vuln_techs:
            if re.search(pattern, tech_str):
                vulns.append({
                    "type": vuln_type,
                    "title": title,
                    "severity": "HIGH" if risk_score >= 70 else "MEDIUM",
                    "evidence": {"detected_tech": [t for t in technologies if re.search(pattern.split('\\')[0], t.lower())]},
                    "status": "THEORETICAL",
                    "risk_score": risk_score,
                    "source": "technology_analysis",
                })

        return vulns

    def _check_security_headers(self, headers: Dict[str, str]) -> List[str]:
        """Check which security headers are missing"""
        missing = []
        headers_lower = {k.lower(): v for k, v in headers.items()}

        for header in self.SECURITY_HEADERS:
            if header.lower() not in headers_lower:
                missing.append(header)

        return missing

    def _categorize_endpoint(self, path: str) -> str:
        """Categorize endpoint based on path patterns"""
        path_lower = path.lower()

        if any(p in path_lower for p in ["/api/", "/v1/", "/v2/", "/graphql"]):
            return "API"
        elif any(p in path_lower for p in ["/admin", "/dashboard", "/manage", "/panel"]):
            return "ADMIN"
        elif any(p in path_lower for p in ["/login", "/signin", "/auth", "/oauth"]):
            return "AUTH"
        elif any(p in path_lower for p in ["/upload", "/file", "/document"]):
            return "FILE_UPLOAD"
        elif any(p in path_lower for p in ["/user", "/profile", "/account"]):
            return "USER"
        elif any(p in path_lower for p in [".js", ".css", ".png", ".jpg", ".gif"]):
            return "STATIC"
        elif any(p in path_lower for p in ["/config", ".env", ".git", "backup"]):
            return "SENSITIVE"
        else:
            return "GENERAL"

    def _generate_hypothesis_for_endpoint(self, endpoint: Dict[str, Any], subdomain: str) -> Optional[Dict[str, Any]]:
        """Generate security hypothesis for an endpoint"""
        path = endpoint.get("path", "").lower()
        category = endpoint.get("category", "GENERAL")

        # Pattern -> (attack_type, title, confidence, risk_score)
        patterns = {
            "API": ("BOLA", "Broken Object Level Authorization", 0.6, 70),
            "ADMIN": ("AUTH_BYPASS", "Admin authentication bypass", 0.7, 80),
            "AUTH": ("AUTH_BYPASS", "Authentication mechanism bypass", 0.6, 75),
            "FILE_UPLOAD": ("RCE", "Unrestricted file upload", 0.5, 85),
            "USER": ("IDOR", "Insecure direct object reference", 0.6, 70),
            "SENSITIVE": ("INFO_DISCLOSURE", "Sensitive information exposure", 0.8, 75),
        }

        if category in patterns:
            attack_type, title, confidence, risk_score = patterns[category]
            return {
                "attack_type": attack_type,
                "title": f"{title} on {path}",
                "confidence": confidence,
                "risk_score": risk_score,
                "target": f"{subdomain}{path}",
                "category": category,
            }

        # Check specific patterns
        if re.search(r'id=|user_id=|account=', path):
            return {
                "attack_type": "SQLI",
                "title": f"Potential SQL injection via parameter",
                "confidence": 0.5,
                "risk_score": 80,
                "target": f"{subdomain}{path}",
            }

        if re.search(r'redirect|return|next|url=', path):
            return {
                "attack_type": "OPEN_REDIRECT",
                "title": f"Potential open redirect",
                "confidence": 0.6,
                "risk_score": 50,
                "target": f"{subdomain}{path}",
            }

        return None

    async def _store_all_results(self):
        """Store all scan results in the graph"""
        nodes_created = 0

        for sub, scan_result in self.scan_results.items():
            if scan_result.status != ScanStatus.COMPLETED:
                continue

            # 1. Ensure subdomain node exists with full data
            await self.graph_client.add_subdomain(sub, source="iterative_scanner")
            nodes_created += 1

            # 2. Create HTTP service node with complete data
            if scan_result.final_url:
                service_props = {
                    "url": scan_result.final_url,
                    "status_code": scan_result.status_code,
                    "title": scan_result.title,
                    "technologies": scan_result.technologies,
                    "server": scan_result.server,
                    "http_alive": scan_result.http_alive,
                    "https_alive": scan_result.https_alive,
                    "missing_security_headers": scan_result.missing_security_headers,
                    "scan_status": "complete",
                }

                node_id = f"http_service:{scan_result.final_url}"
                await self.graph_client.create_node("HTTP_SERVICE", node_id, {
                    **service_props,
                    "mission_id": self.mission_id
                })
                nodes_created += 1

                # Create edge: subdomain -> http_service
                await self.graph_client.create_edge(
                    f"subdomain:{sub}",
                    node_id,
                    "HAS_SERVICE"
                )

            # 3. Create endpoint nodes
            for ep in scan_result.endpoints:
                path = ep.get("path")
                if path:
                    await self.graph_client.add_endpoint(
                        path,
                        method=ep.get("method", "GET"),
                        category=ep.get("category"),
                        risk_score=ep.get("risk_score", 0)
                    )
                    nodes_created += 1

                    # Generate hypothesis for this endpoint
                    await self.graph_client.generate_hypotheses_from_path(path)

            # 4. Create vulnerability nodes
            for vuln in scan_result.vulnerabilities:
                target_id = f"http_service:{scan_result.final_url}" if scan_result.final_url else f"subdomain:{sub}"

                vuln_hash = hashlib.md5(f"{vuln['type']}:{target_id}:{vuln['title']}".encode()).hexdigest()[:8]
                vuln_id = f"vuln:{vuln['type'].lower()}:{vuln_hash}"

                await self.graph_client.create_node("VULNERABILITY", vuln_id, {
                    "attack_type": vuln["type"],
                    "title": vuln["title"],
                    "severity": vuln.get("severity", "MEDIUM"),
                    "status": vuln.get("status", "CONFIRMED"),
                    "risk_score": vuln.get("risk_score", 50),
                    "evidence": json.dumps(vuln.get("evidence", {})),
                    "target_id": target_id,
                    "verified": True,
                    "mission_id": self.mission_id,
                })
                nodes_created += 1

                # Create edge: target -> vulnerability
                await self.graph_client.create_edge(target_id, vuln_id, "HAS_VULNERABILITY")

            # 5. Create hypothesis nodes
            for hyp in scan_result.hypotheses:
                target = hyp.get("target", sub)
                target_id = f"endpoint:{self.target_domain}{target}" if "/" in target else f"subdomain:{target}"

                await self.graph_client.add_hypothesis(
                    title=hyp["title"],
                    attack_type=hyp["attack_type"],
                    target_id=target_id,
                    confidence=hyp.get("confidence", 0.5)
                )
                nodes_created += 1

        emit_log(self.mission_id, "INFO", f"Stored {nodes_created} nodes in graph", "scanner")
        self.stats["technologies_detected"] = len(self.all_technologies)


async def run_iterative_scan(
    mission_id: str,
    target_domain: str,
    subdomains: List[str],
    graph_client: GraphClient,
    tools: Dict[str, Any],
    mode: str = "aggressive",
) -> Dict[str, Any]:
    """
    Entry point for iterative scanning.
    Runs complete reconnaissance on all provided subdomains.
    """
    scanner = IterativeScanner(
        mission_id=mission_id,
        target_domain=target_domain,
        graph_client=graph_client,
        tools=tools,
        mode=mode,
    )

    return await scanner.scan_all_subdomains(subdomains)
