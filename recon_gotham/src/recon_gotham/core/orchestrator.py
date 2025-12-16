"""
Orchestrator Service - V3.0 Main Orchestration
Coordinates all pipelines and manages mission execution.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from recon_gotham.core.asset_graph import AssetGraph
from recon_gotham.pipelines.osint_pipeline import OsintPipeline
from recon_gotham.pipelines.recon_pipeline import ReconPipeline
from recon_gotham.pipelines.safety_net import SafetyNetPipeline
from recon_gotham.pipelines.endpoint_intel_pipeline import EndpointIntelPipeline
from recon_gotham.pipelines.verification_pipeline import VerificationPipeline
from recon_gotham.pipelines.reporting_service import ReportingService


@dataclass
class Settings:
    """Mission settings."""
    target_domain: str
    mode: str = "AGGRESSIVE"
    output_dir: str = "recon_gotham/output"
    knowledge_dir: str = "recon_gotham/knowledge"
    
    # Budgets
    max_targets: int = 50
    http_max_workers: int = 5
    request_timeout: int = 15
    verify_ssl: bool = False
    
    # Thresholds
    min_subdomains_for_active: int = 0
    min_risk_for_active_scan: int = 30
    min_risk_for_verification: int = 40
    continue_on_low_surface: bool = True
    
    # Features
    active_verification_enabled: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "target_domain": self.target_domain,
            "mode": self.mode,
            "output_dir": self.output_dir,
            "knowledge_dir": self.knowledge_dir,
            "max_targets": self.max_targets,
            "http_max_workers": self.http_max_workers,
            "request_timeout": self.request_timeout,
            "verify_ssl": self.verify_ssl,
            "min_subdomains_for_active": self.min_subdomains_for_active,
            "min_risk_for_active_scan": self.min_risk_for_active_scan,
            "min_risk_for_verification": self.min_risk_for_verification,
            "continue_on_low_surface": self.continue_on_low_surface,
            "active_verification_enabled": self.active_verification_enabled
        }


@dataclass
class MissionMetrics:
    """Metrics collected during mission execution."""
    run_id: str
    target_domain: str
    mode: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Phase durations (seconds)
    osint_duration: float = 0
    recon_duration: float = 0
    endpoint_intel_duration: float = 0
    verification_duration: float = 0
    reporting_duration: float = 0
    
    # Counts
    subdomains_found: int = 0
    http_services_found: int = 0
    endpoints_found: int = 0
    endpoints_enriched: int = 0
    parameters_found: int = 0
    hypotheses_generated: int = 0
    vulnerabilities_theoretical: int = 0
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "target_domain": self.target_domain,
            "mode": self.mode,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration": (self.end_time - self.start_time).total_seconds() if self.end_time else None,
            "phase_durations": {
                "osint": self.osint_duration,
                "recon": self.recon_duration,
                "endpoint_intel": self.endpoint_intel_duration,
                "verification": self.verification_duration,
                "reporting": self.reporting_duration
            },
            "counts": {
                "subdomains": self.subdomains_found,
                "http_services": self.http_services_found,
                "endpoints": self.endpoints_found,
                "endpoints_enriched": self.endpoints_enriched,
                "parameters": self.parameters_found,
                "hypotheses": self.hypotheses_generated,
                "vulnerabilities": self.vulnerabilities_theoretical
            },
            "errors": self.errors
        }


class OrchestratorService:
    """
    V3.0 Orchestrator Service.
    
    Coordinates all pipelines in the correct order:
    1. OSINT Pipeline (passive discovery)
    2. Safety Net (gate check)
    3. Recon Pipeline (active recon)
    4. Endpoint Intel Pipeline (Phase 23)
    5. Verification Pipeline (Phase 24/25)
    6. Reporting Service
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.run_id = self._generate_run_id()
        self.graph = AssetGraph(target_domain=settings.target_domain)
        self.metrics = MissionMetrics(
            run_id=self.run_id,
            target_domain=settings.target_domain,
            mode=settings.mode
        )
        
        # Initialize pipelines
        settings_dict = settings.to_dict()
        self.osint_pipeline = OsintPipeline(self.graph, settings_dict, self.run_id)
        self.recon_pipeline = ReconPipeline(self.graph, settings_dict, self.run_id)
        self.safety_net = SafetyNetPipeline(self.graph, settings_dict, self.run_id)
        self.endpoint_intel = EndpointIntelPipeline(self.graph, settings_dict, self.run_id)
        self.verification = VerificationPipeline(self.graph, settings_dict, self.run_id)
        self.reporting = ReportingService(self.graph, settings_dict, self.run_id)
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{timestamp}_{short_uuid}"
    
    def run_mission(self, agents: Dict = None, tasks: Dict = None) -> MissionMetrics:
        """
        Execute the complete mission.
        
        Args:
            agents: CrewAI agents dictionary (optional, for OSINT phase)
            tasks: CrewAI tasks dictionary (optional, for OSINT phase)
            
        Returns:
            MissionMetrics with execution statistics
        """
        print(f"[+] Mission Mode: {self.settings.mode}")
        print(f"[+] Run ID: {self.run_id}")
        
        import time
        
        # === Phase 1: OSINT Pipeline ===
        print("\n[*] Phase 1: OSINT Pipeline (Passive Discovery)...")
        start = time.time()
        
        if agents and tasks:
            osint_result = self.osint_pipeline.execute(agents, tasks)
            self.metrics.subdomains_found = osint_result.subdomains_found
            self.metrics.errors.extend(osint_result.errors)
        
        # Also run Wayback
        subdomains = [n.get("id") for n in self.graph.nodes if n.get("type") == "SUBDOMAIN"]
        if subdomains:
            wayback_count = self.osint_pipeline.run_wayback(subdomains[:10])
            print(f"    - Wayback found {wayback_count} historical endpoints")
        
        self.metrics.osint_duration = time.time() - start
        print(f"    - Duration: {self.metrics.osint_duration:.1f}s")
        
        # === Phase 2: Safety Net Gate Check ===
        print("\n[*] Phase 2: Gate Check...")
        gate_result = self.safety_net.gate_check()
        print(f"    - {gate_result.message}")
        
        if not gate_result.should_continue:
            print("[-] Aborting: Insufficient surface")
            # Generate minimal report
            self._generate_minimal_report()
            return self.metrics
        
        # === Phase 3: Recon Pipeline ===
        print("\n[*] Phase 3: Recon Pipeline (Active)...")
        start = time.time()
        
        recon_result = self.recon_pipeline.execute(subdomains)
        self.metrics.http_services_found = recon_result.http_services_found
        self.metrics.endpoints_found = self.metrics.endpoints_found + recon_result.endpoints_crawled + recon_result.js_endpoints
        self.metrics.errors.extend(recon_result.errors)
        
        self.metrics.recon_duration = time.time() - start
        print(f"    - HTTP Services: {recon_result.http_services_found}")
        print(f"    - Endpoints: {recon_result.endpoints_crawled + recon_result.js_endpoints}")
        print(f"    - Duration: {self.metrics.recon_duration:.1f}s")
        
        # === Phase 4: Endpoint Intelligence (Phase 23) ===
        print("\n[*] Phase 4: Endpoint Intelligence (Phase 23)...")
        start = time.time()
        
        intel_result = self.endpoint_intel.execute()
        self.metrics.endpoints_enriched = intel_result.endpoints_enriched
        self.metrics.parameters_found = intel_result.parameters_found
        self.metrics.hypotheses_generated = intel_result.hypotheses_generated
        self.metrics.errors.extend(intel_result.errors)
        
        self.metrics.endpoint_intel_duration = time.time() - start
        print(f"    - Enriched: {intel_result.endpoints_enriched}")
        print(f"    - Parameters: {intel_result.parameters_found}")
        print(f"    - Hypotheses: {intel_result.hypotheses_generated}")
        print(f"    - High Risk: {intel_result.high_risk_count}")
        print(f"    - Duration: {self.metrics.endpoint_intel_duration:.1f}s")
        
        # === Phase 5: Verification (Phase 24/25) ===
        print("\n[*] Phase 5: Verification Pipeline (Phase 24/25)...")
        start = time.time()
        
        verif_result = self.verification.execute()
        self.metrics.vulnerabilities_theoretical = verif_result.vulnerabilities_theoretical
        self.metrics.errors.extend(verif_result.errors)
        
        self.metrics.verification_duration = time.time() - start
        print(f"    - Services Analyzed: {verif_result.services_analyzed}")
        print(f"    - Tests Performed: {verif_result.tests_performed}")
        print(f"    - Theoretical Vulns: {verif_result.vulnerabilities_theoretical}")
        print(f"    - Duration: {self.metrics.verification_duration:.1f}s")
        
        # === Phase 6: Reporting ===
        print("\n[*] Phase 6: Generating Reports...")
        start = time.time()
        
        report_result = self.reporting.generate_report(self.metrics.to_dict())
        
        self.metrics.reporting_duration = time.time() - start
        self.metrics.end_time = datetime.now()
        
        print(f"    - Summary: {report_result.summary_path}")
        print(f"    - Graph: {report_result.graph_path}")
        if report_result.metrics_path:
            print(f"    - Metrics: {report_result.metrics_path}")
        
        print("\n[+] Mission Complete.")
        
        return self.metrics
    
    def _generate_minimal_report(self):
        """Generate minimal report when aborting early."""
        self.metrics.end_time = datetime.now()
        self.reporting.generate_report(self.metrics.to_dict())
        print("[+] Minimal report generated.")
