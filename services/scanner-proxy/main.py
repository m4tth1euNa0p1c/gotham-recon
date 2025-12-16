"""
Scanner Proxy - Check Runner for Deep Verification
Wraps security scanning tools with ROE enforcement and evidence collection.
Version: 2.0.0 | Deep Verification v3.3
"""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import time
from concurrent import futures
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
import structlog
import yaml
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()


# =====================================================================
# CONFIGURATION
# =====================================================================

class Settings:
    """Application settings."""
    MODULES_DIR = os.getenv("MODULES_DIR", "/app/check_modules")
    ROE_CONFIG_PATH = os.getenv("ROE_CONFIG_PATH", "/app/config/roe.yaml")
    DEFAULT_MODE = os.getenv("DEFAULT_MODE", "AGGRESSIVE")
    MAX_CONCURRENT_CHECKS = int(os.getenv("MAX_CONCURRENT_CHECKS", "10"))
    HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))


settings = Settings()


# =====================================================================
# ENUMS & MODELS (Compatible with orchestrator schemas)
# =====================================================================

class CheckStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    ROE_BLOCKED = "roe_blocked"


class VulnStatus(str, Enum):
    THEORETICAL = "THEORETICAL"
    LIKELY = "LIKELY"
    CONFIRMED = "CONFIRMED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class EvidenceKind(str, Enum):
    HTTP_HEADER = "http_header"
    BODY_SNIPPET = "body_snippet"
    STATUS_CODE = "status_code"
    TIMING = "timing"
    FINGERPRINT = "fingerprint"
    ERROR_MESSAGE = "error_message"
    REFLECTION = "reflection"
    NEGATIVE_PROOF = "negative_proof"


# =====================================================================
# REQUEST/RESPONSE MODELS
# =====================================================================

