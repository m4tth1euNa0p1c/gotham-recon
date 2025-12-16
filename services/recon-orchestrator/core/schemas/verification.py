"""
Deep Verification Schemas (Lot 0.2 & 0.3)
Pydantic models for check modules, evidence, and verification results.
Version: 1.0.0 | Deep Verification v3.3
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator, root_validator
import hashlib
import json
import re


# =====================================================================
# ENUMS
# =====================================================================

class VulnStatus(str, Enum):
    """Vulnerability verification status."""
    THEORETICAL = "THEORETICAL"  # Hypothesis, no verification yet
    LIKELY = "LIKELY"            # Partial evidence supports it
    CONFIRMED = "CONFIRMED"      # Full evidence chain
    FALSE_POSITIVE = "FALSE_POSITIVE"  # Determined not vulnerable


class AttackType(str, Enum):
    """Standard attack type classifications."""
    XXE = "XXE"
    SQLI = "SQLI"
    XSS = "XSS"
    IDOR = "IDOR"
    BOLA = "BOLA"
    AUTH_BYPASS = "AUTH_BYPASS"
    RATE_LIMIT = "RATE_LIMIT"
    RCE = "RCE"
    SSRF = "SSRF"
    LFI = "LFI"
    RFI = "RFI"
    CSRF = "CSRF"
    OPEN_REDIRECT = "OPEN_REDIRECT"
    INFO_DISCLOSURE = "INFO_DISCLOSURE"
    HEADER_INJECTION = "HEADER_INJECTION"
    PATH_TRAVERSAL = "PATH_TRAVERSAL"
    INSECURE_DESERIALIZATION = "INSECURE_DESERIALIZATION"
    BROKEN_ACCESS_CONTROL = "BROKEN_ACCESS_CONTROL"
    SECURITY_MISCONFIGURATION = "SECURITY_MISCONFIGURATION"


class HttpMethod(str, Enum):
    """Allowed HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class EvidenceKind(str, Enum):
    """Types of evidence that can be collected."""
    HTTP_HEADER = "http_header"
    BODY_SNIPPET = "body_snippet"
    STATUS_CODE = "status_code"
    TIMING = "timing"
    FINGERPRINT = "fingerprint"
    ERROR_MESSAGE = "error_message"
    STACK_TRACE = "stack_trace"
    REFLECTION = "reflection"
    BEHAVIOR_DIFF = "behavior_diff"
    NEGATIVE_PROOF = "negative_proof"


class ModuleCategory(str, Enum):
    """Check module categories."""
    HTTP_PROBE = "http_probe"
    HEADER_ANALYSIS = "header_analysis"
    TECH_FINGERPRINT = "tech_fingerprint"
    CONFIG_EXPOSURE = "config_exposure"
    PARAMETER_TEST = "parameter_test"
    FUZZING = "fuzzing"
    AUTH_TEST = "auth_test"


