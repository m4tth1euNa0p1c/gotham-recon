from typing import List, Dict, Generator, Tuple, Optional

def iter_paths_sub_http_js(graph_data: Dict) -> Generator[Tuple[Dict, Dict, Optional[Dict], List[Dict], List[Dict]], None, None]:
    """
    Iterate over paths: SUBDOMAIN -> HTTP_SERVICE [-> JS_FILE].
    Also traverses:
    - SUBDOMAIN -> RESOLVES_TO -> IP -> BELONGS_TO -> ASN (Infra)
    - SUBDOMAIN -> HAS_RECORD -> DNS_RECORD (DNS)
    - HTTP_SERVICE -> EXPOSES_ENDPOINT -> ENDPOINT
    
    Yields tuple of (subdomain_node, http_node, js_node_or_None, infra_nodes, dns_nodes, endpoint_nodes, vuln_nodes).
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    
    node_index = {n["id"]: n for n in nodes}
    
    sub_to_http = {}
    http_to_js = {}
    sub_to_ip = {}
    ip_to_asn = {}
    sub_to_dns = {}
    sub_to_dns = {}
    http_to_endpoints = {}
    node_to_vulns = {}
    
    for edge in edges:
        rel = edge.get("type") or edge.get("relation", "")  # Support both field names
        src = edge["from"]
        dst = edge["to"]
        
        if rel == "EXPOSES_HTTP":
            sub_to_http.setdefault(src, []).append(dst)
        elif rel == "LOADS_JS":
            http_to_js.setdefault(src, []).append(dst)
        elif rel == "EXPOSES_ENDPOINT":
            http_to_endpoints.setdefault(src, []).append(dst)
        elif rel == "RESOLVES_TO":
            sub_to_ip.setdefault(src, []).append(dst)
        elif rel == "BELONGS_TO":
            ip_to_asn.setdefault(src, []).append(dst)
        elif rel == "HAS_RECORD":
            sub_to_dns.setdefault(src, []).append(dst)
        elif rel.startswith("AFFECTS"):
            # VULNERABILITY -> TARGET
            node_to_vulns.setdefault(dst, []).append(src)

    for node in nodes:
        if node["type"] != "SUBDOMAIN":
            continue
            
        sub_id = node["id"]
        
        # Resolve Infra (IP + ASN)
        infra_nodes = []
        ip_ids = sub_to_ip.get(sub_id, [])
        for ip_id in ip_ids:
            ip_node = node_index.get(ip_id)
            if ip_node:
                infra_nodes.append(ip_node)
                # ASN
                asn_ids = ip_to_asn.get(ip_id, [])
                for asn_id in asn_ids:
                    asn_node = node_index.get(asn_id)
                    if asn_node: infra_nodes.append(asn_node)
        
        # Resolve DNS Records
        dns_nodes = []
        dns_ids = sub_to_dns.get(sub_id, [])
        for d_id in dns_ids:
            d_node = node_index.get(d_id)
            if d_node: dns_nodes.append(d_node)
        
        # Resolve HTTP/JS
        http_ids = sub_to_http.get(sub_id, [])
        
        # Even if no HTTP service, if we have interesting DNS/Infra, we might want to surface it.
        # Even if no HTTP service, if we have interesting DNS/Infra, we might want to surface it.
        # Resolve Vulnerabilities (Collect from Subdomain, HTTP, JS, Endpoints)
        vuln_nodes = []
        
        # Helper to collect vulns for a node
        def collect_vulns(nid):
            v_ids = node_to_vulns.get(nid, [])
            for v_id in v_ids:
                v_node = node_index.get(v_id)
                if v_node: vuln_nodes.append(v_node)
        
        collect_vulns(sub_id)
        
        for h_id in http_ids:
            http_node = node_index.get(h_id)
            if not http_node: continue
            
            collect_vulns(h_id)
            
            js_ids = http_to_js.get(h_id, [])
            for j_id in js_ids: collect_vulns(j_id)
            
            # Resolve Endpoints
            ep_ids = http_to_endpoints.get(h_id, [])
            endpoint_nodes = []
            for ep_id in ep_ids:
                ep_node = node_index.get(ep_id)
                if ep_node: 
                    endpoint_nodes.append(ep_node)
                    collect_vulns(ep_id)
            
            # Deduplicate Vulns
            unique_vulns = {v["id"]: v for v in vuln_nodes}
            vuln_nodes_list = list(unique_vulns.values())

            if js_ids:
                for j_id in js_ids:
                    js_node = node_index.get(j_id)
                    if js_node:
                        yield (node, http_node, js_node, infra_nodes, dns_nodes, endpoint_nodes, vuln_nodes_list)
            else:
                yield (node, http_node, None, infra_nodes, dns_nodes, endpoint_nodes, vuln_nodes_list)
        
        if not http_ids and (infra_nodes or dns_nodes):
             # Yield without HTTP but check sub vulns
            unique_vulns = {v["id"]: v for v in vuln_nodes}
            vuln_nodes_list = list(unique_vulns.values())
            yield (node, {}, None, infra_nodes, dns_nodes, [], vuln_nodes_list)

def score_path(subnode: Dict, httpnode: Dict, jsnode: Optional[Dict], infra_nodes: List[Dict], dns_nodes: List[Dict], endpoint_nodes: List[Dict], vuln_nodes: List[Dict] = [], memory_boost: int = 0) -> Tuple[int, List[str]]:
    """
    Score an attack path based on node properties, keywords, and infrastructure.
    """
    score = 0
    reasons = []
    
    # --- 0. Memory Boost ---
    if memory_boost > 0:
        score += memory_boost
        reasons.append(f"Memory Boost (+{memory_boost})")
    
    # --- 1. Subdomain Analysis ---
    sub_props = subnode.get("properties", {})
    score += sub_props.get("priority", 0)
    
    tag = str(sub_props.get("tag", "")).upper()
    sub_name = subnode.get("id", "").lower()
    
    # Tag Bonuses
    if "AUTH" in tag or "login" in sub_name:
        score += 5
        reasons.append("Auth Portal (+5)")
    elif "BACKUP" in tag or "backup" in sub_name:
        score += 4 # User requested ranking backup high
        reasons.append("Backup Exposed (+4)")
    elif "ADMIN" in tag or "admin" in sub_name:
        score += 5
        reasons.append("Admin Panel (+5)")
    elif "DEV" in tag or "dev" in sub_name or "staging" in sub_name:
        score += 4
        reasons.append("Dev Environment (+4)")
    elif "MAIL" in tag or "MAILING" in tag or "mail" in sub_name:
        score += 4
        reasons.append("Mailing System (+4)")
    
    category = str(sub_props.get("category", "")).upper()
    if "APP_BACKEND" in category:
        score += 3
        reasons.append("App Backend (+3)")

    # --- 2. Infra Analysis ---
    # Deduplicate ASN orgs to avoid double counting
    asns = [n for n in infra_nodes if n["type"] == "ASN"]
    seen_orgs = set()
    
    for node in asns:
        org = node.get("properties", {}).get("org", "").lower()
        if org in seen_orgs: continue
        seen_orgs.add(org)
        
        if "cloudflare" in org or "akamai" in org or "fastly" in org:
            score -= 1
            reasons.append(f"CDN Protected (-1)")
        elif "ovh" in org:
            score += 3
            reasons.append(f"OVH Backend (+3)")
        elif "amazon" in org or "aws" in org:
            score += 1
            reasons.append(f"AWS Infra (+1)")

    # --- 3. DNS Analysis ---
    has_mx = False
    has_spf = False
    has_dmarc = False
    
    for node in dns_nodes:
        if node["type"] == "DNS_RECORD":
            rtype = node.get("properties", {}).get("type", "")
            val = node.get("properties", {}).get("value", "")
            
            if rtype == "MX":
                has_mx = True
            if rtype == "TXT":
                if "v=spf1" in val: has_spf = True
                if "v=DMARC1" in val: has_dmarc = True
    
    if has_mx and has_spf:
        score += 2
        reasons.append("Structured Emailing (+2)")
        
    if has_mx and not has_dmarc:
        score += 1
        reasons.append("Missing DMARC (+1)")

    # --- 4. Technology Bonus ---
    technologies = httpnode.get("properties", {}).get("technologies", [])
    if technologies:
        if any(tech in technologies for tech in ["Express", "Spring", "Django", "Laravel", "Node.js"]):
            score += 3
            reasons.append("Backend Stack (+3)")

    # --- 5. JS File Analysis ---
    if jsnode:
        js_url = str(jsnode.get("properties", {}).get("url", "")).lower()
        high_kw = ["auth", "api", "secrets", "config", "key"]
        
        if any(k in js_url for k in high_kw):
            score += 3
            score += 3
            reasons.append("Sensitive JS Keyword (+3)")

    # --- 6. Endpoint Analysis (Enhanced for Phase 23) ---
    if endpoint_nodes:
        # Check count
        if len(endpoint_nodes) > 0:
            reasons.append(f"Endpoints Found (+{min(len(endpoint_nodes), 5)})")
            score += min(len(endpoint_nodes), 5) # Cap at 5 points for volume
            
        admin_bonus = False
        api_bonus = False
        high_risk_bonus = False
        
        for ep in endpoint_nodes:
            props = ep.get("properties", {})
            path = props.get("path", "").lower()
            source = props.get("source", "")
            method = props.get("method", "")
            
            # Phase 23: Category-based scoring
            category = props.get("category", "").upper()
            if category in ("ADMIN", "AUTH") and not admin_bonus:
                score += 4
                reasons.append(f"{category} Endpoint (+4)")
                admin_bonus = True
            elif category == "API" and not api_bonus:
                score += 2
                reasons.append("API Endpoint (+2)")
                api_bonus = True
            elif category == "LEGACY":
                score += 2
                reasons.append("Legacy Endpoint (+2)")
            
            # Phase 23: Risk score-based boost
            risk_score = props.get("risk_score", 0)
            if risk_score >= 70 and not high_risk_bonus:
                bonus = min(5, risk_score // 20)  # 70-79: +3, 80-99: +4, 100: +5
                score += bonus
                reasons.append(f"High Risk Endpoint ({risk_score}) (+{bonus})")
                high_risk_bonus = True
            
            # Phase 23: Behavior-based scoring
            behavior = props.get("behavior_hint", "")
            if behavior == "STATE_CHANGING":
                score += 2
                reasons.append("State Changing Behavior (+2)")
            elif behavior == "ID_BASED_ACCESS":
                score += 1
                reasons.append("ID-Based Access (IDOR potential) (+1)")
            
            # Legacy path-based checks (fallback if no Phase 23 category)
            if not admin_bonus and ("/admin" in path or "/auth" in path or "/login" in path):
                score += 3
                reasons.append("Admin/Auth Endpoint (+3)")
                admin_bonus = True
            
            if not api_bonus and "/api/" in path:
                score += 1
                reasons.append("API Endpoint (+1)")
                api_bonus = True
                
            # Hidden Sources (Accumulate freely or cap?)
            if source == "WAYBACK":
                score += 2
                reasons.append("Historical Endpoint (+2)")
            if source == "ROBOTS":
                score += 2
                reasons.append("Robots Disallow (+2)")
                
            # Interesting Methods
            if method == "POST" or method == "PUT":
                score += 1
                reasons.append("State Changing Method (+1)")
            
    # --- 7. Vulnerability Analysis ---
    if vuln_nodes:
        for v in vuln_nodes:
            props = v.get("properties", {})
            severity = props.get("severity", "LOW")
            name = props.get("name", "Unknown")
            confirmed = props.get("confirmed", False)
            
            val = 1
            if severity == "CRITICAL": val = 7
            elif severity == "HIGH": val = 5
            elif severity == "MEDIUM": val = 3
            
            if confirmed:
                val += 3
                reasons.append(f"CONFIRMED Vulnerability: {name} (+3)")
            
            score += val
            reasons.append(f"{severity} Vulnerability: {name} (+{val})")

    return score, list(set(reasons))

def suggest_actions(subnode: Dict, httpnode: Dict, jsnode: Optional[Dict], dns_nodes: List[Dict], endpoint_nodes: List[Dict], vuln_nodes: List[Dict] = []) -> List[str]:
    """
    Suggest next actions for a path.
    Phase 23 Fix: Gate offensive actions (nuclei, ffuf) based on risk thresholds.
    """
    actions = []
    
    # Phase 23: Calculate max endpoint risk for this path
    max_endpoint_risk = 0
    has_high_value_category = False
    has_high_priority_endpoint = False
    
    for ep in endpoint_nodes:
        props = ep.get("properties", {})
        risk = props.get("risk_score", 0)
        category = props.get("category", "").upper()
        
        if risk > max_endpoint_risk:
            max_endpoint_risk = risk
        if category in ("ADMIN", "AUTH", "API"):
            has_high_value_category = True
        if risk >= 50:
            has_high_priority_endpoint = True
    
    # HTTP Actions - only suggest nuclei if there's something worth scanning
    if httpnode.get("id"):
        # Gate: Only suggest nuclei_scan if risk >= 30 OR high-value category
        if max_endpoint_risk >= 30 or has_high_value_category or vuln_nodes:
            actions.append("nuclei_scan")
        if jsnode: 
            actions.append("parameter_mining")
    else:
        # Infra Only Actions
        actions.append("dns_audit")
        
    # Endpoint-specific actions - gated by risk
    if endpoint_nodes:
        # Gate: Only suggest ffuf if risk >= 40 OR high-value category
        if max_endpoint_risk >= 40 or has_high_value_category:
            actions.append("ffuf_api_fuzz")
        
        # Check for specific endpoints (only if high-risk)
        for ep in endpoint_nodes:
            props = ep.get("properties", {})
            path = props.get("path", "")
            category = props.get("category", "").upper()
            risk = props.get("risk_score", 0)
            
            # Only suggest auth scan for actual ADMIN/AUTH endpoints with risk
            if (category in ("ADMIN", "AUTH") or "/admin" in path or "/login" in path) and risk >= 30:
                actions.append("nuclei_auth_scan")
            if "/graphql" in path:
                actions.append("graphql_introspection")
    
    # DNS Specific
    for node in dns_nodes:
        rtype = node.get("properties", {}).get("type", "")
        if rtype == "MX":
            actions.append("smtp_test")
            break
             
    if not actions: 
        actions.append("manual_review")
    
    if vuln_nodes:
        actions.append("manual_validation")
        # Only suggest exploit lab for High/Critical or Confirmed
        has_exploitable = any(v.get("properties", {}).get("severity") in ["CRITICAL", "HIGH"] or v.get("properties", {}).get("confirmed") for v in vuln_nodes)
        if has_exploitable:
            actions.append("exploit_lab")
              
    return list(set(actions))


def iter_osint_chains(graph_data: Dict) -> Generator[Tuple[Dict, List[Dict], List[Dict], List[Dict]], None, None]:
    """
    Iterate over OSINT paths: ORG -> SAAS / LEAK / BRAND.
    Yields (org_node, saas_nodes, leak_nodes, brand_nodes).
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    
    org_to_saas = {}
    org_to_leaks = {}
    org_to_brands = {}
    
    node_index = {n["id"]: n for n in nodes}
    
    for edge in edges:
        src = edge["from"]
        dst = edge["to"]
        rel = edge.get("type") or edge.get("relation", "")  # Support both field names
        
        if rel == "ORG_USES_SAAS":
            org_to_saas.setdefault(src, []).append(dst)
        elif rel == "LEAK_RELATES_TO_ORG":
            # Edge is LEAK -> ORG usually, based on asset_graph.py: link_leak_org(leak, org)
            # So src=leak, dst=org
            org_to_leaks.setdefault(dst, []).append(src) 
        elif rel == "ORG_OWNS_BRAND":
            org_to_brands.setdefault(src, []).append(dst)
            
    for node in nodes:
        if node["type"] != "ORG":
            continue
        
        org_id = node["id"]
        
        saas_list = [node_index[x] for x in org_to_saas.get(org_id, []) if x in node_index]
        leak_list = [node_index[x] for x in org_to_leaks.get(org_id, []) if x in node_index]
        brand_list = [node_index[x] for x in org_to_brands.get(org_id, []) if x in node_index]
        
        yield (node, saas_list, leak_list, brand_list)

