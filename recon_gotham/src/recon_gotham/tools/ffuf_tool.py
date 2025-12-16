import os
import json
import shutil
import subprocess
import logging
from typing import Type, List, Dict, Optional, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# --- Schema ---
class FfufInput(BaseModel):
    target_url: str = Field(..., description="Target URL (including protocol) to fuzz. e.g. https://example.com/FUZZ")
    mode: str = Field("common", description="Wordlist mode: 'common', 'admin', 'api', or 'custom'")
    custom_wordlist: Optional[str] = Field(None, description="Path to custom wordlist if mode is custom")
    extensions: Optional[str] = Field(None, description="Extensions to append, e.g. '.php,.html'")
    recursive: bool = Field(False, description="Enable recursive fuzzing")

# --- Tool ---
class FfufTool(BaseTool):
    name: str = "ffuf_fuzzer_tool"
    description: str = (
        "Performs web fuzzing using FFUF to discover directories, files, or parameters. "
        "Supports 'common', 'admin', 'api' modes. "
        "Returns a list of discovered endpoints with status codes and sizes."
    )
    args_schema: Type[BaseModel] = FfufInput

    def _run(self, target_url: str, mode: str = "common", custom_wordlist: str = None, extensions: str = None, recursive: bool = False) -> str:
        """
        Executes FFUF against the target.
        """
        logger = logging.getLogger(__name__)
        
        # 1. Determine Execution Method (Local vs Docker)
        use_docker = False
        ffuf_bin = shutil.which("ffuf")
        
        if not ffuf_bin:
            # Fallback to Docker
            # Check if docker is available
            if not shutil.which("docker"):
                return json.dumps({"error": "Ffuf binary not found and Docker not available."})
            use_docker = True
            logging.info("Using Docker for Ffuf execution.")
        
        # 2. Select Wordlist (Internal management)
        # Note: In a real scenario, these would be substantial files. 
        # For this implementation, we will point to known paths or generate temp files.
        working_dir = os.getcwd()
        wordlists_dir = os.path.join(working_dir, "recon_gotham", "wordlists")
        os.makedirs(wordlists_dir, exist_ok=True)
        
        wordlist_path = ""
        
        # Ensure default wordlists exist (Stubbing for robustness)
        self._ensure_wordlists(wordlists_dir)

        if mode == "custom" and custom_wordlist:
             wordlist_path = custom_wordlist
        elif mode == "admin":
            wordlist_path = os.path.join(wordlists_dir, "admin.txt")
        elif mode == "api":
            wordlist_path = os.path.join(wordlists_dir, "api.txt")
        else: # common
            wordlist_path = os.path.join(wordlists_dir, "common.txt")

        if not os.path.exists(wordlist_path):
             return json.dumps({"error": f"Wordlist not found at {wordlist_path}"})

        # 3. Construct Command
        # Output file to parse JSON robustly
        output_file = os.path.join(working_dir, "ffuf_output.json")
        if os.path.exists(output_file):
            os.remove(output_file)

        # Basic Args
        # -s: Silent
        # -mc: Match codes (200,204,301,302,307,401,403) - adjusted per need, keeping generic safe set for recon
        # -of json -o output_file
        
        # Fix URL for Fuzzing if FUZZ keyword missing
        if "FUZZ" not in target_url:
            if target_url.endswith("/"):
                target_url += "FUZZ"
            else:
                target_url += "/FUZZ"

        command = []
        
        if use_docker:
            # Mount wordlist directory and output directory
            # docker run -v /abs/path/wordlists:/wordlists -v /abs/path/output:/output ffuf/ffuf
            
            # Paths inside container
            container_wordlist = f"/wordlists/{os.path.basename(wordlist_path)}"
            container_output = "/output/ffuf_output.json"
            
            command = [
                "docker", "run", "--rm",
                "-v", f"{wordlists_dir}:/wordlists",
                "-v", f"{working_dir}:/output",
                "ffuf/ffuf",
                "-u", target_url,
                "-w", container_wordlist,
                "-of", "json",
                "-o", container_output,
                "-s", # Silent
                "-mc", "200,204,301,302,307" # Common success codes
            ]
        else:
            command = [
                ffuf_bin,
                "-u", target_url,
                "-w", wordlist_path,
                "-of", "json",
                "-o", output_file,
                "-s",
                "-mc", "200,204,301,302,307"
            ]

        if extensions:
             command.extend(["-e", extensions])
        
        if recursive:
             command.append("-recursion")

        # 4. Execute
        try:
            logger.info(f"Running Ffuf command: {' '.join(command)}")
            subprocess.run(command, check=True, timeout=300) # 5 min timeout
        except subprocess.CalledProcessError as e:
            # Ffuf might exit with non-zero if matches found or not found depending on flags, 
            # but usually it's fine. 
            logger.warning(f"Ffuf execution warning: {e}")
        except subprocess.TimeoutExpired:
             logger.error("Ffuf execution timed out.")
             return json.dumps({"error": "Ffuf scan timed out"})

        # 5. Parse Output
        results = []
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    
                    # Ffuf JSON structure: { "commandline": "...", "time": "...", "results": [ ... ] }
                    raw_results = data.get('results', [])
                    
                    for res in raw_results:
                        # Normalize for AssetGraph
                        # { "input": {"FUZZ": "admin"}, "position": 1, "status": 200, "length": 123, "url": "..." }
                        endpoint = res.get('url', '')
                        # Extract relative path if needed, or keep full URL
                        # Let's keep relative to base
                        
                        finding = {
                            "endpoint": endpoint,
                            "keyword": res.get('input', {}).get('FUZZ', ''),
                            "status": res.get('status'),
                            "length": res.get('length'),
                            "source": "FFUF_FUZZ",
                            "confidence": 0.9
                        }
                        results.append(finding)
            except json.JSONDecodeError:
                logger.error("Failed to parse Ffuf JSON output")
        
        return json.dumps(results, indent=2)

    def _ensure_wordlists(self, directory: str):
        """Creates dummy wordlists if they don't exist for test stability."""
        
        common = ["admin", "backup", "test", "dev", "api", "dashboard", "login", "register", "upload"]
        admin = ["admin", "administrator", "admin_panel", "cpanel", "controlpanel", "wp-admin"]
        api = ["v1", "v2", "api", "swagger", "graphql", "health", "metrics", "users", "auth"]
        
        files = {
            "common.txt": common,
            "admin.txt": admin,
            "api.txt": api
        }
        
        for filename, entries in files.items():
            path = os.path.join(directory, filename)
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    f.write('\n'.join(entries))
