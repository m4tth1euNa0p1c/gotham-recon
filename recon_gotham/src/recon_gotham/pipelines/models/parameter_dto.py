"""
Parameter DTO - Data Transfer Object for Parameters
"""

from typing import Optional
from pydantic import BaseModel, Field, validator


class ParameterDTO(BaseModel):
    """DTO for parameter data validation and transfer."""
    
    # Required fields
    name: str = Field(..., description="Parameter name")
    endpoint_id: str = Field(..., description="Parent endpoint ID")
    
    # Location and typing
    location: str = Field(default="query", description="query/path/body/header/cookie")
    datatype_hint: str = Field(default="unknown", description="int/string/uuid/token/unknown")
    
    # Sensitivity
    sensitivity: str = Field(default="LOW", description="LOW/MEDIUM/HIGH/CRITICAL")
    is_critical: bool = Field(default=False)
    
    # Flags
    is_id_param: bool = Field(default=False)
    is_auth_param: bool = Field(default=False)
    
    @validator('location')
    def validate_location(cls, v):
        valid = ['query', 'path', 'body', 'header', 'cookie']
        return v.lower() if v.lower() in valid else 'query'
    
    @validator('sensitivity')
    def validate_sensitivity(cls, v):
        valid = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        return v.upper() if v.upper() in valid else 'LOW'
    
    def to_node(self, param_id: str) -> dict:
        """Convert to AssetGraph node format."""
        return {
            "id": param_id,
            "type": "PARAMETER",
            "properties": {
                "name": self.name,
                "location": self.location,
                "datatype_hint": self.datatype_hint,
                "sensitivity": self.sensitivity,
                "is_critical": self.is_critical,
                "is_id_param": self.is_id_param,
                "is_auth_param": self.is_auth_param
            }
        }
    
    @classmethod
    def from_node(cls, node: dict, endpoint_id: str = "") -> "ParameterDTO":
        """Create from AssetGraph node."""
        props = node.get("properties", {})
        return cls(
            name=props.get("name", ""),
            endpoint_id=endpoint_id,
            location=props.get("location", "query"),
            datatype_hint=props.get("datatype_hint", "unknown"),
            sensitivity=props.get("sensitivity", "LOW"),
            is_critical=props.get("is_critical", False),
            is_id_param=props.get("is_id_param", False),
            is_auth_param=props.get("is_auth_param", False)
        )
    
    class Config:
        extra = "ignore"