def score_osint_chain(org_node: Dict, saas_nodes: List[Dict], leak_nodes: List[Dict]) -> Tuple[int, List[str], List[str]]:
    """Return score, reasons, and actions."""
    score = 0
    reasons = []
    actions = []
    
    # SaaS Scoring
    for saas in saas_nodes:
        name = saas.get("properties", {}).get("name", "Unknown")
        cat = saas.get("properties", {}).get("category", "")
        
        score += 2
        reasons.append(f"SaaS: {name} ({cat})")
        
        if "mail" in cat.lower() or "crm" in cat.lower():
            score += 3
            actions.append("phishing_scenario_design")
    
    # Leak Scoring
    for leak in leak_nodes:
        ltype = leak.get("properties", {}).get("type", "")
        desc = leak.get("properties", {}).get("description", "")
        
        score += 5
        reasons.append(f"Leak: {ltype}")
        actions.append("credential_stuffing_simulation")
        actions.append("manual_review")
        
    if not actions and score > 0:
        actions.append("manual_context_review")
        
    return score, reasons, list(set(actions))

def find_top_paths(graph_data: Dict, memory_context: Dict = None, k: int = 5) -> List[Dict]:
    best_paths: Dict[str, Dict] = {}
    memory_context = memory_context or {"keywords": [], "targets": []}
    past_targets = memory_context.get("targets", [])
    
    # 1. Technical Paths (Subdomain/HTTP)
    for sub, http, js, infra, dns, eps, vulns in iter_paths_sub_http_js(graph_data):
        sub_id = sub.get("id", "")
        mem_boost = 3 if sub_id in past_targets else 0
        
        current_score, reasons = score_path(sub, http, js, infra, dns, eps, vulns, memory_boost=mem_boost)
        
        path_info = {
            "score": current_score,
            "subdomain": sub_id,
            "url": http.get("properties", {}).get("url"),
            "reason": " | ".join(reasons),
            "next_actions": suggest_actions(sub, http, js, dns, eps, vulns)
        }
        
        if sub_id not in best_paths or current_score > best_paths[sub_id]["score"]:
            best_paths[sub_id] = path_info

    # 2. OSINT Paths (Org/SaaS/Leaks)
    for org, saas_list, leak_list, brand_list in iter_osint_chains(graph_data):
        score, reasons, actions = score_osint_chain(org, saas_list, leak_list)
        if score > 0:
            # We treat the Organization as the "subdomain" (target entity) for reporting purposes
            target_id = org.get("id")
            
            path_info = {
                "score": score,
                "subdomain": target_id, # Re-using field for compatibility
                "url": None,
                "reason": "OSINT | " + " | ".join(reasons),
                "next_actions": actions
            }
             # Append or Merge? If org has same ID as subdomain (unlikely), take max.
            if target_id not in best_paths or score > best_paths[target_id]["score"]:
                best_paths[target_id] = path_info
            
    scored_paths = list(best_paths.values())
    scored_paths.sort(key=lambda x: x["score"], reverse=True)
    return scored_paths[:k]


