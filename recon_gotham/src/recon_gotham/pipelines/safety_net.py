"""
Safety Net Pipeline - Fallback and Recovery
Handles edge cases, error recovery, and safety checks.
"""

from typing import Dict, List
from dataclasses import dataclass

from recon_gotham.core.asset_graph import AssetGraph


@dataclass
class SafetyCheckResult:
    """Result of safety check."""
    passed: bool
    subdomains_count: int
    http_services_count: int
    message: str
    should_continue: bool


class SafetyNetPipeline:
    """
    Safety Net Pipeline - Gate Check and Recovery.
    
    Responsibilities:
    - Gate check (minimum subdomains before active phase)
    - Error recovery when tools fail
    - Fallback strategies when primary tools return empty
    - Anti-hallucination validation
    """
    
    def __init__(self, graph: AssetGraph, settings: Dict, run_id: str):
        self.graph = graph
        self.settings = settings
        self.run_id = run_id
        self.target_domain = settings.get("target_domain")
        self.min_subdomains = settings.get("min_subdomains_for_active", 0)
    
    def gate_check(self) -> SafetyCheckResult:
        """
        Check if we have enough data to proceed to active phase.
        
        Returns:
            SafetyCheckResult with decision
        """
        # Count subdomains
        subdomains = [n for n in self.graph.nodes if n.get("type") == "SUBDOMAIN"]
        subdomain_count = len(subdomains)
        
        # Count HTTP services
        http_services = [n for n in self.graph.nodes if n.get("type") == "HTTP_SERVICE"]
        http_count = len(http_services)
        
        # Decision logic
        if subdomain_count == 0:
            return SafetyCheckResult(
                passed=False,
                subdomains_count=0,
                http_services_count=http_count,
                message="ZERO SURFACE DETECTED - No subdomains found",
                should_continue=False
            )
        
        if subdomain_count < self.min_subdomains:
            return SafetyCheckResult(
                passed=False,
                subdomains_count=subdomain_count,
                http_services_count=http_count,
                message=f"Insufficient subdomains ({subdomain_count} < {self.min_subdomains})",
                should_continue=self.settings.get("continue_on_low_surface", True)
            )
        
        return SafetyCheckResult(
            passed=True,
            subdomains_count=subdomain_count,
            http_services_count=http_count,
            message=f"Gate check passed: {subdomain_count} subdomains found",
            should_continue=True
        )
    
    def validate_scope(self, items: List[str]) -> List[str]:
        """
        Filter items to ensure they are in scope.
        
        Args:
            items: List of URLs or hostnames
            
        Returns:
            Filtered list (in-scope only)
        """
        valid = []
        for item in items:
            if self.target_domain and self.target_domain.lower() in item.lower():
                # Reject known hallucination patterns
                if "example.com" not in item.lower():
                    valid.append(item)
        return valid
    
    def attempt_recovery(self, failed_tool: str, context: Dict) -> bool:
        """
        Attempt to recover when a tool fails.
        
        Args:
            failed_tool: Name of the failed tool
            context: Context about the failure
            
        Returns:
            True if recovery was successful
        """
        # Recovery strategies by tool
        recovery_strategies = {
            "subfinder": self._recover_subfinder,
            "httpx": self._recover_httpx,
            "wayback": self._recover_wayback,
        }
        
        strategy = recovery_strategies.get(failed_tool)
        if strategy:
            try:
                return strategy(context)
            except Exception:
                return False
        
        return False
    
    def _recover_subfinder(self, context: Dict) -> bool:
        """Try alternative subdomain enumeration."""
        # Could add crt.sh, SecurityTrails, etc.
        return False
    
    def _recover_httpx(self, context: Dict) -> bool:
        """Try alternative HTTP probing."""
        # Could add simple requests-based probing
        return False
    
    def _recover_wayback(self, context: Dict) -> bool:
        """Try alternative historical data."""
        # Could add CommonCrawl, etc.
        return False
