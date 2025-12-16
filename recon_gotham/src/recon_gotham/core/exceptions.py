"""
Recon-Gotham V3.0 - Exception Hierarchy
Custom exceptions for structured error handling.
"""


class ReconGothamError(Exception):
    """Base exception for Recon-Gotham."""
    
    def __init__(self, message: str, phase: str = None, component: str = None, recoverable: bool = True):
        super().__init__(message)
        self.message = message
        self.phase = phase
        self.component = component
        self.recoverable = recoverable
    
    def to_dict(self) -> dict:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "phase": self.phase,
            "component": self.component,
            "recoverable": self.recoverable
        }


class OrchestrationError(ReconGothamError):
    """Error during orchestration/pipeline execution."""
    
    def __init__(self, message: str, phase: str = None):
        super().__init__(message, phase=phase, component="orchestrator")


class ToolError(ReconGothamError):
    """Error during tool execution."""
    
    def __init__(self, message: str, tool_name: str, phase: str = None, recoverable: bool = True):
        super().__init__(message, phase=phase, component=f"tool.{tool_name}", recoverable=recoverable)
        self.tool_name = tool_name


class AgentError(ReconGothamError):
    """Error during agent execution (CrewAI)."""
    
    def __init__(self, message: str, agent_name: str, task_name: str = None, phase: str = None):
        super().__init__(message, phase=phase, component=f"agent.{agent_name}")
        self.agent_name = agent_name
        self.task_name = task_name


class IngestionError(ReconGothamError):
    """Error during data ingestion into AssetGraph."""
    
    def __init__(self, message: str, source: str = None, data_type: str = None, phase: str = None):
        super().__init__(message, phase=phase, component="ingestion", recoverable=True)
        self.source = source
        self.data_type = data_type


class ValidationError(ReconGothamError):
    """Error during data validation (DTO/Schema)."""
    
    def __init__(self, message: str, field: str = None, expected: str = None, actual: str = None):
        super().__init__(message, component="validation", recoverable=True)
        self.field = field
        self.expected = expected
        self.actual = actual


class VerificationError(ReconGothamError):
    """Error during Phase 24/25 verification."""
    
    def __init__(self, message: str, target_url: str = None, test_type: str = None):
        super().__init__(message, phase="VERIFICATION", component="verification_pipeline")
        self.target_url = target_url
        self.test_type = test_type


class ScopeError(ReconGothamError):
    """Error when data is out of scope (anti-hallucination)."""
    
    def __init__(self, message: str, rejected_item: str = None, target_domain: str = None):
        super().__init__(message, component="scope_validator", recoverable=True)
        self.rejected_item = rejected_item
        self.target_domain = target_domain


class BudgetExceededError(ReconGothamError):
    """Error when budget/limit is exceeded."""
    
    def __init__(self, message: str, budget_type: str = None, limit: int = None, current: int = None):
        super().__init__(message, component="budget_manager", recoverable=False)
        self.budget_type = budget_type
        self.limit = limit
        self.current = current


class ConfigurationError(ReconGothamError):
    """Error in configuration (missing/invalid settings)."""
    
    def __init__(self, message: str, config_key: str = None):
        super().__init__(message, component="configuration", recoverable=False)
        self.config_key = config_key
