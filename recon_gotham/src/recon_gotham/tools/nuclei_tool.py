
import json
import logging
import subprocess
import shutil
import platform
import os
from typing import ClassVar, List, Type, Optional

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass

from pydantic import BaseModel, Field

# Setup logging
logger = logging.getLogger(__name__)

class NucleiToolSchema(BaseModel):
    targets: List[str] = Field(..., description="List of URLs or Hosts to scan.")
    severity: str = Field("critical,high,medium", description="Severity filters (comma separated). Default: critical,high,medium.")
    tags: Optional[str] = Field(None, description="Tags to filter templates (e.g. cve,misconfig,exposure).")

class NucleiTool(BaseTool):
    """
    Tool for running Nuclei vulnerability scans.
    Wraps the 'nuclei' binary (or Docker fallback if needed).
    """
    name: str = "nuclei_scan_tool"
    description: str = (
        "Active Vulnerability Scanner using Nuclei. "
        "Use this to find critical vulnerabilities on discovered web services. "
        "Input: list of URLs. Output: JSON list of findings."
    )
    args_schema: Type[BaseModel] = NucleiToolSchema

    def _run(self, targets: List[str], severity: str = "critical,high,medium", tags: str = None) -> str:
        """
        Executes Nuclei scan on the provided targets.
        """
        targets = [t for t in targets if t and isinstance(t, str) and len(t.strip()) > 3]
        if not targets:
            return "[]"

        # Check for binary
        nuclei_path = shutil.which("nuclei")
        use_docker = False
        
        if not nuclei_path:
            # Check docker
            if shutil.which("docker"):
                use_docker = True
            else:
                 return json.dumps([{
                    "error": "Nuclei binary and Docker not found. Cannot run scan.",
                    "status": "FAILED"
                }])

        # Create target file
        target_file = "nuclei_targets_tmp.txt"
        output_file = "nuclei_results_tmp.json"
        
        try:
            with open(target_file, "w") as f:
                for t in targets:
                    f.write(f"{t}\n")
            
            # Construct command
            cmd = []
            if use_docker:
                # Docker command (Mounting current dir to access targets)
                # Ensure we mount the current working directory
                cwd = os.getcwd().replace("\\", "/") # Normalize for Docker
                
                # Ensure image is present (optional, but good practice)
                # subprocess.run(["docker", "pull", "projectdiscovery/nuclei:latest"], check=False)
                
                cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{cwd}:/app",
                    "-w", "/app",
                    "projectdiscovery/nuclei:latest",
                    "-l", target_file,
                    "-json-export", output_file,
                    "-risk", severity,
                    "-silent"
                ]
                if tags:
                    cmd.extend(["-t", tags])
            else:
                # Binary command
                cmd = [
                    nuclei_path,
                    "-l", target_file,
                    "-json-export", output_file,
                    "-risk", severity,
                    "-silent"
                ]
                if tags:
                    cmd.extend(["-t", tags])
            
            # Run scan
            logger.info(f"Running Nuclei: {' '.join(cmd)}")
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            
            # Parse Results
            results = []
            if os.path.exists(output_file):
                with open(output_file, "r", encoding="utf-8") as f:
                    # Nuclei writes newline-delimited JSON objects, not a JSON array
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            finding = json.loads(line)
                            # Normalize for Agent
                            # Extract key fields: template-id, info.severity, info.name, matched-at, matcher-name
                            info = finding.get("info", {})
                            
                            normalized = {
                                "name": info.get("name", "Unknown Vulnerability"),
                                "severity": info.get("severity", "LOW").upper(),
                                "template_id": finding.get("template-id"),
                                "url": finding.get("matched-at"),
                                "description": info.get("description", ""),
                                "matcher": finding.get("matcher-name", "default")
                            }
                            results.append(normalized)
                        except json.JSONDecodeError:
                            continue
            
            return json.dumps(results, indent=2)

        except Exception as e:
            return json.dumps([{
                "error": str(e),
                "status": "CRASHED"
            }])
        finally:
            # Cleanup
            if os.path.exists(target_file):
                 try: os.remove(target_file)
                 except: pass
            if os.path.exists(output_file):
                 try: os.remove(output_file)
                 except: pass
