"""
Recon-Gotham V3.0 - Structured Logging
JSON-formatted logging with run_id propagation.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class StructuredJsonFormatter(logging.Formatter):
    """JSON formatter for structured logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add custom fields if present
        if hasattr(record, 'run_id'):
            log_entry["run_id"] = record.run_id
        if hasattr(record, 'phase'):
            log_entry["phase"] = record.phase
        if hasattr(record, 'component'):
            log_entry["component"] = record.component
        if hasattr(record, 'domain'):
            log_entry["domain"] = record.domain
        if hasattr(record, 'event'):
            log_entry["event"] = record.event
        if hasattr(record, 'extra_data'):
            log_entry["data"] = record.extra_data
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


class ReconLogger:
    """
    Structured logger for Recon-Gotham.
    
    Usage:
        logger = ReconLogger.get_logger("my_module", run_id="abc123")
        logger.info("Processing completed", extra={"phase": "OSINT", "count": 42})
    """
    
    _loggers: Dict[str, logging.Logger] = {}
    _run_id: Optional[str] = None
    _domain: Optional[str] = None
    _log_file: Optional[str] = None
    
    @classmethod
    def configure(cls, run_id: str, domain: str, log_dir: str = "recon_gotham/output"):
        """Configure global logging settings."""
        cls._run_id = run_id
        cls._domain = domain
        cls._log_file = f"{log_dir}/{domain}_{run_id}_live.log"
        
        # Ensure directory exists
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get or create a logger."""
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(f"recon_gotham.{name}")
        logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Console handler (INFO+)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(console_handler)
        
        # File handler (DEBUG+, JSON format)
        if cls._log_file:
            file_handler = logging.FileHandler(cls._log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(StructuredJsonFormatter())
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def log_event(cls, name: str, level: str, message: str, 
                  phase: str = None, component: str = None, 
                  event: str = None, data: Dict = None):
        """Log a structured event."""
        logger = cls.get_logger(name)
        
        extra = {}
        if cls._run_id:
            extra['run_id'] = cls._run_id
        if cls._domain:
            extra['domain'] = cls._domain
        if phase:
            extra['phase'] = phase
        if component:
            extra['component'] = component
        if event:
            extra['event'] = event
        if data:
            extra['extra_data'] = data
        
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(message, extra=extra)
    
    @classmethod
    def phase_start(cls, phase: str, component: str = None):
        """Log phase start."""
        cls.log_event(
            "orchestrator", "info",
            f"Phase {phase} started",
            phase=phase, component=component, event="PHASE_START"
        )
    
    @classmethod
    def phase_end(cls, phase: str, duration: float, stats: Dict = None):
        """Log phase end."""
        cls.log_event(
            "orchestrator", "info",
            f"Phase {phase} completed in {duration:.1f}s",
            phase=phase, event="PHASE_END",
            data={"duration": duration, "stats": stats or {}}
        )
    
    @classmethod
    def tool_execution(cls, tool_name: str, success: bool, duration: float = None, error: str = None):
        """Log tool execution."""
        status = "success" if success else "failure"
        cls.log_event(
            f"tool.{tool_name}", "info" if success else "error",
            f"Tool {tool_name} {status}",
            component=tool_name, event="TOOL_EXECUTION",
            data={"success": success, "duration": duration, "error": error}
        )
    
    @classmethod
    def decision(cls, decision_type: str, reasoning: str, outcome: str):
        """Log an orchestrator decision."""
        cls.log_event(
            "orchestrator", "info",
            f"Decision: {decision_type} -> {outcome}",
            event="DECISION",
            data={"type": decision_type, "reasoning": reasoning, "outcome": outcome}
        )


# Convenience function
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return ReconLogger.get_logger(name)
