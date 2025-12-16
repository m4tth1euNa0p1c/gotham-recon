import requests
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from typing import List

class ASNLookupInput(BaseModel):
    ips: List[str] = Field(..., description="List of IP addresses to lookup")

class ASNLookupTool(BaseTool):
    name: str = "asn_lookup"
    description: str = "Retrieve ASN, org, and netblock info for a LIST of IPs."
    args_schema: type[BaseModel] = ASNLookupInput

    def _lookup_single(self, ip: str) -> dict:
        url = f"http://ip-api.com/json/{ip}"
        try:
            data = requests.get(url, timeout=5).json()
            if data.get("status") == "fail":
                return {"ip": ip, "error": data.get("message")}
                
            as_string = data.get("as", "")
            asn_code = as_string.split(" ")[0] if " " in as_string else as_string
            
            return {
                "ip": ip,
                "asn": {
                    "asn": asn_code,
                    "name": data.get("org") or data.get("isp"),
                    "country_code": data.get("countryCode"),
                    "description": data.get("as")
                },
                "prefixes": []
            }
        except Exception as e:
            return {"ip": ip, "error": str(e)}

    def _run(self, ips: List[str]):
        results = []
        # Deduplicate IPs
        unique_ips = list(set(ips))
        for ip in unique_ips:
            if not ip: continue
            results.append(self._lookup_single(ip))
        return results
