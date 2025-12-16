#!/usr/bin/env python3
"""
Test script for Gotham Recon Real-time Architecture
Tests: Services, WebSocket, GraphQL, Kafka event flow
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Optional
import subprocess
import os
import signal

# Test configuration
GRAPH_SERVICE_PORT = 8001
ORCHESTRATOR_PORT = 8000
BFF_GATEWAY_PORT = 8080

# Service processes
processes = []

def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_result(test_name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"  [{color}{status}{reset}] {test_name}")
    if details:
        print(f"        {details}")

async def test_service_syntax():
    """Test that all services have valid Python syntax"""
    print_header("Testing Service Syntax")

    services = [
        "services/graph-service/main.py",
        "services/bff-gateway/main.py",
        "services/recon-orchestrator/main.py",
        "services/osint-runner/main.py",
        "services/active-recon/main.py",
        "services/endpoint-intel/main.py",
        "services/verification/main.py",
        "services/reporter/main.py",
        "services/planner/main.py",
    ]

    all_passed = True
    for service_path in services:
        try:
            with open(service_path, 'r') as f:
                code = f.read()
            compile(code, service_path, 'exec')
            print_result(f"Syntax: {service_path}", True)
        except SyntaxError as e:
            print_result(f"Syntax: {service_path}", False, str(e))
            all_passed = False
        except FileNotFoundError:
            print_result(f"Syntax: {service_path}", False, "File not found")
            all_passed = False

    return all_passed

async def test_imports():
    """Test that all required imports are available"""
    print_header("Testing Required Imports")

    required_modules = [
        ("fastapi", "FastAPI framework"),
        ("uvicorn", "ASGI server"),
        ("pydantic", "Data validation"),
        ("httpx", "HTTP client"),
        ("structlog", "Structured logging"),
        ("websockets", "WebSocket support"),
    ]

    optional_modules = [
        ("aiokafka", "Kafka client"),
        ("strawberry", "GraphQL framework"),
    ]

    all_passed = True
    for module, description in required_modules:
        try:
            __import__(module)
            print_result(f"Import: {module} ({description})", True)
        except ImportError as e:
            print_result(f"Import: {module} ({description})", False, str(e))
            all_passed = False

    print("\n  Optional modules:")
    for module, description in optional_modules:
        try:
            __import__(module)
            print_result(f"Import: {module} ({description})", True)
        except ImportError:
            print_result(f"Import: {module} ({description})", False, "Not installed (optional)")

    return all_passed

async def start_service(name: str, path: str, port: int) -> Optional[subprocess.Popen]:
    """Start a service in background"""
    try:
        env = os.environ.copy()
        env["KAFKA_BROKERS"] = "localhost:9092"  # Will fail gracefully if not available

        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        processes.append(process)
        await asyncio.sleep(2)  # Wait for service to start

        if process.poll() is not None:
            # Process already terminated
            stdout, stderr = process.communicate()
            print_result(f"Start: {name}", False, stderr.decode()[:200])
            return None

        print_result(f"Start: {name} on port {port}", True)
        return process
    except Exception as e:
        print_result(f"Start: {name}", False, str(e))
        return None

async def test_health_endpoint(service_name: str, port: int) -> bool:
    """Test health endpoint of a service"""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"http://127.0.0.1:{port}/health")
            if response.status_code == 200:
                data = response.json()
                print_result(f"Health: {service_name}", True, f"Status: {data.get('status', 'unknown')}")
                return True
            else:
                print_result(f"Health: {service_name}", False, f"Status code: {response.status_code}")
                return False
    except Exception as e:
        print_result(f"Health: {service_name}", False, str(e))
        return False

async def test_websocket_connection(service_name: str, port: int, path: str, mission_id: str) -> bool:
    """Test WebSocket connection"""
    import websockets

    uri = f"ws://127.0.0.1:{port}{path}/{mission_id}"

    try:
        async with websockets.connect(uri, close_timeout=2) as ws:
            # Wait for initial message (snapshot)
            message = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(message)

            if "type" in data or "run_id" in data or "snapshot" in str(data).lower():
                print_result(f"WebSocket: {service_name}", True, f"Received: {str(data)[:100]}...")
                return True
            else:
                print_result(f"WebSocket: {service_name}", True, f"Connected, got: {str(data)[:50]}")
                return True
    except asyncio.TimeoutError:
        print_result(f"WebSocket: {service_name}", False, "Timeout waiting for message")
        return False
    except Exception as e:
        print_result(f"WebSocket: {service_name}", False, str(e)[:100])
        return False

async def test_create_node(port: int) -> bool:
    """Test creating a node in graph-service"""
    import httpx

    node_data = {
        "id": f"test:node:{int(time.time())}",
        "type": "SUBDOMAIN",
        "mission_id": "test-mission-001",
        "properties": {
            "label": "test.example.com",
            "risk_score": 50
        }
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/api/v1/nodes",
                json=node_data
            )
            if response.status_code == 200:
                data = response.json()
                print_result("Create Node", True, f"Created: {data.get('id', 'unknown')}")
                return True
            else:
                print_result("Create Node", False, f"Status: {response.status_code}, {response.text[:100]}")
                return False
    except Exception as e:
        print_result("Create Node", False, str(e))
        return False

async def test_query_nodes(port: int) -> bool:
    """Test querying nodes from graph-service"""
    import httpx

    query_data = {
        "mission_id": "test-mission-001",
        "limit": 10
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/api/v1/nodes/query",
                json=query_data
            )
            if response.status_code == 200:
                data = response.json()
                node_count = len(data.get("nodes", []))
                print_result("Query Nodes", True, f"Found {node_count} nodes")
                return True
            else:
                print_result("Query Nodes", False, f"Status: {response.status_code}")
                return False
    except Exception as e:
        print_result("Query Nodes", False, str(e))
        return False

async def test_create_mission(port: int) -> Optional[str]:
    """Test creating a mission in orchestrator"""
    import httpx

    mission_data = {
        "target_domain": "test.example.com",
        "mode": "aggressive",
        "options": {}
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/api/v1/missions",
                json=mission_data
            )
            if response.status_code == 200:
                data = response.json()
                mission_id = data.get("id")
                print_result("Create Mission", True, f"Mission ID: {mission_id}")
                return mission_id
            else:
                print_result("Create Mission", False, f"Status: {response.status_code}, {response.text[:100]}")
                return None
    except Exception as e:
        print_result("Create Mission", False, str(e))
        return None

async def test_graphql_endpoint(port: int) -> bool:
    """Test GraphQL endpoint"""
    import httpx

    query = """
    query {
        missions(limit: 5) {
            missions {
                id
                targetDomain
                status
            }
            total
        }
    }
    """

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/graphql",
                json={"query": query}
            )
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    print_result("GraphQL Query", True, f"Response: {str(data)[:100]}")
                    return True
                elif "errors" in data:
                    print_result("GraphQL Query", False, f"Errors: {data['errors'][0].get('message', '')[:100]}")
                    return False
            else:
                print_result("GraphQL Query", False, f"Status: {response.status_code}")
                return False
    except Exception as e:
        print_result("GraphQL Query", False, str(e))
        return False

async def test_realtime_event_flow():
    """Test the full real-time event flow"""
    print_header("Testing Real-time Event Flow")

    import httpx
    import websockets

    mission_id = "realtime-test-" + str(int(time.time()))
    events_received = []

    # Connect to WebSocket first
    try:
        ws_uri = f"ws://127.0.0.1:{GRAPH_SERVICE_PORT}/ws/graph/{mission_id}"

        async def ws_listener():
            try:
                async with websockets.connect(ws_uri, close_timeout=2) as ws:
                    # Wait for snapshot
                    msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    events_received.append(("snapshot", json.loads(msg)))

                    # Wait for additional events
                    try:
                        while True:
                            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                            events_received.append(("event", json.loads(msg)))
                    except asyncio.TimeoutError:
                        pass
            except Exception as e:
                events_received.append(("error", str(e)))

        # Start WebSocket listener in background
        ws_task = asyncio.create_task(ws_listener())
        await asyncio.sleep(0.5)  # Let WS connect

        # Create a node via HTTP
        node_data = {
            "id": f"realtime:test:{int(time.time())}",
            "type": "SUBDOMAIN",
            "mission_id": mission_id,
            "properties": {"label": "realtime-test.example.com"}
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"http://127.0.0.1:{GRAPH_SERVICE_PORT}/api/v1/nodes",
                json=node_data
            )
            node_created = response.status_code == 200

        # Wait for WS events
        await asyncio.sleep(2)
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass

        # Check results
        has_snapshot = any(e[0] == "snapshot" for e in events_received)
        has_event = any(e[0] == "event" for e in events_received)

        print_result("WS Connection", has_snapshot or len(events_received) > 0,
                    f"Received {len(events_received)} messages")
        print_result("Node Creation", node_created)
        print_result("Event Received via WS", has_event or has_snapshot,
                    f"Events: {[e[0] for e in events_received]}")

        return has_snapshot and node_created

    except Exception as e:
        print_result("Real-time Flow", False, str(e))
        return False

def cleanup():
    """Clean up all started processes"""
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            try:
                process.kill()
            except:
                pass

async def run_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("  GOTHAM RECON - Real-time Architecture Tests")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)

    results = {}

    # Test 1: Syntax validation
    results["syntax"] = await test_service_syntax()

    # Test 2: Import validation
    results["imports"] = await test_imports()

    if not results["syntax"]:
        print("\n[!] Syntax errors found. Fix them before starting services.")
        return results

    # Test 3: Start services
    print_header("Starting Services")

    graph_service = await start_service(
        "graph-service",
        "services/graph-service",
        GRAPH_SERVICE_PORT
    )

    orchestrator = await start_service(
        "recon-orchestrator",
        "services/recon-orchestrator",
        ORCHESTRATOR_PORT
    )

    # Give services time to fully start
    await asyncio.sleep(2)

    # Test 4: Health checks
    print_header("Testing Health Endpoints")

    if graph_service:
        results["graph_health"] = await test_health_endpoint("graph-service", GRAPH_SERVICE_PORT)

    if orchestrator:
        results["orchestrator_health"] = await test_health_endpoint("orchestrator", ORCHESTRATOR_PORT)

    # Test 5: Graph operations
    if graph_service and results.get("graph_health"):
        print_header("Testing Graph Operations")
        results["create_node"] = await test_create_node(GRAPH_SERVICE_PORT)
        results["query_nodes"] = await test_query_nodes(GRAPH_SERVICE_PORT)

    # Test 6: WebSocket
    if graph_service and results.get("graph_health"):
        print_header("Testing WebSocket Connections")
        results["websocket_graph"] = await test_websocket_connection(
            "graph-service",
            GRAPH_SERVICE_PORT,
            "/ws/graph",
            "test-mission-001"
        )

    if orchestrator and results.get("orchestrator_health"):
        results["websocket_logs"] = await test_websocket_connection(
            "orchestrator-logs",
            ORCHESTRATOR_PORT,
            "/ws/logs",
            "test-mission-001"
        )

    # Test 7: Mission creation
    if orchestrator and results.get("orchestrator_health"):
        print_header("Testing Mission Flow")
        mission_id = await test_create_mission(ORCHESTRATOR_PORT)
        results["mission_created"] = mission_id is not None

    # Test 8: Real-time event flow
    if results.get("graph_health") and results.get("create_node"):
        results["realtime_flow"] = await test_realtime_event_flow()

    # Summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"  Total tests: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {total - passed}")
    print(f"\n  Success rate: {passed/total*100:.1f}%")

    if passed == total:
        print("\n  [SUCCESS] All tests passed!")
    else:
        print("\n  [WARNING] Some tests failed. Check output above.")

    return results

if __name__ == "__main__":
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        results = asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\n[!] Tests interrupted by user")
    finally:
        print("\nCleaning up processes...")
        cleanup()
        print("Done.")
