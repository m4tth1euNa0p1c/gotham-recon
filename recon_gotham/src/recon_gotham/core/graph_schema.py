"""
Graph Schema - V3.0 Node/Edge Types and ID Helpers
Formal schema for AssetGraph structure.
"""

from enum import Enum
from typing import Optional
from urllib.parse import urlparse
import hashlib


# ============================================================================
# NODE TYPES
# ============================================================================

class NodeType(str, Enum):
    """Valid node types in the AssetGraph."""
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


VALID_NODE_TYPES = [t.value for t in NodeType]


# ============================================================================
# EDGE TYPES
# ============================================================================

class EdgeType(str, Enum):
    """Valid edge types in the AssetGraph."""
    HAS_SUBDOMAIN = "HAS_SUBDOMAIN"        # DOMAIN -> SUBDOMAIN
    RESOLVES_TO = "RESOLVES_TO"            # SUBDOMAIN -> IP_ADDRESS
    HAS_DNS = "HAS_DNS"                    # SUBDOMAIN -> DNS_RECORD
    SERVES = "SERVES"                      # SUBDOMAIN -> HTTP_SERVICE
    EXPOSES_HTTP = "EXPOSES_HTTP"          # SUBDOMAIN -> HTTP_SERVICE (alias)
    EXPOSES_ENDPOINT = "EXPOSES_ENDPOINT"  # HTTP_SERVICE -> ENDPOINT
    HAS_PARAM = "HAS_PARAM"                # ENDPOINT -> PARAMETER
    HAS_HYPOTHESIS = "HAS_HYPOTHESIS"      # ENDPOINT -> HYPOTHESIS
    HAS_VULNERABILITY = "HAS_VULNERABILITY"# ENDPOINT -> VULNERABILITY
    TARGETS = "TARGETS"                    # ATTACK_PATH -> target


VALID_EDGE_TYPES = [t.value for t in EdgeType]


# ============================================================================
# ID GENERATION HELPERS
# ============================================================================

def make_subdomain_id(hostname: str) -> str:
    """Generate subdomain node ID."""
    return f"subdomain:{hostname.lower().strip()}"


def make_http_service_id(url: str) -> str:
    """Generate HTTP service node ID."""
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    host = parsed.netloc.lower()
    port = ""
    
    if ":" in host:
        host, port = host.rsplit(":", 1)
    else:
        port = "443" if scheme == "https" else "80"
    
    return f"http_service:{scheme}://{host}:{port}"


def make_endpoint_id(origin: str) -> str:
    """Generate endpoint node ID from full URL."""
    # Use hash for long URLs
    if len(origin) > 100:
        hash_part = hashlib.md5(origin.encode()).hexdigest()[:12]
        return f"endpoint:{hash_part}"
    return f"endpoint:{origin}"


def make_parameter_id(endpoint_id: str, param_name: str) -> str:
    """Generate parameter node ID."""
    return f"param:{endpoint_id}:{param_name}"


def make_hypothesis_id(endpoint_id: str, attack_type: str) -> str:
    """Generate hypothesis node ID."""
    return f"hypothesis:{endpoint_id}:{attack_type}"


def make_vulnerability_id(endpoint_id: str, vuln_type: str) -> str:
    """Generate vulnerability node ID."""
    return f"vuln:{endpoint_id}:{vuln_type}"


def make_attack_path_id(target_id: str) -> str:
    """Generate attack path node ID."""
    return f"attack_path:{target_id}"


def make_ip_id(ip: str) -> str:
    """Generate IP address node ID."""
    return f"ip:{ip}"


def make_dns_record_id(subdomain: str, record_type: str, value: str) -> str:
    """Generate DNS record node ID."""
    hash_part = hashlib.md5(f"{subdomain}:{record_type}:{value}".encode()).hexdigest()[:12]
    return f"dns:{record_type}:{hash_part}"


# ============================================================================
# URL/HOST EXTRACTION HELPERS
# ============================================================================

def extract_hostname(url: str) -> str:
    """Extract hostname from URL."""
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path.split('/')[0]
    if ":" in host:
        host = host.rsplit(":", 1)[0]
    return host.lower()


def extract_path(url: str) -> str:
    """Extract path from URL."""
    parsed = urlparse(url)
    return parsed.path or "/"


def normalize_path(path: str) -> str:
    """Normalize a URL path."""
    if not path:
        return "/"
    
    # Remove query string
    if "?" in path:
        path = path.split("?")[0]
    
    # Remove fragment
    if "#" in path:
        path = path.split("#")[0]
    
    # Ensure leading slash
    if not path.startswith("/"):
        path = "/" + path
    
    # Remove double slashes
    while "//" in path:
        path = path.replace("//", "/")
    
    return path


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def is_valid_node_type(node_type: str) -> bool:
    """Check if node type is valid."""
    return node_type in VALID_NODE_TYPES


def is_valid_edge_type(edge_type: str) -> bool:
    """Check if edge type is valid."""
    return edge_type in VALID_EDGE_TYPES


def validate_node(node: dict) -> bool:
    """Validate a node structure."""
    if not isinstance(node, dict):
        return False
    
    required = ["id", "type"]
    for field in required:
        if field not in node:
            return False
    
    if not is_valid_node_type(node["type"]):
        return False
    
    return True


def validate_edge(edge: dict) -> bool:
    """Validate an edge structure."""
    if not isinstance(edge, dict):
        return False
    
    required = ["from", "to", "type"]
    for field in required:
        if field not in edge:
            return False
    
    if not is_valid_edge_type(edge["type"]):
        return False
    
    return True
