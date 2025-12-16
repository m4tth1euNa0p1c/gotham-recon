import json
from typing import Type, List
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Try importing dnspython
try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

class DnsInput(BaseModel):
    domain: str = Field(..., description="Domain to analyze (e.g. 'example.com')")

class DnsIntelTool(BaseTool):
    name: str = "dns_intelligence"
    description: str = "Retrieves A, MX, TXT records to identify IP, Mail Providers, and SPF/DMARC."
    args_schema: Type[BaseModel] = DnsInput

    def _run(self, domain: str) -> str:
        results = {
            "domain": domain,
            "a_records": [],
            "mx_records": [],
            "txt_records": [],
            "spf_present": False,
            "dmarc_present": False,
            "error": None
        }

        if not DNS_AVAILABLE:
            results["error"] = "dnspython library not installed."
            return json.dumps(results, indent=2)

        resolver = dns.resolver.Resolver()
        # Set timeout to avoid hanging
        resolver.lifetime = 5.0 

        # A Records
        try:
            answers = resolver.resolve(domain, 'A')
            results["a_records"] = [r.to_text() for r in answers]
        except Exception:
            pass

        # MX Records
        try:
            answers = resolver.resolve(domain, 'MX')
            results["mx_records"] = [r.exchange.to_text().rstrip('.') for r in answers]
        except Exception:
            pass

        # TXT Records (SPF)
        try:
            answers = resolver.resolve(domain, 'TXT')
            for r in answers:
                txt_val = r.to_text().strip('"')
                results["txt_records"].append(txt_val)
                if "v=spf1" in txt_val:
                    results["spf_present"] = True
        except Exception:
            pass

        # DMARC
        try:
            dmarc_domain = f"_dmarc.{domain}"
            answers = resolver.resolve(dmarc_domain, 'TXT')
            for r in answers:
                txt_val = r.to_text().strip('"')
                if "v=DMARC1" in txt_val:
                    results["dmarc_present"] = True
        except Exception:
            pass

        return json.dumps(results, indent=2)