class CheckStatus(str, Enum):
    """Status of a check execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    ROE_BLOCKED = "roe_blocked"


# =====================================================================
# CHECK MODULE SCHEMA (Lot 0.2)
# =====================================================================

class StopCondition(BaseModel):
    """Condition that stops module execution early."""
    type: str = Field(..., description="Condition type: status_code, header_match, body_match, timeout")
    value: Union[int, str, float] = Field(..., description="Value to match")
    operator: str = Field(default="equals", description="Comparison operator: equals, contains, regex, gt, lt")


class ExpectedProof(BaseModel):
    """Definition of what constitutes proof for this vulnerability."""
    type: str = Field(..., description="Proof type: status_code, header, body_pattern, timing")
    pattern: Optional[str] = Field(None, description="Regex pattern to match")
    value: Optional[Union[int, str, float]] = Field(None, description="Expected value")
    description: str = Field(..., description="Human-readable description of what this proves")


class CheckModule(BaseModel):
    """
    Check Module Schema (per plan.pdf spec).
    Defines a single verification check to run against a target.
    """
    # Identity
    id: str = Field(..., description="Unique module identifier (e.g., 'sqli-error-based-01')")
    name: str = Field(..., description="Human-readable module name")
    version: str = Field(default="1.0.0", description="Module version")
    category: ModuleCategory = Field(..., description="Module category")

    # Target specification
    target: str = Field(..., description="Target URL or endpoint pattern")
    method: HttpMethod = Field(default=HttpMethod.GET, description="HTTP method to use")

    # Request configuration
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom headers to send")
    body: Optional[str] = Field(None, description="Request body (for POST/PUT/PATCH)")
    body_type: Optional[str] = Field(None, description="Content-Type for body")
    query_params: Dict[str, str] = Field(default_factory=dict, description="Query parameters")

    # Execution control
    stop_conditions: List[StopCondition] = Field(default_factory=list, description="Conditions to abort early")
    timeout: int = Field(default=30, ge=1, le=60, description="Request timeout in seconds")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")
    max_redirects: int = Field(default=3, ge=0, le=10, description="Maximum redirects to follow")

    # Expected results
    expected_proof: List[ExpectedProof] = Field(..., min_items=1, description="What proves the vulnerability")
    max_status: VulnStatus = Field(default=VulnStatus.CONFIRMED, description="Maximum status this module can assign")

    # Metadata
    attack_type: AttackType = Field(..., description="Type of attack being tested")
    severity: str = Field(default="MEDIUM", description="Base severity if confirmed")
    description: str = Field(..., description="What this module tests")
    references: List[str] = Field(default_factory=list, description="CWE, CVE, or documentation links")

    # ROE constraints
    allowed_modes: List[str] = Field(default=["AGGRESSIVE"], description="Execution modes that allow this module")
    requires_auth: bool = Field(default=False, description="Whether auth context is required")

    @validator('id')
    def validate_id(cls, v):
        """Module ID must be lowercase alphanumeric with hyphens."""
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', v):
            raise ValueError('Module ID must be lowercase alphanumeric with hyphens')
        return v

    @validator('target')
    def validate_target(cls, v):
        """Target must be a valid URL pattern or placeholder."""
        if not v.startswith(('http://', 'https://', '{target_url}')):
            raise ValueError('Target must be a URL or {target_url} placeholder')
        return v

    class Config:
        use_enum_values = True


# =====================================================================
# EVIDENCE MODEL (Lot 0.3)
# =====================================================================

class RequestMeta(BaseModel):
    """Metadata about the request that produced evidence (redacted)."""
    method: str
    url: str = Field(..., description="Target URL (no query params with secrets)")
    timestamp: datetime
    headers_count: int = Field(default=0, description="Number of headers sent")
    body_size: int = Field(default=0, description="Size of request body")


class ResponseMeta(BaseModel):
    """Metadata about the response (redacted)."""
    status_code: int
    headers_count: int = Field(default=0, description="Number of response headers")
    body_size: int = Field(default=0, description="Size of response body")
    response_time_ms: int = Field(default=0, description="Response time in milliseconds")


class Evidence(BaseModel):
    """
    Evidence Model (Lot 0.3).
    Structured evidence with automatic hash generation and redaction.
    """
    # Evidence identity
    id: str = Field(default="", description="Evidence ID (auto-generated)")
    kind: EvidenceKind = Field(..., description="Type of evidence")

    # Content (redacted)
    summary: str = Field(..., max_length=500, description="Short summary of the evidence")
    detail: Optional[str] = Field(None, max_length=5000, description="Detailed evidence (redacted)")

    # Proof verification
    hash: str = Field(default="", description="SHA256 hash of canonical evidence")

    # Context
    request_meta: Optional[RequestMeta] = Field(None, description="Request metadata")
    response_meta: Optional[ResponseMeta] = Field(None, description="Response metadata")

    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Module reference
    module_id: Optional[str] = Field(None, description="Module that produced this evidence")
    tool_call_id: Optional[str] = Field(None, description="Tool call that produced this evidence")

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-generate ID and hash if not provided
        if not self.id:
            self.id = self._generate_id()
        if not self.hash:
            self.hash = self._compute_hash()

    def _generate_id(self) -> str:
        """Generate deterministic evidence ID."""
        kind_value = self.kind.value if hasattr(self.kind, 'value') else str(self.kind)
        ts_value = str(self.timestamp.timestamp()) if isinstance(self.timestamp, datetime) else str(self.timestamp)
        components = [
            kind_value,
            self.summary[:50],
            self.module_id or "",
            ts_value
        ]
        content = "|".join(components)
        return f"evidence-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _compute_hash(self) -> str:
        """Compute SHA256 hash of canonical evidence for verification."""
        kind_value = self.kind.value if hasattr(self.kind, 'value') else str(self.kind)
        canonical = {
            "kind": kind_value,
            "summary": self.summary,
            "detail": self.detail or "",
            "status_code": self.response_meta.status_code if self.response_meta else None
        }
        content = json.dumps(canonical, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    @classmethod
    def redact_secrets(cls, text: str, patterns: List[Dict[str, str]] = None) -> str:
        """
        Redact sensitive patterns from text.
        Uses default patterns if none provided.
        """
        if text is None:
            return None

        default_patterns = [
            (r'Authorization:\s*[^\s]+', 'Authorization: [REDACTED]'),
            (r'Cookie:\s*[^\r\n]+', 'Cookie: [REDACTED]'),
            (r'Set-Cookie:\s*[^\r\n]+', 'Set-Cookie: [REDACTED]'),
            (r'(api[_-]?key|apikey)[=:]\s*[\'"]?[a-zA-Z0-9_-]{16,}[\'"]?', '[API_KEY_REDACTED]'),
            (r'Bearer\s+[a-zA-Z0-9._-]+', 'Bearer [REDACTED]'),
            (r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*', '[JWT_REDACTED]'),
            (r'(password|passwd|pwd)[=:]\s*[^\s&]+', '[PASSWORD_REDACTED]'),
        ]

        result = text
        for pattern, replacement in default_patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    class Config:
        use_enum_values = True


# =====================================================================
# CHECK EXECUTION MODELS
# =====================================================================

class RunCheckRequest(BaseModel):
    """Request to run a check module against a target."""
    # Identity
    mission_id: str = Field(..., description="Mission this check belongs to")
    module_id: str = Field(..., description="Module to execute")
    target_id: str = Field(..., description="Target node ID (endpoint/http_service)")

    # Target resolution
    target_url: str = Field(..., description="Resolved target URL")

    # Execution context
    mode: str = Field(default="AGGRESSIVE", description="Execution mode (STEALTH/BALANCED/AGGRESSIVE)")
    auth_context: Optional[Dict[str, Any]] = Field(None, description="Authentication context if required")

    # Variables for template substitution
    variables: Dict[str, str] = Field(default_factory=dict, description="Variables for module template")

    # Idempotency
    idempotency_key: Optional[str] = Field(None, description="Key for idempotent execution")

    def generate_tool_call_id(self) -> str:
        """Generate deterministic tool_call_id for idempotency."""
        components = [
            self.mission_id,
            self.module_id,
            self.target_id
        ]
        content = "|".join(components)
        return f"check-{hashlib.sha256(content.encode()).hexdigest()[:16]}"


class RunCheckResult(BaseModel):
    """Result of running a check module."""
    # Identity
    tool_call_id: str = Field(..., description="Deterministic tool call ID")
    module_id: str = Field(..., description="Module that was executed")
    target_id: str = Field(..., description="Target that was checked")

    # Execution status
    status: CheckStatus = Field(..., description="Execution status")
    error_code: Optional[str] = Field(None, description="Error code if failed")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Results
    vulnerability_found: bool = Field(default=False, description="Whether vulnerability was found")
    vuln_status: Optional[VulnStatus] = Field(None, description="Status if vulnerability found")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")

    # Evidence
    evidence: List[Evidence] = Field(default_factory=list, description="Collected evidence")
    proof_hash: Optional[str] = Field(None, description="Hash of combined evidence")

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None)
    duration_ms: int = Field(default=0, description="Execution duration in ms")

    # Metrics
    requests_made: int = Field(default=0, description="Number of HTTP requests made")
    bytes_sent: int = Field(default=0, description="Total bytes sent")
    bytes_received: int = Field(default=0, description="Total bytes received")

    def compute_proof_hash(self) -> str:
        """Compute combined proof hash from all evidence."""
        if not self.evidence:
            return ""
        hashes = sorted([e.hash for e in self.evidence])
        combined = "|".join(hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    class Config:
        use_enum_values = True


# =====================================================================
# VERIFICATION PLAN MODELS
# =====================================================================

class VerificationTarget(BaseModel):
    """A target selected for verification."""
    target_id: str = Field(..., description="Node ID (endpoint or http_service)")
    target_url: str = Field(..., description="Resolved URL")
    target_type: str = Field(..., description="Node type (ENDPOINT, HTTP_SERVICE)")

    # Context
    hypothesis_id: Optional[str] = Field(None, description="Related hypothesis if any")
    vuln_id: Optional[str] = Field(None, description="Related THEORETICAL vuln if any")

    # Selection criteria
    risk_score: int = Field(default=0, ge=0, le=100, description="Risk score")
    priority: int = Field(default=1, ge=1, le=5, description="Verification priority")
    reason: str = Field(..., description="Why this target was selected")


class ModuleAssignment(BaseModel):
    """Assignment of a module to a target."""
    target_id: str
    module_id: str
    order: int = Field(default=0, description="Execution order")
    depends_on: List[str] = Field(default_factory=list, description="Must complete before this")


class VerificationPlan(BaseModel):
    """
    Complete verification plan produced by agents.
    Defines what to check, in what order, with what constraints.
    """
    # Identity
    mission_id: str
    plan_id: str = Field(default="", description="Auto-generated plan ID")

    # Targets
    targets: List[VerificationTarget] = Field(..., min_items=1)

    # Module assignments
    assignments: List[ModuleAssignment] = Field(..., min_items=1)

    # Constraints
    mode: str = Field(default="AGGRESSIVE")
    max_duration_seconds: int = Field(default=1800, ge=60, le=7200)
    max_modules: int = Field(default=100, ge=1, le=500)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="validation_planner_agent")

    def __init__(self, **data):
        super().__init__(**data)
        if not self.plan_id:
            self.plan_id = self._generate_plan_id()

    def _generate_plan_id(self) -> str:
        """Generate deterministic plan ID."""
        components = [
            self.mission_id,
            str(len(self.targets)),
            str(len(self.assignments)),
            str(self.created_at.timestamp()) if self.created_at else ""
        ]
        content = "|".join(components)
        return f"plan-{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def get_execution_order(self) -> List[ModuleAssignment]:
        """Return assignments in execution order, respecting dependencies."""
        # Simple topological sort
        completed = set()
        ordered = []
        remaining = list(self.assignments)

        while remaining:
            for assignment in remaining[:]:
                deps_met = all(dep in completed for dep in assignment.depends_on)
                if deps_met:
                    ordered.append(assignment)
                    completed.add(f"{assignment.target_id}:{assignment.module_id}")
                    remaining.remove(assignment)

            # Prevent infinite loop
            if not any(
                all(dep in completed for dep in a.depends_on)
                for a in remaining
            ):
                # Add remaining with unmet deps anyway
                ordered.extend(sorted(remaining, key=lambda x: x.order))
                break

        return ordered


# =====================================================================
# VULNERABILITY UPDATE MODEL
# =====================================================================

class VulnerabilityUpdate(BaseModel):
    """Update to apply to a vulnerability node."""
    vuln_id: str = Field(..., description="Vulnerability node ID")

    # Status update
    new_status: Optional[VulnStatus] = Field(None, description="New status to set")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Evidence to add
    evidence: List[Evidence] = Field(default_factory=list)
    proof_hash: Optional[str] = Field(None)

    # Metadata
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    validated_by: str = Field(..., description="Module or agent that validated")

    # Reason for update
    reason: str = Field(..., description="Why status changed")


# =====================================================================
# MODULE VALIDATION
# =====================================================================

def validate_module_against_roe(module: CheckModule, mode: str, roe_config: Dict) -> tuple[bool, str]:
    """
    Validate a module against ROE configuration.
    Returns (is_valid, error_message).
    """
    mode_config = roe_config.get("modes", {}).get(mode, {})

    if not mode_config:
        return False, f"Unknown mode: {mode}"

    # Check if mode allows this module
    if mode not in module.allowed_modes:
        return False, f"Module {module.id} not allowed in mode {mode}"

    # Check HTTP method
    allowed_methods = mode_config.get("allowed_methods", [])
    if module.method.value not in allowed_methods:
        return False, f"Method {module.method} not allowed in mode {mode}"

    # Check body constraints
    if module.body and not mode_config.get("allow_body", False):
        return False, f"Request body not allowed in mode {mode}"

    # Check auth requirement
    if module.requires_auth:
        category_config = roe_config.get("module_categories", {}).get(module.category.value, {})
        if category_config.get("requires_auth_context", False):
            return True, ""  # Auth will be checked at runtime

    return True, ""
