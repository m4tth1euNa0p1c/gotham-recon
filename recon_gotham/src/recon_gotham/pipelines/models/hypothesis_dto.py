"""
Hypothesis DTO - Data Transfer Object for Vulnerability Hypotheses
"""

from typing import Optional
from pydantic import BaseModel, Field, validator


class HypothesisDTO(BaseModel):
    """DTO for hypothesis data validation and transfer."""
    
    # Required fields
    endpoint_id: str = Field(..., description="Parent endpoint ID")
    attack_type: str = Field(..., description="Type of attack (SQLI, XSS, IDOR, etc.)")
    title: str = Field(..., description="Hypothesis title")
    
    # Details
    description: str = Field(default="", description="Detailed description")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    priority: int = Field(default=3, ge=1, le=5, description="1=low, 5=critical")
    
    # Status
    status: str = Field(default="UNTESTED")
    tested_by: Optional[str] = Field(default=None)
    
    @validator('attack_type')
    def validate_attack_type(cls, v):
        valid = ['SQLI', 'XSS', 'IDOR', 'AUTH_BYPASS', 'CODE_INJECTION', 'RCE', 'LFI', 'SSRF', 'OPEN_REDIRECT', 'CSRF', 'UNKNOWN']
        return v.upper() if v.upper() in valid else 'UNKNOWN'
    
    @validator('status')
    def validate_status(cls, v):
        valid = ['UNTESTED', 'POSSIBLE', 'CONFIRMED_THEORETICAL', 'REJECTED', 'INCONCLUSIVE']
        return v.upper() if v.upper() in valid else 'UNTESTED'
    
    def to_node(self, hyp_id: str) -> dict:
        """Convert to AssetGraph node format."""
        return {
            "id": hyp_id,
            "type": "HYPOTHESIS",
            "properties": {
                "attack_type": self.attack_type,
                "title": self.title,
                "description": self.description,
                "confidence": self.confidence,
                "priority": self.priority,
                "status": self.status,
                "tested_by": self.tested_by
            }
        }
    
    @classmethod
    def from_node(cls, node: dict, endpoint_id: str = "") -> "HypothesisDTO":
        """Create from AssetGraph node."""
        props = node.get("properties", {})
        return cls(
            endpoint_id=endpoint_id,
            attack_type=props.get("attack_type", "UNKNOWN"),
            title=props.get("title", ""),
            description=props.get("description", ""),
            confidence=props.get("confidence", 0.5),
            priority=props.get("priority", 3),
            status=props.get("status", "UNTESTED"),
            tested_by=props.get("tested_by")
        )
    
    class Config:
        extra = "ignore"
