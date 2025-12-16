import os
import json
import logging
import datetime
import shutil
import subprocess
from typing import Dict, List, Any

class ReportBuilder:
    """
    Generates a comprehensive Red Team Mission Report.
    """
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)

    def _normalize_label(self, label: str) -> str:
        if not label: return "Unknown"
        if label.startswith("http://"): return label.replace("http://", "") + " (HTTP)"
        if label.startswith("https://"): return label.replace("https://", "") + " (HTTPS)"
        return label

    def generate_report(self, domain: str, graph_data: Dict[str, Any], attack_plan: List[Dict[str, Any]], confirmed_chains: List[Dict[str, Any]]) -> str:
        """
        Builds the Markdown report and attempts to convert it to PDF.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        report_path = os.path.join(self.output_dir, f"{domain}_red_team_report.md")
        
        md_content = self._build_markdown(domain, graph_data, attack_plan, confirmed_chains)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        self.logger.info(f"Report generated: {report_path}")
        
        # PDF Conversion
        self._convert_to_pdf(report_path)
        
        return report_path

    def _build_markdown(self, domain: str, graph_data: Dict, attack_plan: List, chains: List) -> str:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Stats
        nodes = graph_data.get("nodes", [])
        subdomains = [n for n in nodes if n["type"] == "SUBDOMAIN"]
        eps = [n for n in nodes if n["type"] == "ENDPOINT"]
        vulns = [n for n in nodes if n["type"] == "VULNERABILITY"]
        params = [n for n in nodes if n["type"] == "PARAMETER"]
        
        high_vulns = [v for v in vulns if v.get("properties", {}).get("severity") in ["CRITICAL", "HIGH"]]
        confirmed_vulns = [v for v in vulns if v.get("properties", {}).get("confirmed")]

        md = f"""# 🚩 Red Team Mission Report: {domain}
**Date:** {now}
**Confidentiality:** INTERNAL USE ONLY

---

## 1. Executive Summary
**Mission Status:** {'🔴 CRITICAL ISSUES FOUND' if confirmed_vulns else '🟢 RECONNAISSANCE COMPLETE'}

The automated reconnaissance and preliminary offensive phase against **{domain}** has been completed.
The system identified **{len(subdomains)}** subdomains and **{len(eps)}** endpoints.

**Key Findings:**
- **Vulnerabilities:** {len(vulns)} detected ({len(high_vulns)} High/Critical).
- **Confirmed Exploitable:** {len(confirmed_vulns)} confirmed via safe probes.
- **Exploit Chains:** {len(chains)} potential attack paths identified.

---

## 2. Infrastructure Overview
**Attack Surface:**
- Subdomains: {len(subdomains)}
- Endpoints: {len(eps)}
- Parameters: {len(params)}

**Top Targets:**

### 🏛️ Strategic Intelligence (OSINT)
"""
        osint_prefixes = ("org:", "saas:", "repo:", "brand:", "leak:")
        osint_plans = [p for p in attack_plan if str(p.get('subdomain', '')).startswith(osint_prefixes)]
        
        if not osint_plans:
            md += "*No significant OSINT chains identified.*\n"
        else:
            for plan in osint_plans[:5]:
                lbl = plan.get('subdomain')
                score = plan.get('score', 0)
                reason = plan.get('reason', '')
                md += f"- **{lbl}** (Score: {score})\n  Reason: {reason}\n"

        md += """
### 🎯 Technical Attack Vectors
"""
        tech_plans = [p for p in attack_plan if p not in osint_plans]
        
        if not tech_plans:
             md += "*No high-value technical targets identified.*\n"
        else:
            for plan in tech_plans[:5]: # Top 5
                lbl = self._normalize_label(plan.get('subdomain'))
                score = plan.get('score', 0)
                reason = plan.get('reason', '')
                md += f"- **{lbl}** (Score: {score})\n  Reason: {reason}\n"

        md += """
---

## 3. Vulnerability Analysis
"""
        if not vulns:
            md += "*No significant vulnerabilities detected during this phase.*"
        else:
            md += "| Severity | Name | Confirmed | Tool | URL |\n|---|---|---|---|---|\n"
            for v in vulns:
                p = v.get("properties", {})
                sev = p.get("severity", "LOW")
                name = p.get("name", "Unknown")
                conf = "✅" if p.get("confirmed") else "❓"
                tool = p.get("tool", "Unknown")
                # Find affected URL logic is complex via edges, here we rely on the ID or assume simplistic link
                # For summary we just list what we have
                md += f"| **{sev}** | {name} | {conf} | {tool} | ... |\n"

        md += """
---

## 4. Exploitation Plan
"""
        if chains:
            for i, chain in enumerate(chains, 1):
                md += f"### Chain #{i}: {chain.get('chain', 'Unknown Strategy')}\n"
                md += f"- **Vulnerability:** {chain.get('vulnerability')}\n"
                md += f"- **Target:** {chain.get('path')}\n"
                md += f"- **Payload:** `{chain.get('payload')}`\n\n"
        else:
            md += "*No full exploitation chains could be automatically constructed.*"

        md += """
---

## 5. Recommendations
1. **Immediate Action:** Patch {len(high_vulns)} Critical/High vulnerabilities.
2. **Review:** Manual verification of unconfirmed findings.
3. **Hardening:** Review exposed parameters and legacy endpoints.

---
*Generated by Recon-Gotham AI*
"""
        return md

    def _convert_to_pdf(self, md_path: str):
        if not shutil.which("pandoc"):
            self.logger.warning("Pandoc not found. Skipping PDF generation.")
            return

        pdf_path = md_path.replace(".md", ".pdf")
        try:
            # simple pandoc call
            subprocess.run(["pandoc", md_path, "-o", pdf_path], check=True)
            self.logger.info(f"PDF Generated: {pdf_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate PDF: {e}")
