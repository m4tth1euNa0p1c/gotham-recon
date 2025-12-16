import os
import subprocess
import sys

def run_batch():
    # Read targets
    test_file = os.path.join("test", "test.txt")
    if not os.path.exists(test_file):
        print(f"[-] Test file not found: {test_file}")
        return

    with open(test_file, 'r') as f:
        domains = [line.strip() for line in f if line.strip()]

    print(f"[+] Found {len(domains)} targets: {domains}")
    
    results = {}

    for domain in domains:
        print(f"\n{'='*50}")
        print(f"🚀 Running Mission for: {domain}")
        print(f"{'='*50}")
        
        try:
            # Run mission
            # We assume python is in path and we are in root dir
            # Capture output to analyze later if needed, but let's print to stdout for now to let user see progress
            # actually capturing it allows us to analyze it for "STRICT JSON" errors programmatically
            
            proc = subprocess.run(
                ["python", "run_mission.py", domain],
                capture_output=True,
                text=True,
                timeout=300 # 5 minutes max per domain
            )
            
            output = proc.stdout + proc.stderr
            
            # Checks
            graph_file = os.path.join("output", f"{domain}_asset_graph.json")
            plan_file = os.path.join("output", f"{domain}_attack_plan.json")
            summary_file = os.path.join("recon_gotham", "knowledge", f"{domain}_summary.md")
            
            files_exist = {
                "graph": os.path.exists(graph_file),
                "plan": os.path.exists(plan_file),
                "summary": os.path.exists(summary_file)
            }
            
            # Simple heuristic analysis of output for errors
            json_error = "JSONDecodeError" in output
            hallucination_warning = "CRITICAL" in output # If we log hallucination warnings
            
            results[domain] = {
                "exit_code": proc.returncode,
                "artifacts": files_exist,
                "errors": {
                    "json_decode": json_error
                },
                "output_snippet": output[-500:] if output else "No Output"
            }
            
            if proc.returncode == 0:
                print(f"✅ Mission Success for {domain}")
            else:
                print(f"❌ Mission Failed for {domain} (Exit Code: {proc.returncode})")
                print(proc.stderr)

        except subprocess.TimeoutExpired:
             print(f"⏰ Timeout for {domain}")
             results[domain] = {"error": "Timeout"}
        except Exception as e:
             print(f"💥 Exception for {domain}: {e}")
             results[domain] = {"error": str(e)}

    # Summary Report
    print("\n\n")
    print(f"{'='*50}")
    print("📊 BATCH TEST SUMMARY")
    print(f"{'='*50}")
    for domain, res in results.items():
        if "error" in res and isinstance(res["error"], str): # Timeout or Exception
             print(f"❌ {domain}: Critical Failure ({res['error']})")
             continue
             
        status = "✅ PASS" if res["exit_code"] == 0 and all(res["artifacts"].values()) else "⚠️ PARTIAL" if res["exit_code"] == 0 else "❌ FAIL"
        print(f"{status} {domain}")
        print(f"   - Artifacts: Graph={res['artifacts']['graph']}, Plan={res['artifacts']['plan']}, Summary={res['artifacts']['summary']}")
        if res["errors"]["json_decode"]:
            print("   - Detected JSON Formatting Errors in logs!")

if __name__ == "__main__":
    run_batch()
