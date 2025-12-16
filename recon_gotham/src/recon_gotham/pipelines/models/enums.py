"""
Enums for Recon-Gotham V3.0
Defines all enumeration types for the system.
"""

from enum import Enum


class NodeType(str, Enum):
    """Types of nodes in the AssetGraph."""
    DOMAIN = "DOMAIN"
    SUBDOMAIN = "SUBDOMAIN"
    HTTP_SERVICE = "HTTP_SERVICE"
    ENDPOINT = "ENDPOINT"
    PARAMETER = "PARAMETER"
    HYPOTHESIS = "HYPOTHESIS"
    VULNERABILITY = "VULNERABILITY"
    ATTACK_PATH = "ATTACK_PATH"
    IP_ADDRESS = "IP_ADDRESS"
    DNS_RECORD = "DNS_RECORD"
    ASN = "ASN"


class EdgeType(str, Enum):
    """Types of edges/relationships in the AssetGraph."""
    HAS_SUBDOMAIN = "HAS_SUBDOMAIN"
    RESOLVES_TO = "RESOLVES_TO"
    HAS_DNS = "HAS_DNS"
    SERVES = "SERVES"
    EXPOSES_HTTP = "EXPOSES_HTTP"
    EXPOSES_ENDPOINT = "EXPOSES_ENDPOINT"
    HAS_PARAM = "HAS_PARAM"
    HAS_HYPOTHESIS = "HAS_HYPOTHESIS"
    HAS_VULNERABILITY = "HAS_VULNERABILITY"
    TARGETS = "TARGETS"


class CategoryType(str, Enum):
    """Endpoint category types."""
    API = "API"
    ADMIN = "ADMIN"
    AUTH = "AUTH"
    PUBLIC = "PUBLIC"
    STATIC = "STATIC"
    LEGACY = "LEGACY"
    HEALTHCHECK = "HEALTHCHECK"
    UNKNOWN = "UNKNOWN"


class SensitivityLevel(str, Enum):
    """Parameter sensitivity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VulnerabilityStatus(str, Enum):
    """Vulnerability verification status."""
    UNTESTED = "UNTESTED"
    POSSIBLE = "POSSIBLE"
    CONFIRMED_THEORETICAL = "CONFIRMED_THEORETICAL"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class AttackType(str, Enum):
    """Types of attacks for hypotheses."""
    SQLI = "SQLI"
    XSS = "XSS"
    IDOR = "IDOR"
    AUTH_BYPASS = "AUTH_BYPASS"
    CODE_INJECTION = "CODE_INJECTION"
    RCE = "RCE"
    LFI = "LFI"
    SSRF = "SSRF"
    OPEN_REDIRECT = "OPEN_REDIRECT"
    CSRF = "CSRF"
    UNKNOWN = "UNKNOWN"


class BehaviorType(str, Enum):
    """Endpoint behavior types."""
    READ_ONLY = "READ_ONLY"
    STATE_CHANGING = "STATE_CHANGING"
    ID_BASED_ACCESS = "ID_BASED_ACCESS"
    SEARCH_QUERY = "SEARCH_QUERY"
    FILE_OPERATION = "FILE_OPERATION"
    AUTH_OPERATION = "AUTH_OPERATION"
    UNKNOWN = "UNKNOWN"


class TechStack(str, Enum):
    """Technology stack hints."""
    PHP = "PHP"
    ASP_NET = "ASP.NET"
    RAILS = "Rails"
    NODEJS = "Node.js"
    JAVA = "Java"
    PYTHON = "Python"
    GO = "Go"
    UNKNOWN = "Unknown"
