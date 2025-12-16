"""Reporter - Phase 6 Report Generation Service

Generates comprehensive mission reports including:
- Red Team Mission Report (markdown)
- Mission Summary
- Knowledge Summary (for future runs)
- Asset Graph Export (JSON)
- Metrics Export (JSON)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
import httpx
import json
import os
import hashlib

logger = structlog.get_logger()
app = FastAPI(title="Reporter", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GRAPH_SERVICE = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8000")


class ExecuteRequest(BaseModel):
    mission_id: str
    target_domain: str
    mode: str
    options: Dict[str, Any] = {}


# ════════════════════════════════════════════════════════════════════════════════
# GRAPH SERVICE COMMUNICATION
# ════════════════════════════════════════════════════════════════════════════════

async def fetch_graph_data(mission_id: str) -> Dict[str, Any]:
    """Fetch all nodes and edges for a mission from graph-service."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Fetch nodes
            nodes_resp = await client.get(
                f"{GRAPH_SERVICE}/api/v1/nodes",
                params={"mission_id": mission_id, "limit": 10000}
            )
            nodes_resp.raise_for_status()
            nodes = nodes_resp.json().get("nodes", [])

            # Fetch edges
            edges_resp = await client.get(
                f"{GRAPH_SERVICE}/api/v1/edges",
                params={"mission_id": mission_id, "limit": 50000}
            )
            edges_resp.raise_for_status()
            edges = edges_resp.json().get("edges", [])

            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            logger.error("failed_to_fetch_graph", error=str(e))
            return {"nodes": [], "edges": []}


async def publish_node(mission_id: str, node_type: str, properties: Dict, label: str) -> Optional[str]:
    """Publish a node to graph-service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {
                "mission_id": mission_id,
                "type": node_type,
                "label": label,
                "properties": properties
            }
            resp = await client.post(f"{GRAPH_SERVICE}/api/v1/nodes", json=payload)
            resp.raise_for_status()
            return resp.json().get("id")
        except Exception as e:
            logger.error("failed_to_publish_node", error=str(e))
            return None


async def publish_edge(mission_id: str, source_id: str, target_id: str, edge_type: str, properties: Dict = None) -> Optional[str]:
    """Publish an edge to graph-service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {
                "mission_id": mission_id,
                "source_id": source_id,
                "target_id": target_id,
                "type": edge_type,
                "properties": properties or {}
            }
            resp = await client.post(f"{GRAPH_SERVICE}/api/v1/edges", json=payload)
            resp.raise_for_status()
            return resp.json().get("id")
        except Exception as e:
            logger.error("failed_to_publish_edge", error=str(e))
            return None


# ════════════════════════════════════════════════════════════════════════════════
# ASSET COUNTING & STATISTICS
# ════════════════════════════════════════════════════════════════════════════════

def count_assets(nodes: List[Dict]) -> Dict[str, int]:
    """Count assets by type."""
    counts = {
        "subdomains": 0,
        "http_services": 0,
        "endpoints": 0,
        "parameters": 0,
        "dns_records": 0,
        "hypotheses": 0,
        "vulnerabilities": 0,
        "high_risk": 0,
        "js_files": 0,
        "secrets": 0,
        "attack_paths": 0
    }

    for node in nodes:
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
        elif node_type == "JS_FILE":
            counts["js_files"] += 1
        elif node_type == "SECRET":
            counts["secrets"] += 1
        elif node_type == "ATTACK_PATH":
            counts["attack_paths"] += 1

    return counts


def get_high_risk_endpoints(nodes: List[Dict], threshold: int = 50) -> List[Dict]:
    """Get high-risk endpoints sorted by risk score."""
    endpoints = [n for n in nodes if n.get("type") == "ENDPOINT"]
    high_risk = [e for e in endpoints if e.get("properties", {}).get("risk_score", 0) >= threshold]
    return sorted(high_risk, key=lambda x: x.get("properties", {}).get("risk_score", 0), reverse=True)


def get_endpoint_categories(nodes: List[Dict]) -> Dict[str, int]:
    """Get endpoint category distribution."""
    categories = {}
    endpoints = [n for n in nodes if n.get("type") == "ENDPOINT"]
    for ep in endpoints:
        cat = ep.get("properties", {}).get("category", "UNKNOWN")
        categories[cat] = categories.get(cat, 0) + 1
    return categories


