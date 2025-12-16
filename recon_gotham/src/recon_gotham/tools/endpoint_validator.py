"""
Endpoint Validator Tool - Phase 23 V2.3
Validates discovered endpoints exist and conform to expected behavior.
"""

import requests
import json
import concurrent.futures
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import time


class EndpointValidator:
    """
    Validates endpoints discovered in the AssetGraph.
    Checks HTTP status codes, content types, and response characteristics.
    """
    
    def __init__(self, timeout: int = 10, max_workers: int = 5, verify_ssl: bool = False):
        self.timeout = timeout
        self.max_workers = max_workers
        self.verify_ssl = verify_ssl
        self.results = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/json,*/*"
        }
    
    def validate_url(self, url: str) -> Dict:
        """
        Validate a single URL and return detailed response info.
        """
        result = {
            "url": url,
            "status_code": None,
            "reachable": False,
            "content_type": None,
            "response_time_ms": None,
            "redirect_url": None,
            "error": None,
            "validated": False
        }
        
        try:
            start_time = time.time()
            response = requests.head(
                url, 
                headers=self.headers, 
                timeout=self.timeout, 
                verify=self.verify_ssl,
                allow_redirects=True
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            result["status_code"] = response.status_code
            result["reachable"] = True
            result["response_time_ms"] = elapsed_ms
            result["content_type"] = response.headers.get("Content-Type", "")
            
            # Track redirects
            if response.history:
                result["redirect_url"] = response.url
            
            # Mark as validated if we got a response (even 4xx/5xx)
            result["validated"] = True
            
        except requests.exceptions.SSLError as e:
            result["error"] = f"SSL Error: {str(e)[:100]}"
        except requests.exceptions.ConnectionError as e:
            result["error"] = f"Connection Error: {str(e)[:100]}"
        except requests.exceptions.Timeout:
            result["error"] = "Timeout"
        except requests.exceptions.RequestException as e:
            result["error"] = f"Request Error: {str(e)[:100]}"
        
        return result

    def validate_graph(self, graph_path: str, target_domain: str = None) -> Dict:
        """
        Load an AssetGraph JSON and validate all endpoints.
        Returns a validation report.
        """
        # Load graph
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
        
        nodes = graph.get("nodes", [])
        
        # Collect URLs to validate
        urls_to_validate = []
        
        # 1. Validate HTTP_SERVICEs
        http_services = [n for n in nodes if n["type"] == "HTTP_SERVICE"]
        for svc in http_services:
            url = svc.get("properties", {}).get("url")
            if url:
                urls_to_validate.append(("HTTP_SERVICE", url, svc["id"]))
        
        # 2. Validate ENDPOINTs (sample top endpoints)
        endpoints = [n for n in nodes if n["type"] == "ENDPOINT"]
        # Sort by risk_score and take top 20
        sorted_eps = sorted(
            endpoints, 
            key=lambda x: x.get("properties", {}).get("risk_score", 0), 
            reverse=True
        )[:20]
        
        for ep in sorted_eps:
            origin = ep.get("properties", {}).get("origin")
            if origin and origin.startswith("http"):
                urls_to_validate.append(("ENDPOINT", origin, ep["id"]))
        
        # 3. Validate SUBDOMAINs as HTTPS
        subdomains = [n for n in nodes if n["type"] == "SUBDOMAIN"]
        for sub in subdomains[:15]:  # Limit to 15
            name = sub.get("properties", {}).get("name")
            if name:
                urls_to_validate.append(("SUBDOMAIN", f"https://{name}", sub["id"]))
        
        # Run validations in parallel
        print(f"[*] Validating {len(urls_to_validate)} URLs...")
        
        validation_results = {
            "HTTP_SERVICE": [],
            "ENDPOINT": [],
            "SUBDOMAIN": []
        }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self.validate_url, url): (node_type, url, node_id)
                for node_type, url, node_id in urls_to_validate
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                node_type, url, node_id = future_to_url[future]
                try:
                    result = future.result()
                    result["node_id"] = node_id
                    result["node_type"] = node_type
                    validation_results[node_type].append(result)
                except Exception as e:
                    validation_results[node_type].append({
                        "url": url,
                        "node_id": node_id,
                        "error": str(e),
                        "validated": False
                    })
        
        # Generate summary
        summary = self._generate_summary(validation_results)
        
        return {
            "summary": summary,
            "results": validation_results
        }

    def _generate_summary(self, results: Dict) -> Dict:
        """Generate a validation summary."""
        summary = {
            "total_validated": 0,
            "reachable": 0,
            "unreachable": 0,
            "status_distribution": {},
            "errors": []
        }
        
        for node_type, items in results.items():
            for item in items:
                summary["total_validated"] += 1
                
                if item.get("reachable"):
                    summary["reachable"] += 1
                    status = item.get("status_code", 0)
                    status_group = f"{status // 100}xx"
                    summary["status_distribution"][status_group] = \
                        summary["status_distribution"].get(status_group, 0) + 1
                else:
                    summary["unreachable"] += 1
                    if item.get("error"):
                        summary["errors"].append({
                            "url": item.get("url"),
                            "error": item.get("error")
                        })
        
        return summary

    def print_report(self, report: Dict):
        """Print a formatted validation report."""
        summary = report["summary"]
        
        print("\n" + "=" * 60)
        print("ENDPOINT VALIDATION REPORT")
        print("=" * 60)
        
        print(f"\n📊 Summary:")
        print(f"   Total URLs Validated: {summary['total_validated']}")
        print(f"   ✅ Reachable: {summary['reachable']}")
        print(f"   ❌ Unreachable: {summary['unreachable']}")
        
        print(f"\n📈 Status Code Distribution:")
        for status, count in sorted(summary["status_distribution"].items()):
            print(f"   {status}: {count}")
        
        # Show reachable endpoints by type
        for node_type, items in report["results"].items():
            reachable_items = [i for i in items if i.get("reachable")]
            if reachable_items:
                print(f"\n✅ {node_type}s Reached ({len(reachable_items)}):")
                for item in reachable_items[:5]:  # Show top 5
                    status = item.get("status_code", "N/A")
                    time_ms = item.get("response_time_ms", "N/A")
                    print(f"   [{status}] {item['url']} ({time_ms}ms)")
                if len(reachable_items) > 5:
                    print(f"   ... and {len(reachable_items) - 5} more")
        
        # Show errors
        if summary["errors"]:
            print(f"\n❌ Errors ({len(summary['errors'])}):")
            for err in summary["errors"][:5]:
                print(f"   {err['url']}: {err['error']}")
            if len(summary["errors"]) > 5:
                print(f"   ... and {len(summary['errors']) - 5} more")
        
        print("\n" + "=" * 60)


def validate_graph_file(graph_path: str, target_domain: str = None):
    """CLI entry point for validating a graph file."""
    validator = EndpointValidator(timeout=10, max_workers=5)
    report = validator.validate_graph(graph_path, target_domain)
    validator.print_report(report)
    
    # Save report to JSON
    report_path = graph_path.replace("_asset_graph.json", "_validation_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] Report saved to: {report_path}")
    
    return report


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python endpoint_validator.py <graph_path>")
        sys.exit(1)
    
    graph_path = sys.argv[1]
    validate_graph_file(graph_path)
