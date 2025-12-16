"""
DNS Resolver tool for CrewAI agents.
Resolves DNS records (A, MX, TXT, etc.) for subdomains.
"""
import json
from typing import List, Type

from pydantic import BaseModel, Field

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass


class DNSResolveInput(BaseModel):
    """Schema for DnsResolverTool arguments."""
    subdomains: List[str] = Field(..., description="List of FQDNs to resolve.")


class DnsResolverTool(BaseTool):
    """CrewAI tool for DNS resolution."""
    name: str = "dns_resolver"
    description: str = "Resolve DNS records (A, MX, TXT, CNAME, NS, CAA) for a list of subdomains."
    args_schema: Type[BaseModel] = DNSResolveInput

    def _resolve_single(self, subdomain: str) -> dict:
        """Resolve DNS records for a single subdomain."""
        results = {
            "subdomain": subdomain,
            "ips": [],
            "records": {}
        }

        if not DNS_AVAILABLE:
            results["error"] = "dnspython not installed"
            return results

        record_types = ['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS', 'CAA']

        for rtype in record_types:
            try:
                answers = dns.resolver.resolve(subdomain, rtype, lifetime=3)
                collected = []
                for rdata in answers:
                    val = rdata.to_text()
                    collected.append(val)
                    if rtype in ['A', 'AAAA']:
                        results["ips"].append(val)
                if collected:
                    results["records"][rtype] = collected
            except Exception:
                continue

        return results

    def _run(self, subdomains: List[str]) -> str:
        """Run DNS resolution for all subdomains."""
        output = []
        for sub in subdomains:
            if not sub:
                continue
            output.append(self._resolve_single(sub))
        return json.dumps(output, indent=2)
