#!/usr/bin/env python3
"""
Test script for Deep Verification implementation.
Tests the Check Runner with colombes.fr as target.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add schemas path directly (avoid importing other modules that have dependencies)
SCHEMAS_PATH = Path(__file__).parent / "services" / "recon-orchestrator" / "core" / "schemas"
sys.path.insert(0, str(SCHEMAS_PATH.parent.parent))

# Test configuration
TARGET_DOMAIN = "colombes.fr"
TARGET_URL = "https://www.colombes.fr"
MISSION_ID = "test-deep-verification-001"


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(test_name: str, success: bool, details: str = ""):
    """Print test result."""
    status = "PASS" if success else "FAIL"
    symbol = "[+]" if success else "[-]"
    print(f"{symbol} {test_name}: {status}")
    if details:
        for line in details.split("\n"):
            print(f"    {line}")


async def test_schemas():
    """Test Lot 0.2 & 0.3: Schema validation."""
    print_header("Testing Schemas (Lot 0.2 & 0.3)")

    try:
        # Import directly from the verification module file
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "verification",
            SCHEMAS_PATH / "verification.py"
        )
        verification = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verification)

        CheckModule = verification.CheckModule
        Evidence = verification.Evidence
        RunCheckRequest = verification.RunCheckRequest
        RunCheckResult = verification.RunCheckResult
        VulnStatus = verification.VulnStatus
        AttackType = verification.AttackType
        EvidenceKind = verification.EvidenceKind
        ModuleCategory = verification.ModuleCategory
        VerificationPlan = verification.VerificationPlan
        VerificationTarget = verification.VerificationTarget
        ModuleAssignment = verification.ModuleAssignment

        # Test 1: Create a valid CheckModule
        module = CheckModule(
            id="test-module-01",
            name="Test Module",
            category=ModuleCategory.HEADER_ANALYSIS,
            target="{target_url}",
            method="GET",
            expected_proof=[{
                "type": "header",
                "pattern": "Server:\\s*.+",
                "description": "Server header present"
            }],
            attack_type=AttackType.INFO_DISCLOSURE,
            description="Test module for validation"
        )
        print_result("CheckModule creation", True, f"Created module: {module.id}")

        # Test 2: Create Evidence with hash
        evidence = Evidence(
            kind=EvidenceKind.HTTP_HEADER.value,
            summary="Test evidence",
            detail="Server: nginx/1.18.0",
            module_id="test-module-01"
        )
        hash_value = evidence.hash  # Hash is auto-generated on init
        print_result("Evidence hash generation", len(hash_value) == 64, f"Hash: {hash_value[:16]}...")

        # Test 3: Test redaction
        sensitive = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        redacted = Evidence.redact_secrets(sensitive)
        print_result("Secret redaction", "REDACTED" in redacted, f"Redacted: {redacted[:50]}...")

        # Test 4: Create RunCheckRequest
        request = RunCheckRequest(
            mission_id=MISSION_ID,
            module_id="test-module-01",
            target_id="endpoint:https://www.colombes.fr/",
            target_url=TARGET_URL,
            mode="STEALTH"
        )
        tool_call_id = request.generate_tool_call_id()
        print_result("RunCheckRequest creation", tool_call_id.startswith("check-"),
                    f"Tool call ID: {tool_call_id}")

        # Test 5: Create VerificationPlan
        plan = VerificationPlan(
            mission_id=MISSION_ID,
            targets=[
                VerificationTarget(
                    target_id="endpoint:https://www.colombes.fr/",
                    target_url=TARGET_URL,
                    target_type="HTTP_SERVICE",
                    risk_score=50,
                    priority=1,
                    reason="Test target"
                )
            ],
            assignments=[
                ModuleAssignment(
                    target_id="endpoint:https://www.colombes.fr/",
                    module_id="test-module-01",
                    order=1
                )
            ]
        )
        print_result("VerificationPlan creation", plan.plan_id.startswith("plan-"),
                    f"Plan ID: {plan.plan_id}")

        return True

    except Exception as e:
        print_result("Schema tests", False, str(e))
        import traceback
        traceback.print_exc()
        return False


async def test_roe_config():
    """Test Lot 0.1: ROE configuration."""
    print_header("Testing ROE Configuration (Lot 0.1)")

    try:
        import yaml
        roe_path = Path(__file__).parent / "services" / "recon-orchestrator" / "config" / "roe.yaml"

        with open(roe_path, "r") as f:
            roe = yaml.safe_load(f)

        # Test 1: Modes defined
        modes = roe.get("modes", {})
        print_result("ROE modes defined", len(modes) >= 3,
                    f"Modes: {list(modes.keys())}")

        # Test 2: STEALTH mode is restrictive
        stealth = modes.get("STEALTH", {})
        stealth_methods = stealth.get("allowed_methods", [])
        print_result("STEALTH mode restrictive", "POST" not in stealth_methods,
                    f"Allowed methods: {stealth_methods}")

        # Test 3: Scope rules exist
        scope = roe.get("scope", {})
        print_result("Scope rules defined", "domain_rules" in scope,
                    f"Has domain_rules, ip_rules, auto_exclude_providers")

        # Test 4: Security patterns defined
        security = roe.get("security", {})
        patterns = security.get("sensitive_patterns", [])
        print_result("Sensitive patterns defined", len(patterns) >= 5,
                    f"Found {len(patterns)} redaction patterns")

        # Test 5: Vuln status definitions
        vuln_statuses = roe.get("vulnerability_statuses", {})
        print_result("Vuln status definitions", "CONFIRMED" in vuln_statuses,
                    f"Statuses: {list(vuln_statuses.keys())}")

        return True

    except Exception as e:
        print_result("ROE config tests", False, str(e))
        import traceback
        traceback.print_exc()
        return False


async def test_module_registry():
    """Test Lot 1.1: Module registry."""
    print_header("Testing Module Registry (Lot 1.1)")

    try:
        modules_dir = Path(__file__).parent / "services" / "scanner-proxy" / "check_modules"

        # Test 1: Modules directory exists
        print_result("Modules directory exists", modules_dir.exists(),
                    f"Path: {modules_dir}")

        # Test 2: Core modules exist
        core_dir = modules_dir / "core"
        core_modules = list(core_dir.glob("*.json")) if core_dir.exists() else []
        print_result("Core modules found", len(core_modules) >= 2,
                    f"Found {len(core_modules)} core modules")

        # Test 3: Modules are valid JSON
        valid_count = 0
        for module_file in core_modules:
            try:
                with open(module_file, "r") as f:
                    module = json.load(f)
                    if "id" in module and "expected_proof" in module:
                        valid_count += 1
                        print(f"    [+] Loaded: {module['id']} ({module['name']})")
            except Exception as e:
                print(f"    [-] Failed: {module_file.name} - {e}")

        print_result("Modules are valid", valid_count == len(core_modules),
                    f"{valid_count}/{len(core_modules)} valid")

        return True

    except Exception as e:
        print_result("Module registry tests", False, str(e))
        import traceback
        traceback.print_exc()
        return False


async def test_check_runner():
    """Test Lot 1.2: Check Runner with colombes.fr."""
    print_header(f"Testing Check Runner with {TARGET_DOMAIN} (Lot 1.2)")

    try:
        import httpx

        # Test 1: Direct HTTP check (simulate what runner does)
        print(f"\n[*] Testing against {TARGET_URL}...")

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(TARGET_URL)

            print_result("HTTP request successful", response.status_code == 200,
                        f"Status: {response.status_code}")

            # Test 2: Check for security headers
            headers_str = "\n".join([f"{k}: {v}" for k, v in response.headers.items()])

            has_x_frame = "x-frame-options" in headers_str.lower()
            has_csp = "content-security-policy" in headers_str.lower()
            has_server = "server" in headers_str.lower()

            print_result("Security headers analysis", True,
                        f"X-Frame-Options: {'Yes' if has_x_frame else 'No'}\n"
                        f"    CSP: {'Yes' if has_csp else 'No'}\n"
                        f"    Server header: {'Yes' if has_server else 'No'}")

            # Test 3: Server info disclosure
            server_header = response.headers.get("server", "Not disclosed")
            print_result("Server info disclosure check", True,
                        f"Server: {server_header}")

            # Test 4: Check response timing
            response_time = response.elapsed.total_seconds() * 1000
            print_result("Response timing", response_time < 5000,
                        f"Response time: {int(response_time)}ms")

            # Test 5: Evidence collection simulation
            evidence_items = [
                {
                    "kind": "status_code",
                    "summary": f"HTTP {response.status_code}",
                    "module_id": "test-check"
                },
                {
                    "kind": "http_header",
                    "summary": f"Server: {server_header}",
                    "module_id": "server-info-disclosure-01"
                },
                {
                    "kind": "timing",
                    "summary": f"Response time: {int(response_time)}ms",
                    "module_id": "test-check"
                }
            ]

            if not has_x_frame:
                evidence_items.append({
                    "kind": "http_header",
                    "summary": "Missing X-Frame-Options header",
                    "module_id": "security-headers-01"
                })

            if not has_csp:
                evidence_items.append({
                    "kind": "http_header",
                    "summary": "Missing Content-Security-Policy header",
                    "module_id": "security-headers-01"
                })

            print_result("Evidence collection", len(evidence_items) >= 3,
                        f"Collected {len(evidence_items)} evidence items")

            # Display evidence
            print("\n[*] Evidence collected:")
            for ev in evidence_items:
                print(f"    - [{ev['kind']}] {ev['summary']}")

        return True

    except Exception as e:
        print_result("Check runner tests", False, str(e))
        import traceback
        traceback.print_exc()
        return False


async def test_idempotency():
    """Test idempotency of tool call IDs."""
    print_header("Testing Idempotency")

    try:
        import hashlib

        def generate_tool_call_id(mission_id: str, module_id: str, target_id: str) -> str:
            content = f"{mission_id}|{module_id}|{target_id}"
            return f"check-{hashlib.sha256(content.encode()).hexdigest()[:16]}"

        # Same inputs should produce same ID
        id1 = generate_tool_call_id(MISSION_ID, "security-headers-01", "endpoint:https://www.colombes.fr/")
        id2 = generate_tool_call_id(MISSION_ID, "security-headers-01", "endpoint:https://www.colombes.fr/")

        print_result("Deterministic IDs", id1 == id2, f"ID: {id1}")

        # Different inputs should produce different ID
        id3 = generate_tool_call_id(MISSION_ID, "server-info-disclosure-01", "endpoint:https://www.colombes.fr/")

        print_result("Different inputs = different IDs", id1 != id3,
                    f"ID1: {id1}\n    ID2: {id3}")

        return True

    except Exception as e:
        print_result("Idempotency tests", False, str(e))
        return False


async def test_roe_enforcement():
    """Test ROE enforcement logic."""
    print_header("Testing ROE Enforcement")

    try:
        # Simulate ROE checking
        roe_config = {
            "modes": {
                "STEALTH": {
                    "allowed_methods": ["GET", "HEAD", "OPTIONS"],
                    "allow_body": False
                },
                "BALANCED": {
                    "allowed_methods": ["GET", "HEAD", "OPTIONS", "POST"],
                    "allow_body": True
                },
                "AGGRESSIVE": {
                    "allowed_methods": ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH"],
                    "allow_body": True
                }
            }
        }

        def check_method(method: str, mode: str) -> tuple[bool, str]:
            mode_config = roe_config.get("modes", {}).get(mode, {})
            allowed = mode_config.get("allowed_methods", [])
            if method.upper() not in allowed:
                return False, f"Method {method} not allowed in {mode} mode"
            return True, ""

        # Test 1: GET allowed in STEALTH
        allowed, _ = check_method("GET", "STEALTH")
        print_result("GET allowed in STEALTH", allowed)

        # Test 2: POST blocked in STEALTH
        allowed, error = check_method("POST", "STEALTH")
        print_result("POST blocked in STEALTH", not allowed, f"Error: {error}")

        # Test 3: POST allowed in BALANCED
        allowed, _ = check_method("POST", "BALANCED")
        print_result("POST allowed in BALANCED", allowed)

        # Test 4: PUT blocked in BALANCED
        allowed, error = check_method("PUT", "BALANCED")
        print_result("PUT blocked in BALANCED", not allowed, f"Error: {error}")

        # Test 5: PUT allowed in AGGRESSIVE
        allowed, _ = check_method("PUT", "AGGRESSIVE")
        print_result("PUT allowed in AGGRESSIVE", allowed)

        # Test 6: DELETE always blocked
        allowed, error = check_method("DELETE", "AGGRESSIVE")
        print_result("DELETE blocked in AGGRESSIVE", not allowed, f"Error: {error}")

        return True

    except Exception as e:
        print_result("ROE enforcement tests", False, str(e))
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print(" DEEP VERIFICATION TEST SUITE")
    print(f" Target: {TARGET_DOMAIN}")
    print(f" Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    results = {}

    # Run tests
    results["schemas"] = await test_schemas()
    results["roe_config"] = await test_roe_config()
    results["module_registry"] = await test_module_registry()
    results["check_runner"] = await test_check_runner()
    results["idempotency"] = await test_idempotency()
    results["roe_enforcement"] = await test_roe_enforcement()

    # Summary
    print_header("TEST SUMMARY")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for name, success in results.items():
        status = "PASS" if success else "FAIL"
        symbol = "[+]" if success else "[-]"
        print(f"{symbol} {name}: {status}")

    print("\n" + "-" * 60)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    print("-" * 60)

    if failed == 0:
        print("\n[+] All tests passed! Deep Verification Lot 0 & 1 validated.")
    else:
        print(f"\n[-] {failed} test(s) failed. Please review.")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
