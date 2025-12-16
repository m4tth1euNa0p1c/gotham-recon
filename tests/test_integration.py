#!/usr/bin/env python3
"""
Full Integration Test for Gotham Recon Architecture
Tests the complete flow: Mission creation -> Graph updates -> Real-time events
"""
import asyncio
import json
import subprocess
import sys
import os
import time
from datetime import datetime

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

def print_info(msg: str):
    print(f"  [INFO] {msg}")

async def start_service(name: str, path: str, port: int):
    """Start a service"""
    try:
        env = os.environ.copy()
        env["KAFKA_BROKERS"] = "localhost:9092"
        env["ORCHESTRATOR_URL"] = "http://127.0.0.1:8000"
        env["GRAPH_SERVICE_URL"] = "http://127.0.0.1:8001"

        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        processes.append(process)
        await asyncio.sleep(2)

        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print_result(f"Start: {name}", False, stderr.decode()[:200])
            return None

        print_result(f"Start: {name}:{port}", True)
        return process
    except Exception as e:
        print_result(f"Start: {name}", False, str(e))
        return None

async def integration_test_flow():
    """Test the full integration flow"""
    import httpx
    import websockets

    results = {}
    mission_id = None

    print_header("Integration Test: Full Flow")

    # Step 1: Create a mission via GraphQL
    print_info("Step 1: Creating mission via GraphQL...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            mutation = """
            mutation StartMission($input: MissionInput!) {
                startMission(input: $input) {
                    id
                    targetDomain
                    status
                    mode
                }
            }
            """
            response = await client.post(
                "http://127.0.0.1:8080/graphql",
                json={
                    "query": mutation,
                    "variables": {
                        "input": {
                            "targetDomain": "integration-test.example.com",
                            "mode": "AGGRESSIVE"
                        }
                    }
                }
            )
            data = response.json()
            if "data" in data and data["data"]["startMission"]:
                mission = data["data"]["startMission"]
                mission_id = mission["id"]
                print_result("Create Mission via GraphQL", True, f"ID: {mission_id}")
                results["create_mission"] = True
            else:
                print_result("Create Mission via GraphQL", False, str(data.get("errors", "Unknown error"))[:100])
                results["create_mission"] = False
    except Exception as e:
        print_result("Create Mission via GraphQL", False, str(e))
        results["create_mission"] = False

    if not mission_id:
        return results

    # Step 2: Connect to WebSocket for graph events
    print_info("Step 2: Connecting to graph WebSocket...")
    ws_events = []
    ws_connected = False

    ws = None
    try:
        import websockets
        uri = f"ws://127.0.0.1:8001/ws/graph/{mission_id}"
        ws = await websockets.connect(uri, close_timeout=5)
        ws_connected = True

        # Wait for initial snapshot
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            ws_events.append(json.loads(msg))
        except asyncio.TimeoutError:
            pass

        print_result("WebSocket Connection", ws_connected, "Snapshot received" if ws_events else "No snapshot")
        results["websocket_connect"] = ws_connected
    except Exception as e:
        print_result("WebSocket Connection", False, str(e))
        results["websocket_connect"] = False

    # Step 3: Create nodes directly in graph-service
    print_info("Step 3: Creating nodes in graph-service...")
    nodes_created = 0
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Create domain node
            response = await client.post(
                "http://127.0.0.1:8001/api/v1/nodes",
                json={
                    "id": f"domain:{mission_id}:integration-test.example.com",
                    "type": "DOMAIN",
                    "mission_id": mission_id,
                    "properties": {"label": "integration-test.example.com"}
                }
            )
            if response.status_code == 200:
                nodes_created += 1

            # Create subdomain node
            response = await client.post(
                "http://127.0.0.1:8001/api/v1/nodes",
                json={
                    "id": f"subdomain:{mission_id}:www.integration-test.example.com",
                    "type": "SUBDOMAIN",
                    "mission_id": mission_id,
                    "properties": {"label": "www.integration-test.example.com", "risk_score": 25}
                }
            )
            if response.status_code == 200:
                nodes_created += 1

            # Create endpoint node
            response = await client.post(
                "http://127.0.0.1:8001/api/v1/nodes",
                json={
                    "id": f"endpoint:{mission_id}:/api/users",
                    "type": "ENDPOINT",
                    "mission_id": mission_id,
                    "properties": {"label": "/api/users", "method": "GET", "risk_score": 60}
                }
            )
            if response.status_code == 200:
                nodes_created += 1

        print_result("Create Nodes", nodes_created >= 2, f"Created {nodes_created} nodes")
        results["create_nodes"] = nodes_created >= 2
    except Exception as e:
        print_result("Create Nodes", False, str(e))
        results["create_nodes"] = False

    # Step 4: Create edges
    print_info("Step 4: Creating edges...")
    edges_created = 0
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://127.0.0.1:8001/api/v1/edges",
                json={
                    "from_node": f"domain:{mission_id}:integration-test.example.com",
                    "to_node": f"subdomain:{mission_id}:www.integration-test.example.com",
                    "relation": "HAS_SUBDOMAIN",
                    "mission_id": mission_id
                }
            )
            if response.status_code == 200:
                edges_created += 1

        print_result("Create Edges", edges_created >= 1, f"Created {edges_created} edges")
        results["create_edges"] = edges_created >= 1
    except Exception as e:
        print_result("Create Edges", False, str(e))
        results["create_edges"] = False

    # Step 5: Wait for and collect WebSocket events
    await asyncio.sleep(0.5)  # Allow time for events to propagate

    # Collect WebSocket events
    if ws:
        try:
            for _ in range(5):  # Try to receive up to 5 more messages
                msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                ws_events.append(json.loads(msg))
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        finally:
            try:
                await ws.close()
            except:
                pass

    # Step 5: Verify WebSocket received events
    print_info("Step 5: Verifying WebSocket events...")
    snapshot_received = any(e.get("type") == "snapshot" for e in ws_events)
    node_events = sum(1 for e in ws_events if e.get("event_type") == "node_added")
    edge_events = sum(1 for e in ws_events if e.get("event_type") == "edge_added")

    print_result("WebSocket Snapshot", snapshot_received)
    print_result("WebSocket Node Events", node_events >= 1, f"Received {node_events} node events")
    print_result("WebSocket Edge Events", edge_events >= 1, f"Received {edge_events} edge events")

    results["ws_snapshot"] = snapshot_received
    results["ws_node_events"] = node_events >= 1
    results["ws_edge_events"] = edge_events >= 1

    # Step 6: Query graph via GraphQL
    print_info("Step 6: Querying graph via GraphQL...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            query = """
            query GetNodes($missionId: String!) {
                nodes(missionId: $missionId, limit: 100) {
                    id
                    type
                    properties
                }
                edges(missionId: $missionId) {
                    fromNode
                    toNode
                    relation
                }
                graphStats(missionId: $missionId) {
                    totalNodes
                    totalEdges
                    nodesByType
                }
            }
            """
            response = await client.post(
                "http://127.0.0.1:8080/graphql",
                json={
                    "query": query,
                    "variables": {"missionId": mission_id}
                }
            )
            data = response.json()
            if "data" in data:
                nodes = data["data"]["nodes"]
                edges = data["data"]["edges"]
                stats = data["data"]["graphStats"]

                print_result("GraphQL Query Nodes", len(nodes) >= 2, f"Found {len(nodes)} nodes")
                print_result("GraphQL Query Edges", len(edges) >= 1, f"Found {len(edges)} edges")

                if stats:
                    print_result("GraphQL Query Stats", True,
                               f"Nodes: {stats['totalNodes']}, Edges: {stats['totalEdges']}")
                else:
                    print_result("GraphQL Query Stats", False)

                results["graphql_nodes"] = len(nodes) >= 2
                results["graphql_edges"] = len(edges) >= 1
                results["graphql_stats"] = stats is not None
    except Exception as e:
        print_result("GraphQL Query", False, str(e))
        results["graphql_nodes"] = False
        results["graphql_edges"] = False
        results["graphql_stats"] = False

    # Step 7: Check mission status
    print_info("Step 7: Checking mission status...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            query = """
            query GetMission($id: String!) {
                mission(id: $id) {
                    id
                    status
                    currentPhase
                    progress
                }
            }
            """
            response = await client.post(
                "http://127.0.0.1:8080/graphql",
                json={
                    "query": query,
                    "variables": {"id": mission_id}
                }
            )
            data = response.json()
            if "data" in data and data["data"]["mission"]:
                mission = data["data"]["mission"]
                print_result("Mission Status", True, f"Status: {mission['status']}, Phase: {mission.get('currentPhase', 'N/A')}")
                results["mission_status"] = True
            else:
                print_result("Mission Status", False)
                results["mission_status"] = False
    except Exception as e:
        print_result("Mission Status", False, str(e))
        results["mission_status"] = False

    return results

def cleanup():
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=2)
        except:
            try:
                p.kill()
            except:
                pass

async def run_integration_tests():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("  GOTHAM RECON - Full Integration Tests")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Start all services
    print_header("Starting Services")

    graph = await start_service("graph-service", "services/graph-service", 8001)
    orchestrator = await start_service("orchestrator", "services/recon-orchestrator", 8000)
    bff = await start_service("bff-gateway", "services/bff-gateway", 8080)

    if not all([graph, orchestrator, bff]):
        print("\n[!] Not all services started successfully")
        return

    await asyncio.sleep(2)

    # Run integration tests
    results = await integration_test_flow()

    # Summary
    print_header("Integration Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"  Total tests: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {total - passed}")
    print(f"\n  Success rate: {passed/total*100:.1f}%")

    if passed == total:
        print("\n  [SUCCESS] All integration tests passed!")
    else:
        print("\n  [WARNING] Some tests failed.")
        print("\n  Failed tests:")
        for name, passed in results.items():
            if not passed:
                print(f"    - {name}")

    return results

if __name__ == "__main__":
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        asyncio.run(run_integration_tests())
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    finally:
        print("\nCleaning up...")
        cleanup()
        print("Done.")