def get_stack_info(nodes: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Extract server and framework information from HTTP services."""
    servers = {}
    frameworks = {}
    technologies = {}

    http_services = [n for n in nodes if n.get("type") == "HTTP_SERVICE"]
    for svc in http_services:
        props = svc.get("properties", {})

        server = props.get("server")
        if server:
            servers[server] = servers.get(server, 0) + 1

        framework = props.get("framework")
        if framework:
            frameworks[framework] = frameworks.get(framework, 0) + 1

        techs = props.get("technologies", [])
        if isinstance(techs, list):
            for tech in techs:
                technologies[tech] = technologies.get(tech, 0) + 1

    return {"servers": servers, "frameworks": frameworks, "technologies": technologies}


# ════════════════════════════════════════════════════════════════════════════════
# REPORT GENERATION - MARKDOWN SECTIONS
# ════════════════════════════════════════════════════════════════════════════════

def normalize_label(label: str) -> str:
    """Normalize URL labels for display."""
    if not label:
        return "Unknown"
    if label.startswith("http://"):
        return label.replace("http://", "") + " (HTTP)"
    if label.startswith("https://"):
        return label.replace("https://", "") + " (HTTPS)"
    return label


def generate_executive_summary(domain: str, stats: Dict, vulns: List[Dict], attack_paths: List[Dict]) -> str:
    """Generate executive summary section."""
    high_vulns = [v for v in vulns if v.get("properties", {}).get("severity") in ("CRITICAL", "HIGH")]
    confirmed_vulns = [v for v in vulns if v.get("properties", {}).get("confirmed")]

    status = "CRITICAL ISSUES FOUND" if confirmed_vulns else "RECONNAISSANCE COMPLETE"
    status_icon = "🔴" if confirmed_vulns else "🟢"

    return f"""## 1. Executive Summary
**Mission Status:** {status_icon} {status}

The automated reconnaissance and preliminary offensive phase against **{domain}** has been completed.
The system identified **{stats['subdomains']}** subdomains and **{stats['endpoints']}** endpoints.

**Key Findings:**
- **Vulnerabilities:** {stats['vulnerabilities']} detected ({len(high_vulns)} High/Critical)
- **Confirmed Exploitable:** {len(confirmed_vulns)} confirmed via safe probes
- **Attack Paths:** {stats['attack_paths']} potential attack paths identified
- **High-Risk Endpoints:** {stats['high_risk']} requiring immediate attention
- **Secrets/Credentials Found:** {stats['secrets']}
"""


def generate_infrastructure_section(domain: str, stats: Dict, attack_paths: List[Dict]) -> str:
    """Generate infrastructure overview section."""
    lines = [
        "## 2. Infrastructure Overview",
        "**Attack Surface:**",
        f"- Subdomains: {stats['subdomains']}",
        f"- HTTP Services: {stats['http_services']}",
        f"- Endpoints: {stats['endpoints']}",
        f"- Parameters: {stats['parameters']}",
        f"- JS Files Analyzed: {stats['js_files']}",
        "",
        "### Top Attack Paths",
    ]

    if attack_paths:
        for i, path in enumerate(attack_paths[:5], 1):
            props = path.get("properties", {})
            target = props.get("target", "Unknown")
            score = props.get("score", 0)
            reasons = props.get("reasons", [])
            lines.append(f"{i}. **{normalize_label(target)}** (Score: {score})")
            if reasons:
                for reason in reasons[:3]:
                    lines.append(f"   - {reason}")
    else:
        lines.append("_No attack paths generated yet._")

    lines.append("")
    return "\n".join(lines)


def generate_endpoint_intel_section(nodes: List[Dict]) -> str:
    """Generate endpoint intelligence section."""
    lines = ["## 3. Endpoint Intelligence (Phase 23)", ""]

    categories = get_endpoint_categories(nodes)
    endpoints = [n for n in nodes if n.get("type") == "ENDPOINT"]

    # Category distribution
    lines.append("### Category Distribution")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {count}")
    lines.append("")

    # Top 5 by risk
    sorted_eps = sorted(
        endpoints,
        key=lambda x: x.get("properties", {}).get("risk_score", 0),
        reverse=True
    )[:10]

    if sorted_eps:
        max_risk = sorted_eps[0].get("properties", {}).get("risk_score", 0)

        if max_risk >= 50:
            lines.append("### ⚠️ High-Risk Endpoints")
        else:
            lines.append("### Top Endpoints by Risk Score")

        lines.append("| # | Path | Risk | Category | Behavior | Parameters |")
        lines.append("|---|------|------|----------|----------|------------|")

        for i, ep in enumerate(sorted_eps, 1):
            props = ep.get("properties", {})
            path = props.get("path", "")[:40]
            risk = props.get("risk_score", 0)
            cat = props.get("category", "UNKNOWN")
            behavior = props.get("behavior_hint", "")
            params = len(props.get("parameters", []))
            lines.append(f"| {i} | `{path}` | **{risk}** | {cat} | {behavior} | {params} |")

        lines.append("")

        if max_risk < 30:
            lines.append(f"> All endpoints present low risk (max risk_score = {max_risk}).")
            lines.append("> No priority targets retained for offensive phase.")

    lines.append("")
    return "\n".join(lines)


def generate_vulnerability_section(nodes: List[Dict]) -> str:
    """Generate vulnerabilities section."""
    lines = ["## 4. Vulnerability Analysis", ""]

    vulns = [n for n in nodes if n.get("type") == "VULNERABILITY"]
    hypotheses = [n for n in nodes if n.get("type") == "HYPOTHESIS"]

    if vulns:
        lines.append("### Detected Vulnerabilities")
        lines.append("| Severity | Type | Status | Confidence | Evidence |")
        lines.append("|----------|------|--------|------------|----------|")

        for v in sorted(vulns, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(x.get("properties", {}).get("severity", "LOW"), 4))[:15]:
            props = v.get("properties", {})
            sev = props.get("severity", "LOW")
            vuln_type = props.get("type", "Unknown")
            status = props.get("status", "Theoretical")
            conf = props.get("confidence", 0)
            evidence = props.get("evidence", "")[:50]
            confirmed = "✅" if props.get("confirmed") else "❓"
            lines.append(f"| **{sev}** | {vuln_type} | {status} {confirmed} | {conf:.0%} | {evidence} |")
        lines.append("")

    if hypotheses:
        lines.append("### Theoretical Hypotheses")
        for h in hypotheses[:10]:
            props = h.get("properties", {})
            hyp_type = props.get("type", "Unknown")
            conf = props.get("confidence", 0)
            evidence = props.get("evidence", "")
            lines.append(f"- **{hyp_type}** (Confidence: {conf:.0%})")
            if evidence:
                lines.append(f"  Evidence: {evidence[:100]}")
        lines.append("")

    if not vulns and not hypotheses:
        lines.append("_No significant vulnerabilities detected during this phase._")
        lines.append("")

    return "\n".join(lines)


def generate_stack_section(nodes: List[Dict]) -> str:
    """Generate stack & infrastructure section."""
    lines = ["## 5. Stack & Infrastructure", ""]

    stack_info = get_stack_info(nodes)

    if stack_info["servers"]:
        lines.append("### Servers Detected")
        for server, count in stack_info["servers"].items():
            lines.append(f"- {server}: {count} service(s)")
        lines.append("")

    if stack_info["frameworks"]:
        lines.append("### Frameworks Detected")
        for fw, count in stack_info["frameworks"].items():
            lines.append(f"- {fw}: {count} service(s)")
        lines.append("")

    if stack_info["technologies"]:
        lines.append("### Technologies Detected")
        for tech, count in sorted(stack_info["technologies"].items(), key=lambda x: -x[1])[:15]:
            lines.append(f"- {tech}: {count}")
        lines.append("")

    if not any(stack_info.values()):
        lines.append("_No stack information detected._")
        lines.append("")

    return "\n".join(lines)


def generate_secrets_section(nodes: List[Dict]) -> str:
    """Generate secrets/credentials section."""
    lines = ["## 6. Secrets & Credentials", ""]

    secrets = [n for n in nodes if n.get("type") == "SECRET"]

    if secrets:
        lines.append("⚠️ **WARNING: Sensitive data detected!**")
        lines.append("")
        lines.append("| Type | Source | Severity |")
        lines.append("|------|--------|----------|")

        for s in secrets[:20]:
            props = s.get("properties", {})
            secret_type = props.get("type", "Unknown")
            source = props.get("source", "Unknown")[:30]
            severity = props.get("severity", "MEDIUM")
            lines.append(f"| {secret_type} | {source} | **{severity}** |")
        lines.append("")
    else:
        lines.append("_No exposed secrets detected._")
        lines.append("")

    return "\n".join(lines)


def generate_recommendations(stats: Dict, high_vulns_count: int) -> str:
    """Generate recommendations section."""
    lines = ["## 7. Recommendations", ""]

    if high_vulns_count > 0:
        lines.append(f"1. **Immediate Action:** Patch {high_vulns_count} Critical/High vulnerabilities")

    if stats["secrets"] > 0:
        lines.append(f"2. **URGENT:** Rotate {stats['secrets']} exposed credentials/secrets")

    if stats["high_risk"] > 0:
        lines.append(f"3. **Priority:** Review {stats['high_risk']} high-risk endpoints")

    lines.append("4. **Review:** Manual verification of unconfirmed findings")
    lines.append("5. **Hardening:** Review exposed parameters and legacy endpoints")
    lines.append("6. **Monitoring:** Set up alerts for detected attack surfaces")

    lines.append("")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════════
# MAIN REPORT BUILDERS
# ════════════════════════════════════════════════════════════════════════════════

def build_red_team_report(domain: str, mode: str, run_id: str, graph_data: Dict) -> str:
    """Build comprehensive Red Team Mission Report."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    nodes = graph_data.get("nodes", [])

    stats = count_assets(nodes)
    vulns = [n for n in nodes if n.get("type") == "VULNERABILITY"]
    attack_paths = [n for n in nodes if n.get("type") == "ATTACK_PATH"]
    high_vulns = [v for v in vulns if v.get("properties", {}).get("severity") in ("CRITICAL", "HIGH")]

    # Sort attack paths by score
    attack_paths = sorted(attack_paths, key=lambda x: x.get("properties", {}).get("score", 0), reverse=True)

    report = f"""# 🚩 Red Team Mission Report: {domain}

**Date:** {now}
**Mode:** {mode}
**Run ID:** {run_id}
**Confidentiality:** INTERNAL USE ONLY

---

{generate_executive_summary(domain, stats, vulns, attack_paths)}
---

{generate_infrastructure_section(domain, stats, attack_paths)}
---

{generate_endpoint_intel_section(nodes)}
---

{generate_vulnerability_section(nodes)}
---

{generate_stack_section(nodes)}
---

{generate_secrets_section(nodes)}
---

{generate_recommendations(stats, len(high_vulns))}
---

## 8. Asset Statistics Summary

| Asset Type | Count |
|------------|-------|
| Subdomains | {stats['subdomains']} |
| HTTP Services | {stats['http_services']} |
| Endpoints | {stats['endpoints']} |
| Parameters | {stats['parameters']} |
| JS Files | {stats['js_files']} |
| DNS/IP/ASN | {stats['dns_records']} |
| Hypotheses | {stats['hypotheses']} |
| Vulnerabilities | {stats['vulnerabilities']} |
| Secrets | {stats['secrets']} |
| Attack Paths | {stats['attack_paths']} |

---

*Generated by Recon-Gotham AI - Automated Red Team Reconnaissance*
"""
    return report


def build_knowledge_summary(domain: str, run_id: str, graph_data: Dict) -> str:
    """Build knowledge summary for future runs."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    nodes = graph_data.get("nodes", [])
    stats = count_assets(nodes)

    lines = [
        f"# Knowledge Summary: {domain}",
        "",
        f"**Last Updated:** {now}",
        f"**Run ID:** {run_id}",
        "",
        "## Key Assets",
        f"- Subdomains: {stats['subdomains']}",
        f"- HTTP Services: {stats['http_services']}",
        f"- Endpoints: {stats['endpoints']}",
        f"- High-Risk Endpoints: {stats['high_risk']}",
        f"- Vulnerabilities: {stats['vulnerabilities']}",
        "",
    ]

    # Add critical endpoints
    high_risk = get_high_risk_endpoints(nodes, threshold=50)
    if high_risk:
        lines.append("## Critical Endpoints")
        for ep in high_risk[:10]:
            props = ep.get("properties", {})
            path = props.get("path", "")
            score = props.get("risk_score", 0)
            cat = props.get("category", "")
            lines.append(f"- `{path}` (Risk: {score}, Category: {cat})")
        lines.append("")

    # Add attack paths
    attack_paths = [n for n in nodes if n.get("type") == "ATTACK_PATH"]
    if attack_paths:
        lines.append("## Top Attack Paths")
        for path in sorted(attack_paths, key=lambda x: x.get("properties", {}).get("score", 0), reverse=True)[:5]:
            props = path.get("properties", {})
            target = props.get("target", "Unknown")
            score = props.get("score", 0)
            lines.append(f"- {target} (Score: {score})")
        lines.append("")

    # Add vulnerabilities
    vulns = [n for n in nodes if n.get("type") == "VULNERABILITY"]
    if vulns:
        lines.append("## Known Vulnerabilities")
        for v in vulns[:10]:
            props = v.get("properties", {})
            vuln_type = props.get("type", "Unknown")
            status = props.get("status", "Unknown")
            severity = props.get("severity", "UNKNOWN")
            lines.append(f"- [{severity}] {vuln_type}: {status}")
        lines.append("")

    return "\n".join(lines)


def build_metrics_json(domain: str, run_id: str, graph_data: Dict, duration: float) -> Dict:
    """Build metrics JSON export."""
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    stats = count_assets(nodes)

    # Edge type distribution
    edge_types = {}
    for edge in edges:
        et = edge.get("type", "UNKNOWN")
        edge_types[et] = edge_types.get(et, 0) + 1

    # Endpoint categories
    categories = get_endpoint_categories(nodes)

    # Risk score distribution
    risk_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    endpoints = [n for n in nodes if n.get("type") == "ENDPOINT"]
    for ep in endpoints:
        risk = ep.get("properties", {}).get("risk_score", 0)
        if risk >= 80:
            risk_distribution["critical"] += 1
        elif risk >= 50:
            risk_distribution["high"] += 1
        elif risk >= 30:
            risk_distribution["medium"] += 1
        else:
            risk_distribution["low"] += 1

    return {
        "domain": domain,
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "duration_seconds": duration,
        "assets": stats,
        "edge_types": edge_types,
        "endpoint_categories": categories,
        "risk_distribution": risk_distribution,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }


# ════════════════════════════════════════════════════════════════════════════════
# REPORTER RUNNER
# ════════════════════════════════════════════════════════════════════════════════

class ReporterRunner:
    """Main reporter runner."""

    def __init__(self, mission_id: str, target_domain: str, mode: str, options: Dict):
        self.mission_id = mission_id
        self.target_domain = target_domain
        self.mode = mode
        self.options = options
        self.run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    async def run(self) -> Dict:
        """Execute reporting phase."""
        start_time = datetime.utcnow()
        logger.info("reporter_started", mission_id=self.mission_id, domain=self.target_domain)

        results = {
            "reports_generated": [],
            "report_nodes": [],
            "summary": {}
        }

        # Step 1: Fetch all graph data
        logger.info("fetching_graph_data", mission_id=self.mission_id)
        graph_data = await fetch_graph_data(self.mission_id)

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        logger.info("graph_data_fetched", nodes=len(nodes), edges=len(edges))

        if not nodes:
            logger.warning("no_graph_data", mission_id=self.mission_id)
            return {
                "reports_generated": [],
                "report_nodes": [],
                "summary": {"error": "No graph data found for mission"}
            }

        # Calculate stats
        stats = count_assets(nodes)
        results["summary"] = stats

        # Step 2: Generate Red Team Report (Markdown)
        logger.info("generating_red_team_report")
        red_team_report = build_red_team_report(
            self.target_domain,
            self.mode,
            self.run_id,
            graph_data
        )

        # Publish report node
        report_hash = hashlib.md5(red_team_report.encode()).hexdigest()[:8]
        report_node_id = await publish_node(
            self.mission_id,
            "REPORT",
            {
                "type": "red_team_report",
                "format": "markdown",
                "filename": f"{self.target_domain}_red_team_report.md",
                "content": red_team_report,
                "content_hash": report_hash,
                "generated_at": datetime.utcnow().isoformat(),
                "run_id": self.run_id,
                "stats": stats
            },
            f"Red Team Report - {self.target_domain}"
        )

        if report_node_id:
            results["reports_generated"].append(f"{self.target_domain}_red_team_report.md")
            results["report_nodes"].append(report_node_id)

        # Step 3: Generate Knowledge Summary
        logger.info("generating_knowledge_summary")
        knowledge_summary = build_knowledge_summary(self.target_domain, self.run_id, graph_data)

        knowledge_node_id = await publish_node(
            self.mission_id,
            "REPORT",
            {
                "type": "knowledge_summary",
                "format": "markdown",
                "filename": f"{self.target_domain}_knowledge_summary.md",
                "content": knowledge_summary,
                "generated_at": datetime.utcnow().isoformat(),
                "run_id": self.run_id
            },
            f"Knowledge Summary - {self.target_domain}"
        )

        if knowledge_node_id:
            results["reports_generated"].append(f"{self.target_domain}_knowledge_summary.md")
            results["report_nodes"].append(knowledge_node_id)

        # Step 4: Generate Graph Export (JSON)
        logger.info("generating_graph_export")
        graph_export = {
            "domain": self.target_domain,
            "run_id": self.run_id,
            "exported_at": datetime.utcnow().isoformat(),
            "nodes": nodes,
            "edges": edges,
            "stats": stats
        }

        graph_node_id = await publish_node(
            self.mission_id,
            "REPORT",
            {
                "type": "graph_export",
                "format": "json",
                "filename": f"{self.target_domain}_asset_graph.json",
                "content": json.dumps(graph_export),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "generated_at": datetime.utcnow().isoformat(),
                "run_id": self.run_id
            },
            f"Asset Graph Export - {self.target_domain}"
        )

        if graph_node_id:
            results["reports_generated"].append(f"{self.target_domain}_asset_graph.json")
            results["report_nodes"].append(graph_node_id)

        # Step 5: Generate Metrics Export (JSON)
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info("generating_metrics_export")

        metrics = build_metrics_json(self.target_domain, self.run_id, graph_data, duration)

        metrics_node_id = await publish_node(
            self.mission_id,
            "REPORT",
            {
                "type": "metrics_export",
                "format": "json",
                "filename": f"{self.target_domain}_{self.run_id}_metrics.json",
                "content": json.dumps(metrics),
                "generated_at": datetime.utcnow().isoformat(),
                "run_id": self.run_id,
                "metrics": metrics
            },
            f"Metrics Export - {self.target_domain}"
        )

        if metrics_node_id:
            results["reports_generated"].append(f"{self.target_domain}_{self.run_id}_metrics.json")
            results["report_nodes"].append(metrics_node_id)

        # Create edges linking reports to mission
        # Find the mission/domain root node
        domain_nodes = [n for n in nodes if n.get("type") == "SUBDOMAIN" and n.get("label") == self.target_domain]
        if domain_nodes and results["report_nodes"]:
            root_node_id = domain_nodes[0].get("id")
            for report_id in results["report_nodes"]:
                await publish_edge(
                    self.mission_id,
                    root_node_id,
                    report_id,
                    "HAS_REPORT",
                    {"generated_at": datetime.utcnow().isoformat()}
                )

        logger.info(
            "reporter_completed",
            mission_id=self.mission_id,
            reports=len(results["reports_generated"]),
            duration=duration
        )

        return results


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "reporter"}


@app.post("/api/v1/execute")
async def execute(request: ExecuteRequest):
    """Generate comprehensive mission reports."""
    logger.info("reporting_started", mission_id=request.mission_id, domain=request.target_domain)

    start = datetime.utcnow()

    try:
        runner = ReporterRunner(
            request.mission_id,
            request.target_domain,
            request.mode,
            request.options
        )
        results = await runner.run()

        duration = (datetime.utcnow() - start).total_seconds()

        return {
            "phase": "reporting",
            "status": "completed",
            "duration": duration,
            "results": results
        }
    except Exception as e:
        logger.error("reporting_failed", error=str(e))
        duration = (datetime.utcnow() - start).total_seconds()
        return {
            "phase": "reporting",
            "status": "error",
            "duration": duration,
            "error": str(e)
        }


@app.get("/api/v1/reports/{mission_id}")
async def get_reports(mission_id: str):
    """Get all reports for a mission."""
    graph_data = await fetch_graph_data(mission_id)
    nodes = graph_data.get("nodes", [])

    reports = [n for n in nodes if n.get("type") == "REPORT"]

    return {
        "mission_id": mission_id,
        "reports": [
            {
                "id": r.get("id"),
                "type": r.get("properties", {}).get("type"),
                "format": r.get("properties", {}).get("format"),
                "filename": r.get("properties", {}).get("filename"),
                "generated_at": r.get("properties", {}).get("generated_at")
            }
            for r in reports
        ]
    }


@app.get("/api/v1/reports/{mission_id}/{report_type}")
async def get_report_content(mission_id: str, report_type: str):
    """Get specific report content."""
    graph_data = await fetch_graph_data(mission_id)
    nodes = graph_data.get("nodes", [])

    reports = [n for n in nodes if n.get("type") == "REPORT"]

    for r in reports:
        if r.get("properties", {}).get("type") == report_type:
            return {
                "mission_id": mission_id,
                "type": report_type,
                "content": r.get("properties", {}).get("content"),
                "filename": r.get("properties", {}).get("filename"),
                "generated_at": r.get("properties", {}).get("generated_at")
            }

    return {"error": f"Report type '{report_type}' not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
