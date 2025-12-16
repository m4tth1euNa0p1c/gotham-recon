
import json
import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'recon_gotham', 'src'))

from recon_gotham.tools.nuclei_tool import NucleiTool

def test_nuclei_tool():
    print("[-] Testing NucleiTool (Containerized) on 'suivi.mailings.tahiti-infos.com'...")
    
    nuclei = NucleiTool()
    
    # Target
    # suivi.mailings.tahiti-infos.com is a valid target found in previous steps
    target = "https://suivi.mailings.tahiti-infos.com"
    
    # Run Tool with very safe parameters
    # Limitation: might not find much with just "critical,high,medium" if it's clean,
    # but we want to simulate the flow.
    # Note: Using "info" level or specific tags might be better for a smoke test if target is clean.
    # But let's stick to default to see if it runs.
    
    # We'll enable INFO severity just to get *something* back if possible, or verify empty list.
    print(f"[*] Scanning {target}...")
    result_json = nuclei._run(targets=[target], severity="critical,high,medium,low,info")
    
    print(f"[DEBUG] Raw Result: {result_json}")

    try:
        findings = json.loads(result_json)
        if isinstance(findings, list):
            print(f"[+] Scan completed successfully.")
            print(f"[+] Findings count: {len(findings)}")
            if len(findings) > 0:
                print(f"    First finding: {findings[0]['name']} ({findings[0]['severity']})")
                print(f"    Full: {findings[0]}")
            else:
                print("[-] No vulnerabilities found (Result is empty list []).")
                print("    This likely means the tool ran but found nothing, which is valid.")
        else:
             print(f"[-] Unexpected output format: {type(findings)}")
             print(f"    Raw: {result_json[:200]}")
             
    except json.JSONDecodeError:
        print(f"[-] ERROR: Output is not valid JSON.")
        print(f"    Raw: {result_json}")

if __name__ == "__main__":
    test_nuclei_tool()
