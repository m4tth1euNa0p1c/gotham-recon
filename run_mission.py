import sys
import os
import subprocess

# Helper script to run the recon mission from the root directory.
# Usage: python run_mission.py <target_domain>

import argparse

def main():
    parser = argparse.ArgumentParser(description="Run Recon Gotham Mission")
    parser.add_argument("domain", help="Target domain (e.g. example.com)")
    parser.add_argument("--mode", choices=["stealth", "aggressive"], default="stealth", help="Mission profile")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--seed-file", dest="seed_file", help="File with known subdomains (one per line)")
    
    args = parser.parse_args()
    target_domain = args.domain
    mode = args.mode
    debug_mode = args.debug
    seed_file = args.seed_file
    
    # Calculate path to the src main.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, 'recon_gotham', 'src', 'recon_gotham', 'main.py')
    
    print(f"[Launcher] Executing agent on: {target_domain} (Mode: {mode.upper()}) (Debug: {debug_mode})")
    print(f"[Launcher] Script: {script_path}")
    
    # Run the main script using the same python interpreter
    # We pass the mode as an argument to main.py
    # main.py needs to handle it. We'll simply append it.
    cmd = [sys.executable, script_path, target_domain, "--mode", mode]
    if debug_mode:
        cmd.append("--debug")
    if seed_file:
        cmd.extend(["--seed-file", seed_file])
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[Launcher] Error: Agent execution failed with exit code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
