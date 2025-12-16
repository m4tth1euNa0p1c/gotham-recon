"""
Reporting Service - Report Generation Pipeline
Generates mission summaries, exports graph, and creates knowledge files.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from recon_gotham.core.asset_graph import AssetGraph


@dataclass
class ReportResult:
    """Result of report generation."""
    summary_path: str
    knowledge_path: str
    graph_path: str
    metrics_path: Optional[str]


class ReportingService:
    """
    Reporting Service - Final Report Generation.
    
    Generates:
    - Mission summary (markdown)
    - Knowledge summary (for future runs)
    - Asset graph export (JSON)
    - Metrics export (JSON)
    """
    
    def __init__(self, graph: AssetGraph, settings: Dict, run_id: str):
        self.graph = graph
        self.settings = settings
        self.run_id = run_id
        self.target_domain = settings.get("target_domain")
        self.output_dir = settings.get("output_dir", "recon_gotham/output")
        self.knowledge_dir = settings.get("knowledge_dir", "recon_gotham/knowledge")
    
    def generate_report(self, metrics: Optional[Dict] = None) -> ReportResult:
        """
        Generate all reports.
        
        Args:
            metrics: Optional metrics dictionary to include
            
        Returns:
            ReportResult with file paths
        """
        # Ensure directories exist
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.knowledge_dir, exist_ok=True)
        
        # Generate summary
        summary_content = self._generate_summary(metrics)
        summary_path = os.path.join(self.output_dir, f"{self.target_domain}_summary.md")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        # Generate knowledge summary
        knowledge_content = self._generate_knowledge_summary(metrics)
        knowledge_path = os.path.join(self.knowledge_dir, f"{self.target_domain}_summary.md")
        with open(knowledge_path, 'w', encoding='utf-8') as f:
            f.write(knowledge_content)
        
        # Export graph
        graph_path = os.path.join(self.output_dir, f"{self.target_domain}_asset_graph.json")
        self.graph.export_json(graph_path)
        
        # Export metrics if provided
        metrics_path = None
        if metrics:
            metrics_path = os.path.join(self.output_dir, f"{self.target_domain}_{self.run_id}_metrics.json")
            with open(metrics_path, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2)
        
        return ReportResult(
            summary_path=summary_path,
            knowledge_path=knowledge_path,
            graph_path=graph_path,
            metrics_path=metrics_path
        )
    
    def _generate_summary(self, metrics: Optional[Dict]) -> str:
        """Generate the mission summary markdown."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        mode = self.settings.get("mode", "AGGRESSIVE")
        
        # Count assets
        stats = self._count_assets()
        
        # Build summary
        lines = [
            f"# Mission Summary: {self.target_domain}",
            "",
            f"**Date:** {now}",
            f"**Mode:** {mode}",
            f"**Run ID:** {self.run_id}",
            "",
            "## 📊 Asset Statistics",
            f"- **Subdomains Found**: {stats['subdomains']}",
            f"- **HTTP Services**: {stats['http_services']}",
            f"- **Endpoints**: {stats['endpoints']}",
            f"- **Parameters**: {stats['parameters']}",
            f"- **DNS/IP/ASN Records**: {stats['dns_records']}",
            f"- **Hypotheses**: {stats['hypotheses']}",
            f"- **Vulnerabilities (Theoretical)**: {stats['vulnerabilities']}",
            "",
        ]
        
        # Attack Plan section
        attack_plan = self._generate_attack_plan()
        lines.extend(attack_plan)
        
        # Endpoint Intelligence section
        endpoint_intel = self._generate_endpoint_intel_section()
        lines.extend(endpoint_intel)
        
        # Stack & Infrastructure section
        stack_section = self._generate_stack_section()
        lines.extend(stack_section)
        
        # Vulnerabilities section
        vuln_section = self._generate_vuln_section()
        lines.extend(vuln_section)
        
        return "\n".join(lines)
    
    def _generate_knowledge_summary(self, metrics: Optional[Dict]) -> str:
        """Generate knowledge summary for future runs."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        stats = self._count_assets()
        
        lines = [
            f"# Knowledge Summary: {self.target_domain}",
            "",
            f"**Last Updated:** {now}",
            "",
            "## Key Assets",
            f"- Subdomains: {stats['subdomains']}",
            f"- Endpoints: {stats['endpoints']}",
            f"- High-Risk Endpoints: {stats.get('high_risk', 0)}",
            "",
        ]
        
        # Add critical endpoints
        high_risk = self._get_high_risk_endpoints()
        if high_risk:
            lines.append("## Critical Endpoints")
            for ep in high_risk[:5]:
                path = ep.get("properties", {}).get("path", "")
                score = ep.get("properties", {}).get("risk_score", 0)
                lines.append(f"- `{path}` (Risk: {score})")
            lines.append("")
        
        # Add known vulnerabilities
        vulns = [n for n in self.graph.nodes if n.get("type") == "VULNERABILITY"]
        if vulns:
            lines.append("## Theoretical Vulnerabilities")
            for v in vulns[:5]:
                props = v.get("properties", {})
                lines.append(f"- {props.get('type', 'Unknown')}: {props.get('status', 'Unknown')}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _count_assets(self) -> Dict[str, int]:
        """Count assets by type."""
        counts = {
            "subdomains": 0,
            "http_services": 0,
            "endpoints": 0,
            "parameters": 0,
            "dns_records": 0,
            "hypotheses": 0,
            "vulnerabilities": 0,
            "high_risk": 0
        }
        
        for node in self.graph.nodes:
            node_type = node.get("type")
            if node_type == "SUBDOMAIN":
                counts["subdomains"] += 1
            elif node_type == "HTTP_SERVICE":
                counts["http_services"] += 1
            elif node_type == "ENDPOINT":
                counts["endpoints"] += 1
                if node.get("properties", {}).get("risk_score", 0) >= 70:
                    counts["high_risk"] += 1
            elif node_type == "PARAMETER":
                counts["parameters"] += 1
            elif node_type in ("DNS_RECORD", "IP_ADDRESS", "ASN"):
                counts["dns_records"] += 1
            elif node_type == "HYPOTHESIS":
                counts["hypotheses"] += 1
            elif node_type == "VULNERABILITY":
                counts["vulnerabilities"] += 1
        
        return counts
    
    def _generate_attack_plan(self) -> List[str]:
        """Generate attack plan section."""
        lines = ["## 🎯 Attack Plan", ""]
        
        # Check for high-value targets
        attack_paths = [n for n in self.graph.nodes if n.get("type") == "ATTACK_PATH"]
        
        if attack_paths:
            for path in attack_paths[:5]:
                props = path.get("properties", {})
                target = props.get("target", "Unknown")
                score = props.get("score", 0)
                actions = props.get("actions", [])
                lines.append(f"### Target: {target}")
                lines.append(f"**Priority Score:** {score}")
                lines.append("**Suggested Actions:**")
                for action in actions:
                    lines.append(f"- {action}")
                lines.append("")
        else:
            # Check max risk
            max_risk = 0
            for node in self.graph.nodes:
                if node.get("type") == "ENDPOINT":
                    risk = node.get("properties", {}).get("risk_score", 0)
                    max_risk = max(max_risk, risk)
            
            if max_risk < 30:
                lines.append("_No actionable plan generated (only low-risk endpoints detected)._")
            else:
                lines.append("_Attack paths pending generation._")
        
        lines.append("")
        return lines
    
    def _generate_endpoint_intel_section(self) -> List[str]:
        """Generate endpoint intelligence section."""
        lines = ["## 🔍 Endpoint Intelligence (Phase 23)", ""]
        
        # Category distribution
        categories = {}
        endpoints = [n for n in self.graph.nodes if n.get("type") == "ENDPOINT"]
        
        for ep in endpoints:
            cat = ep.get("properties", {}).get("category", "UNKNOWN")
            categories[cat] = categories.get(cat, 0) + 1
        
        lines.append("### Category Distribution")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}**: {count}")
        lines.append("")
        
        # Top 5 by risk
        sorted_eps = sorted(
            endpoints,
            key=lambda x: x.get("properties", {}).get("risk_score", 0),
            reverse=True
        )[:5]
        
        if sorted_eps:
            max_risk = sorted_eps[0].get("properties", {}).get("risk_score", 0) if sorted_eps else 0
            
            if max_risk >= 30:
                lines.append("### ⚠️ Top 5 High-Risk Endpoints")
            else:
                lines.append("### Top 5 Endpoints par Risk Score")
            
            for i, ep in enumerate(sorted_eps, 1):
                props = ep.get("properties", {})
                path = props.get("path", "")
                risk = props.get("risk_score", 0)
                cat = props.get("category", "UNKNOWN")
                behavior = props.get("behavior", "")
                lines.append(f"{i}. `{path}` — Risk: **{risk}**, Category: {cat}, Behavior: {behavior}")
            
            lines.append("")
            
            if max_risk < 30:
                lines.append(f"> Tous les endpoints identifiés présentent un risque faible (max risk_score = {max_risk}).")
                lines.append("> Aucune cible prioritaire n'a été retenue pour la phase offensive.")
        
        lines.append("")
        return lines
    
    def _generate_stack_section(self) -> List[str]:
        """Generate stack & infrastructure section."""
        lines = ["## 🖥️ Stack & Infrastructure", ""]
        
        http_services = [n for n in self.graph.nodes if n.get("type") == "HTTP_SERVICE"]
        
        servers = {}
        frameworks = {}
        
        for svc in http_services:
            props = svc.get("properties", {})
            
            server = props.get("server")
            if server:
                servers[server] = servers.get(server, 0) + 1
            
            framework = props.get("framework")
            if framework:
                frameworks[framework] = frameworks.get(framework, 0) + 1
        
        if servers:
            lines.append("### Servers Detected")
            for server, count in servers.items():
                lines.append(f"- {server}: {count} service(s)")
            lines.append("")
        
        if frameworks:
            lines.append("### Frameworks Detected")
            for fw, count in frameworks.items():
                lines.append(f"- {fw}: {count} service(s)")
            lines.append("")
        
        if not servers and not frameworks:
            lines.append("_No stack information detected._")
            lines.append("")
        
        return lines
    
    def _generate_vuln_section(self) -> List[str]:
        """Generate vulnerabilities section."""
        lines = ["## 🔴 Vulnerabilities & Theoretical Proofs", ""]
        
        vulns = [n for n in self.graph.nodes if n.get("type") == "VULNERABILITY"]
        
        if vulns:
            for v in vulns[:10]:
                props = v.get("properties", {})
                vuln_type = props.get("type", "Unknown")
                status = props.get("status", "Unknown")
                confidence = props.get("confidence", 0)
                evidence = props.get("evidence", "")
                
                lines.append(f"### {vuln_type}")
                lines.append(f"- **Status:** {status}")
                lines.append(f"- **Confidence:** {confidence:.0%}")
                if evidence:
                    lines.append(f"- **Evidence:** {evidence[:200]}")
                lines.append("")
        else:
            lines.append("_No theoretical vulnerabilities detected._")
            lines.append("")
        
        return lines
    
    def _get_high_risk_endpoints(self) -> List[Dict]:
        """Get high-risk endpoints sorted by risk score."""
        endpoints = [n for n in self.graph.nodes if n.get("type") == "ENDPOINT"]
        return sorted(
            [e for e in endpoints if e.get("properties", {}).get("risk_score", 0) >= 50],
            key=lambda x: x.get("properties", {}).get("risk_score", 0),
            reverse=True
        )
