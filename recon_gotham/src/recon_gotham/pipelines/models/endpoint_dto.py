"""
Endpoint DTO - Data Transfer Object for Endpoints
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator


class EndpointDTO(BaseModel):
    """DTO for endpoint data validation and transfer."""
    
    # Required fields
    id: str = Field(..., description="Unique endpoint identifier")
    path: str = Field(..., description="URL path of the endpoint")
    method: str = Field(default="GET", description="HTTP method")
    source: str = Field(default="UNKNOWN", description="Discovery source")
    origin: str = Field(..., description="Full URL origin")
    
    # Enrichment fields (Phase 23)
    category: str = Field(default="UNKNOWN", description="Endpoint category")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Risk scoring
    likelihood_score: int = Field(default=0, ge=0, le=10)
    impact_score: int = Field(default=0, ge=0, le=10)
    risk_score: int = Field(default=0, ge=0, le=100)
    
    # Hints
    auth_required: str = Field(default="UNKNOWN", description="true/false/UNKNOWN")
    tech_stack_hint: str = Field(default="Unknown")
    behavior: str = Field(default="UNKNOWN")
    
    # Flags
    id_based_access: bool = Field(default=False)
    has_sensitive_params: bool = Field(default=False)
    
    @validator('method')
    def validate_method(cls, v):
        valid = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        return v.upper() if v.upper() in valid else 'GET'
    
    @validator('category')
    def validate_category(cls, v):
        valid = ['API', 'ADMIN', 'AUTH', 'PUBLIC', 'STATIC', 'LEGACY', 'HEALTHCHECK', 'UNKNOWN']
        return v.upper() if v.upper() in valid else 'UNKNOWN'
    
    def to_node(self) -> dict:
        """Convert to AssetGraph node format."""
        return {
            "id": self.id,
            "type": "ENDPOINT",
            "properties": {
                "path": self.path,
                "method": self.method,
                "source": self.source,
                "origin": self.origin,
                "category": self.category,
                "confidence": self.confidence,
                "likelihood_score": self.likelihood_score,
                "impact_score": self.impact_score,
                "risk_score": self.risk_score,
                "auth_required": self.auth_required,
                "tech_stack_hint": self.tech_stack_hint,
                "behavior": self.behavior,
                "id_based_access": self.id_based_access,
                "has_sensitive_params": self.has_sensitive_params
            }
        }
    
    @classmethod
    def from_node(cls, node: dict) -> "EndpointDTO":
        """Create from AssetGraph node."""
        props = node.get("properties", {})
        return cls(
            id=node.get("id", ""),
            path=props.get("path", ""),
            method=props.get("method", "GET"),
            source=props.get("source", "UNKNOWN"),
            origin=props.get("origin", ""),
            category=props.get("category", "UNKNOWN"),
            confidence=props.get("confidence", 0.5),
            likelihood_score=props.get("likelihood_score", 0),
            impact_score=props.get("impact_score", 0),
            risk_score=props.get("risk_score", 0),
            auth_required=props.get("auth_required", "UNKNOWN"),
            tech_stack_hint=props.get("tech_stack_hint", "Unknown"),
            behavior=props.get("behavior", "UNKNOWN"),
            id_based_access=props.get("id_based_access", False),
            has_sensitive_params=props.get("has_sensitive_params", False)
        )
    
    class Config:
        extra = "ignore"