def find_top_offensive_endpoints(graph_data: Dict, limit: int = 10) -> List[Dict]:
    """
    Phase 23: Find top offensive endpoints for targeted scanning.
    Returns a list of endpoint targets sorted by risk_score.
    
    Each result contains:
    - endpoint_id
    - url (origin)
    - path
    - category
    - risk_score
    - likelihood_score
    - impact_score
    - behavior_hint
    - suggested_tools: List of tools to run (Nuclei, Ffuf, etc.)
    """
    nodes = graph_data.get("nodes", [])
    
    # Filter for ENDPOINT nodes with Phase 23 metadata
    endpoint_targets = []
    
    for node in nodes:
        if node["type"] != "ENDPOINT":
            continue
        
        props = node.get("properties", {})
        risk_score = props.get("risk_score", 0)
        
        # Build target info
        target = {
            "endpoint_id": node["id"],
            "url": props.get("origin", ""),
            "path": props.get("path", ""),
            "method": props.get("method", "GET"),
            "category": props.get("category", "UNKNOWN"),
            "risk_score": risk_score,
            "likelihood_score": props.get("likelihood_score", 0),
            "impact_score": props.get("impact_score", 0),
            "behavior_hint": props.get("behavior_hint", "UNKNOWN"),
            "auth_required": props.get("auth_required", False),
            "suggested_tools": [],
        }
        
        # Suggest tools based on endpoint characteristics
        category = target["category"]
        behavior = target["behavior_hint"]
        
        if category in ("ADMIN", "AUTH"):
            target["suggested_tools"].append("nuclei_auth_scan")
            target["suggested_tools"].append("ffuf_dir_fuzz")
        elif category == "API":
            target["suggested_tools"].append("nuclei_api_scan")
            target["suggested_tools"].append("ffuf_api_fuzz")
        elif category == "LEGACY":
            target["suggested_tools"].append("nuclei_legacy_scan")
        
        if behavior == "ID_BASED_ACCESS":
            target["suggested_tools"].append("idor_test")
        if behavior == "STATE_CHANGING":
            target["suggested_tools"].append("csrf_test")
        
        # Default scan if no specific tools
        if not target["suggested_tools"]:
            target["suggested_tools"].append("nuclei_general")
        
        endpoint_targets.append(target)
    
    # Sort by risk_score descending
    endpoint_targets.sort(key=lambda x: (x["risk_score"], x["likelihood_score"]), reverse=True)
    
    return endpoint_targets[:limit]


