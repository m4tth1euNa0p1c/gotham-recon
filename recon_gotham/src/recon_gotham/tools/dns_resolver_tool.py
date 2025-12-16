from pydantic import BaseModel, Field
import dns.resolver
from crewai.tools import BaseTool
from typing import List

class DNSResolveInput(BaseModel):
    subdomains: List[str] = Field(..., description="List of FQDNs to resolve")

class DnsResolverTool(BaseTool):
    name: str = "dns_resolver"
    description: str = "Resolve DNS records (A, MX, TXT, etc.) for a LIST of subdomains."
    args_schema: type[BaseModel] = DNSResolveInput

    def _resolve_single(self, subdomain: str) -> dict:
        results = {
            "subdomain": subdomain,
            "ips": [],
            "records": {}
        }
        
        # Record types to query
        record_types = ['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS', 'CAA']
        
        for rtype in record_types:
            try:
                answers = dns.resolver.resolve(subdomain, rtype, lifetime=3)
                collected = []
                for rdata in answers:
                    val = rdata.to_text()
                    collected.append(val)
                    
                    # Extract IPs from A/AAAA (simple heuristic, ignoring CNAME chains for now)
                    if rtype in ['A', 'AAAA']:
                        results["ips"].append(val)
                        
                if collected:
                    results["records"][rtype] = collected
                    
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout, Exception):
                continue
                
        return results

    def _run(self, subdomains: List[str]):
        output = []
        for sub in subdomains:
            if not sub: continue
            output.append(self._resolve_single(sub))
        return output