class Evidence(BaseModel):
    """Evidence item from check execution."""
    id: str = ""
    kind: str
    summary: str
    detail: Optional[str] = None
    hash: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    module_id: Optional[str] = None

    def compute_hash(self) -> str:
        canonical = json.dumps({
            "kind": self.kind,
            "summary": self.summary,
            "detail": self.detail or ""
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()


class RunCheckRequest(BaseModel):
    """Request to run a check module."""
    mission_id: str
    module_id: str
    target_id: str
    target_url: str
    mode: str = "AGGRESSIVE"
    variables: Dict[str, str] = Field(default_factory=dict)
    auth_context: Optional[Dict[str, Any]] = None


class RunCheckResult(BaseModel):
    """Result of check execution."""
    tool_call_id: str
    module_id: str
    target_id: str
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    vulnerability_found: bool = False
    vuln_status: Optional[str] = None
    confidence: float = 0.0
    evidence: List[Evidence] = Field(default_factory=list)
    proof_hash: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: int = 0
    requests_made: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0


class ModuleInfo(BaseModel):
    """Module metadata for listing."""
    id: str
    name: str
    version: str
    category: str
    attack_type: str
    severity: str
    description: str
    allowed_modes: List[str]


class ValidateModuleRequest(BaseModel):
    """Request to validate a module."""
    module: Dict[str, Any]
    mode: str = "AGGRESSIVE"


# =====================================================================
# ROE ENFORCEMENT
# =====================================================================

class ROEEnforcer:
    """Enforces Rules of Engagement for check execution."""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path or settings.ROE_CONFIG_PATH)
        self._sensitive_patterns = self._compile_patterns()

    def _load_config(self, path: str) -> Dict:
        """Load ROE configuration from YAML."""
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return yaml.safe_load(f)
        except Exception as e:
            logger.warning("roe_config_load_failed", error=str(e))

        # Return default config
        return {
            "modes": {
                "STEALTH": {
                    "allowed_methods": ["GET", "HEAD", "OPTIONS"],
                    "rate_limit": {"requests_per_second": 1},
                    "allow_body": False
                },
                "BALANCED": {
                    "allowed_methods": ["GET", "HEAD", "OPTIONS", "POST"],
                    "rate_limit": {"requests_per_second": 5},
                    "allow_body": True
                },
                "AGGRESSIVE": {
                    "allowed_methods": ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH"],
                    "rate_limit": {"requests_per_second": 20},
                    "allow_body": True
                }
            }
        }

    def _compile_patterns(self) -> List[tuple]:
        """Compile sensitive patterns for redaction."""
        patterns = []
        for item in self.config.get("security", {}).get("sensitive_patterns", []):
            try:
                patterns.append((
                    re.compile(item["pattern"], re.IGNORECASE),
                    item["redact_to"]
                ))
            except:
                pass
        return patterns

    def check_method(self, method: str, mode: str) -> tuple[bool, str]:
        """Check if HTTP method is allowed in mode."""
        mode_config = self.config.get("modes", {}).get(mode, {})
        allowed = mode_config.get("allowed_methods", [])
        if method.upper() not in allowed:
            return False, f"Method {method} not allowed in {mode} mode"
        return True, ""

    def check_body(self, body: str, mode: str) -> tuple[bool, str]:
        """Check if request body is allowed."""
        mode_config = self.config.get("modes", {}).get(mode, {})
        if body and not mode_config.get("allow_body", False):
            return False, f"Request body not allowed in {mode} mode"
        return True, ""

    def check_scope(self, url: str, target_domain: str) -> tuple[bool, str]:
        """Check if URL is in scope."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.netloc.lower()

            # Must end with target domain
            if not host.endswith(target_domain.lower()):
                return False, f"URL {url} is out of scope for {target_domain}"

            # Check excluded paths
            excluded_paths = self.config.get("scope", {}).get("excluded_paths", [])
            for pattern in excluded_paths:
                if pattern.endswith("*"):
                    if parsed.path.startswith(pattern[:-1]):
                        return False, f"Path {parsed.path} is excluded"
                elif parsed.path == pattern:
                    return False, f"Path {parsed.path} is excluded"

            return True, ""
        except Exception as e:
            return False, f"Scope check error: {str(e)}"

    def redact_sensitive(self, text: str) -> str:
        """Redact sensitive information from text."""
        if not text:
            return text

        result = text
        for pattern, replacement in self._sensitive_patterns:
            result = pattern.sub(replacement, result)
        return result

    def get_rate_limit(self, mode: str) -> float:
        """Get requests per second limit for mode."""
        mode_config = self.config.get("modes", {}).get(mode, {})
        return mode_config.get("rate_limit", {}).get("requests_per_second", 1)


# =====================================================================
# MODULE REGISTRY
# =====================================================================

class ModuleRegistry:
    """Registry for check modules."""

    def __init__(self, modules_dir: str = None):
        self.modules_dir = Path(modules_dir or settings.MODULES_DIR)
        self.modules: Dict[str, Dict] = {}
        self._load_modules()

    def _load_modules(self):
        """Load all modules from directory."""
        if not self.modules_dir.exists():
            logger.warning("modules_dir_not_found", path=str(self.modules_dir))
            return

        for category_dir in self.modules_dir.iterdir():
            if category_dir.is_dir():
                for module_file in category_dir.glob("*.json"):
                    try:
                        with open(module_file, "r") as f:
                            module = json.load(f)
                            self.modules[module["id"]] = module
                            logger.info("module_loaded", id=module["id"])
                    except Exception as e:
                        logger.error("module_load_failed", file=str(module_file), error=str(e))

    def get(self, module_id: str) -> Optional[Dict]:
        """Get module by ID."""
        return self.modules.get(module_id)

    def list(self) -> List[ModuleInfo]:
        """List all available modules."""
        return [
            ModuleInfo(
                id=m["id"],
                name=m["name"],
                version=m.get("version", "1.0.0"),
                category=m["category"],
                attack_type=m["attack_type"],
                severity=m.get("severity", "MEDIUM"),
                description=m["description"],
                allowed_modes=m.get("allowed_modes", ["AGGRESSIVE"])
            )
            for m in self.modules.values()
        ]

    def validate(self, module: Dict, mode: str) -> tuple[bool, str]:
        """Validate module structure and ROE compatibility."""
        required_fields = ["id", "name", "category", "target", "method", "expected_proof", "attack_type"]
        for field in required_fields:
            if field not in module:
                return False, f"Missing required field: {field}"

        # Check mode compatibility
        allowed_modes = module.get("allowed_modes", ["AGGRESSIVE"])
        if mode not in allowed_modes:
            return False, f"Module not allowed in {mode} mode"

        return True, ""


# =====================================================================
# CHECK RUNNER
# =====================================================================

class CheckRunner:
    """Executes check modules with ROE enforcement."""

    def __init__(self, roe_enforcer: ROEEnforcer, registry: ModuleRegistry):
        self.roe = roe_enforcer
        self.registry = registry
        self._rate_limiter: Dict[str, float] = {}
        self._idempotency_cache: Dict[str, RunCheckResult] = {}

    def _generate_tool_call_id(self, mission_id: str, module_id: str, target_id: str) -> str:
        """Generate deterministic tool call ID."""
        content = f"{mission_id}|{module_id}|{target_id}"
        return f"check-{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    def _apply_variables(self, text: str, variables: Dict[str, str]) -> str:
        """Apply variable substitution to text."""
        result = text
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    async def _rate_limit(self, mode: str):
        """Apply rate limiting based on mode."""
        rps = self.roe.get_rate_limit(mode)
        delay = 1.0 / rps
        key = f"rate_{mode}"
        last_call = self._rate_limiter.get(key, 0)
        elapsed = time.time() - last_call
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._rate_limiter[key] = time.time()

    async def run_check(self, request: RunCheckRequest) -> RunCheckResult:
        """Execute a check module against a target."""
        tool_call_id = self._generate_tool_call_id(
            request.mission_id,
            request.module_id,
            request.target_id
        )

        # Check idempotency cache
        if tool_call_id in self._idempotency_cache:
            logger.info("returning_cached_result", tool_call_id=tool_call_id)
            return self._idempotency_cache[tool_call_id]

        started_at = datetime.utcnow()
        result = RunCheckResult(
            tool_call_id=tool_call_id,
            module_id=request.module_id,
            target_id=request.target_id,
            status=CheckStatus.RUNNING.value,
            started_at=started_at.isoformat()
        )

        try:
            # Load module
            module = self.registry.get(request.module_id)
            if not module:
                result.status = CheckStatus.FAILED.value
                result.error_code = "MODULE_NOT_FOUND"
                result.error_message = f"Module {request.module_id} not found"
                return result

            # Validate module for mode
            valid, error = self.registry.validate(module, request.mode)
            if not valid:
                result.status = CheckStatus.ROE_BLOCKED.value
                result.error_code = "MODULE_NOT_ALLOWED"
                result.error_message = error
                return result

            # Check method allowed
            valid, error = self.roe.check_method(module["method"], request.mode)
            if not valid:
                result.status = CheckStatus.ROE_BLOCKED.value
                result.error_code = "METHOD_NOT_ALLOWED"
                result.error_message = error
                return result

            # Apply rate limiting
            await self._rate_limit(request.mode)

            # Prepare request
            variables = {"target_url": request.target_url, **request.variables}
            target = self._apply_variables(module["target"], variables)

            # Execute HTTP request
            evidence, vuln_found, confidence = await self._execute_http_check(
                target=target,
                method=module["method"],
                headers=module.get("headers", {}),
                body=module.get("body"),
                timeout=module.get("timeout", settings.HTTP_TIMEOUT),
                expected_proof=module.get("expected_proof", []),
                module_id=request.module_id
            )

            result.evidence = evidence
            result.vulnerability_found = vuln_found
            result.confidence = confidence
            result.requests_made = 1

            if vuln_found:
                result.vuln_status = module.get("max_status", VulnStatus.LIKELY.value)
                # Compute proof hash
                if evidence:
                    hashes = sorted([e.compute_hash() for e in evidence if e.kind != "negative_proof"])
                    if hashes:
                        result.proof_hash = hashlib.sha256("|".join(hashes).encode()).hexdigest()

            result.status = CheckStatus.SUCCESS.value

        except asyncio.TimeoutError:
            result.status = CheckStatus.TIMEOUT.value
            result.error_code = "TIMEOUT"
            result.error_message = "Check execution timed out"
        except Exception as e:
            result.status = CheckStatus.FAILED.value
            result.error_code = "EXECUTION_ERROR"
            result.error_message = str(e)
            logger.error("check_execution_failed", error=str(e), module_id=request.module_id)

        # Finalize result
        result.completed_at = datetime.utcnow().isoformat()
        result.duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)

        # Cache result
        self._idempotency_cache[tool_call_id] = result

        return result

    async def _execute_http_check(
        self,
        target: str,
        method: str,
        headers: Dict[str, str],
        body: Optional[str],
        timeout: int,
        expected_proof: List[Dict],
        module_id: str
    ) -> tuple[List[Evidence], bool, float]:
        """Execute HTTP request and collect evidence."""
        evidence: List[Evidence] = []
        vuln_found = False
        confidence = 0.0
        matches = 0
        total_proofs = len(expected_proof)

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                response = await client.request(
                    method=method,
                    url=target,
                    headers=headers,
                    content=body
                )

                # Collect base evidence
                evidence.append(Evidence(
                    kind=EvidenceKind.STATUS_CODE.value,
                    summary=f"HTTP {response.status_code}",
                    detail=None,
                    module_id=module_id
                ))

                # Check each expected proof
                for proof in expected_proof:
                    proof_type = proof.get("type")
                    pattern = proof.get("pattern")
                    expected_value = proof.get("value")

                    matched = False

                    if proof_type == "status_code":
                        if expected_value and response.status_code == expected_value:
                            matched = True
                            evidence.append(Evidence(
                                kind=EvidenceKind.STATUS_CODE.value,
                                summary=f"Status code {response.status_code} matches expected {expected_value}",
                                detail=proof.get("description", ""),
                                module_id=module_id
                            ))

                    elif proof_type == "header":
                        headers_str = "\n".join([f"{k}: {v}" for k, v in response.headers.items()])
                        if pattern:
                            regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                            if regex.search(headers_str):
                                matched = True
                                # Redact before storing
                                redacted_headers = self.roe.redact_sensitive(headers_str)
                                evidence.append(Evidence(
                                    kind=EvidenceKind.HTTP_HEADER.value,
                                    summary=f"Header pattern matched: {proof.get('description', pattern[:50])}",
                                    detail=redacted_headers[:1000],
                                    module_id=module_id
                                ))

                    elif proof_type == "body_pattern":
                        if pattern:
                            body_text = response.text[:10000]  # Limit body size
                            regex = re.compile(pattern, re.IGNORECASE)
                            match = regex.search(body_text)
                            if match:
                                matched = True
                                # Redact and truncate
                                snippet = body_text[max(0, match.start()-50):match.end()+50]
                                redacted = self.roe.redact_sensitive(snippet)
                                evidence.append(Evidence(
                                    kind=EvidenceKind.BODY_SNIPPET.value,
                                    summary=f"Body pattern matched: {proof.get('description', pattern[:50])}",
                                    detail=redacted[:500],
                                    module_id=module_id
                                ))

                    if matched:
                        matches += 1

                # Calculate confidence and vulnerability status
                if total_proofs > 0:
                    confidence = matches / total_proofs
                    vuln_found = confidence > 0

                # Add timing evidence
                evidence.append(Evidence(
                    kind=EvidenceKind.TIMING.value,
                    summary=f"Response time: {int(response.elapsed.total_seconds() * 1000)}ms",
                    detail=None,
                    module_id=module_id
                ))

            except httpx.RequestError as e:
                evidence.append(Evidence(
                    kind=EvidenceKind.ERROR_MESSAGE.value,
                    summary=f"Request failed: {type(e).__name__}",
                    detail=str(e)[:500],
                    module_id=module_id
                ))

        return evidence, vuln_found, confidence


# =====================================================================
# FASTAPI APPLICATION
# =====================================================================

# Initialize components
roe_enforcer = ROEEnforcer()
module_registry = ModuleRegistry()
check_runner = CheckRunner(roe_enforcer, module_registry)

app = FastAPI(
    title="Scanner Proxy - Check Runner",
    version="2.0.0",
    description="Deep Verification Check Runner with ROE enforcement"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "scanner-proxy",
        "version": "2.0.0",
        "modules_loaded": len(module_registry.modules),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/checks/modules", response_model=List[ModuleInfo])
async def list_modules():
    """List all available check modules."""
    return module_registry.list()


@app.get("/api/v1/checks/modules/{module_id}")
async def get_module(module_id: str):
    """Get details of a specific module."""
    module = module_registry.get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail=f"Module {module_id} not found")
    return module


@app.post("/api/v1/checks/validate")
async def validate_module(request: ValidateModuleRequest):
    """Validate a module against schema and ROE."""
    valid, error = module_registry.validate(request.module, request.mode)
    return {
        "valid": valid,
        "error": error if not valid else None,
        "mode": request.mode
    }


@app.post("/api/v1/checks/run", response_model=RunCheckResult)
async def run_check(request: RunCheckRequest):
    """Run a check module against a target."""
    logger.info("running_check", module_id=request.module_id, target=request.target_url)
    result = await check_runner.run_check(request)
    logger.info("check_completed",
                module_id=request.module_id,
                status=result.status,
                vuln_found=result.vulnerability_found)
    return result


# =====================================================================
# LEGACY SCANNER OPERATIONS (backward compatibility)
# =====================================================================

class ScannerProxyServicer:
    """Legacy gRPC servicer for scanner operations."""

    _idempotency_cache = {}

    def run_subfinder(self, domain: str, timeout: int = 120, idempotency_key: str = None):
        """Run subdomain enumeration."""
        if idempotency_key and idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]

        logger.info("running_subfinder", domain=domain, timeout=timeout)

        try:
            result = subprocess.run(
                ["subfinder", "-d", domain, "-json", "-silent"],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            subdomains = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        data = json.loads(line)
                        subdomains.append({
                            "host": data.get("host"),
                            "source": data.get("source")
                        })
                    except json.JSONDecodeError:
                        subdomains.append({"host": line, "source": "subfinder"})

            response = {"subdomains": subdomains, "count": len(subdomains)}

            if idempotency_key:
                self._idempotency_cache[idempotency_key] = response

            return response
        except subprocess.TimeoutExpired:
            return {"subdomains": [], "count": 0, "error": "timeout"}
        except FileNotFoundError:
            return {"subdomains": [], "count": 0, "error": "tool_not_installed"}

    def probe_http(self, urls: list, concurrency: int = 10, timeout: int = 30):
        """Probe URLs for HTTP services."""
        logger.info("probing_http", url_count=len(urls), concurrency=concurrency)

        try:
            with open("/tmp/urls.txt", "w") as f:
                f.write("\n".join(urls))

            result = subprocess.run(
                ["httpx", "-l", "/tmp/urls.txt", "-json", "-silent", "-threads", str(concurrency)],
                capture_output=True,
                text=True,
                timeout=timeout * len(urls) // concurrency + 30
            )

            services = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        data = json.loads(line)
                        services.append({
                            "url": data.get("url"),
                            "status_code": data.get("status_code"),
                            "title": data.get("title"),
                            "technologies": data.get("tech", []),
                            "content_length": data.get("content_length")
                        })
                    except json.JSONDecodeError:
                        pass

            return {"services": services, "count": len(services)}
        except FileNotFoundError:
            return {"services": [], "count": 0, "error": "tool_not_installed"}
        except subprocess.TimeoutExpired:
            return {"services": [], "count": 0, "error": "timeout"}

    def run_nuclei(self, target: str, templates: list = None, mode: str = "stealth", idempotency_key: str = None):
        """Run vulnerability scanning."""
        if idempotency_key and idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[idempotency_key]

        logger.info("running_nuclei", target=target, mode=mode)

        try:
            cmd = ["nuclei", "-u", target, "-json", "-silent"]
            if templates:
                cmd.extend(["-t", ",".join(templates)])
            if mode == "stealth":
                cmd.extend(["-rl", "10"])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            findings = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        data = json.loads(line)
                        findings.append({
                            "template_id": data.get("template-id"),
                            "severity": data.get("info", {}).get("severity"),
                            "name": data.get("info", {}).get("name"),
                            "matched_at": data.get("matched-at"),
                            "type": data.get("type")
                        })
                    except json.JSONDecodeError:
                        pass

            response = {"findings": findings, "count": len(findings)}

            if idempotency_key:
                self._idempotency_cache[idempotency_key] = response

            return response
        except FileNotFoundError:
            return {"findings": [], "count": 0, "error": "tool_not_installed"}
        except subprocess.TimeoutExpired:
            return {"findings": [], "count": 0, "error": "timeout"}


# Legacy endpoints
scanner = ScannerProxyServicer()


@app.post("/api/v1/scanner/subfinder")
async def run_subfinder(domain: str, timeout: int = 120, idempotency_key: str = None):
    """Legacy subfinder endpoint."""
    return scanner.run_subfinder(domain, timeout, idempotency_key)


@app.post("/api/v1/scanner/httpx")
async def probe_http(urls: List[str], concurrency: int = 10, timeout: int = 30):
    """Legacy httpx endpoint."""
    return scanner.probe_http(urls, concurrency, timeout)


@app.post("/api/v1/scanner/nuclei")
async def run_nuclei(target: str, templates: List[str] = None, mode: str = "stealth"):
    """Legacy nuclei endpoint."""
    return scanner.run_nuclei(target, templates, mode)


# =====================================================================
# STARTUP
# =====================================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("scanner_proxy_started", http_port=8051)
    uvicorn.run(app, host="0.0.0.0", port=8051)
