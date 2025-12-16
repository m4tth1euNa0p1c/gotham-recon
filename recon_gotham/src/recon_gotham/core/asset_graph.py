
import json
import os
from typing import List, Dict

class AssetGraph:
    """
    In-memory graph structure to store reconnaissance assets and relationships.
    Refactored V2: Consolidated addition methods and preparation for JS/Secrets.
    """
    
    VALID_NODE_TYPES = {
        "SUBDOMAIN", "HTTP_SERVICE", "JS_FILE", "ENDPOINT", "SECRET", 
        "IP_ADDRESS", "ASN", "DNS_RECORD", "VULNERABILITY", "PARAMETER",
        # Phase 15 Extensions
        "ORG", "BRAND", "SAAS_APP", "REPOSITORY", "LEAK", "HYPOTHESIS",
        # Phase 23 V2.2 Extensions
        "ATTACK_PATH"
    }
    
    # Phase 23 V2.2 Constants
    ENDPOINT_CATEGORIES = {
        "API", "ADMIN", "AUTH", "PUBLIC", "STATIC", "LEGACY", "HEALTHCHECK", "UNKNOWN"
    }
    
    BEHAVIOR_HINTS = {
        "READ_ONLY", "STATE_CHANGING", "ID_BASED_ACCESS", "OTHER", "UNKNOWN"
    }
    
    ATTACK_TYPES = {
        "XXE", "SQLI", "XSS", "IDOR", "BOLA", "AUTH_BYPASS", "RATE_LIMIT", 
        "RCE", "SSRF", "LFI", "RFI", "CSRF", "OPEN_REDIRECT", "INFO_DISCLOSURE"
    }
    
    PARAM_LOCATIONS = {"query", "path", "body", "header", "cookie", "unknown"}
    PARAM_SENSITIVITIES = {"LOW", "MEDIUM", "HIGH"}
    
    def __init__(self, target_domain: str = None):
        self.target_domain = target_domain  # Store for scope checks
        self.nodes = []
        self.edges = []
        # Sets to track uniqueness
        self._seen_nodes = set()
        self._seen_edges = set()

    def _is_generic_example(self, text: str, target_root: str = None) -> bool:
        """
        Check if the text is a generic example or unrelated to the target.
        """
        if not text: return True
        text_lower = text.lower()
        
        # 1. Block obvious hallucinations/examples
        FORBIDDEN = ["target corporation", "target corp", "acme corp", "example.com", "mycompany", "test org"]
        if any(bad in text_lower for bad in FORBIDDEN):
            return True
            
        # 2. If target_root provided, ensure strict relevance
        if target_root:
            # Check if target_root (e.g. "tahiti-infos") is in the text
            # Extract root name
            root_name = target_root.split('.')[0] # "tahiti-infos" from "tahiti-infos.com"
            if len(root_name) > 3 and root_name not in text_lower:
                 # Special case: The org might be the PARENT company (e.g. "Fenyx" for "tahiti-infos")
                 # But usually prompt asks for related orgs. 
                 # We can be lenient or strict. User asked for strict scope.
                 # Let's return True (Is Generic/Unrelated) if valid root name is missing
                 return True
                 
        return False

        return False

    def _add_node(self, node_id, node_type, properties):
        """Internal helper to add a node safely."""
        if node_id in self._seen_nodes:
            return # Avoid duplicates
        
        self.nodes.append({
            "id": node_id,
            "type": node_type,
            "properties": properties
        })
        self._seen_nodes.add(node_id)
        self._seen_nodes.add(node_id)
        return node_id

    def ensure_subdomain(self, name: str, priority: int = 5, tag: str = "PASSIVE_DISCOVERY", category: str = "RECON", reason: str = None) -> str:
        """
        Normalize and ensure a SUBDOMAIN node exists.
        Returns the node_id, or None if out of scope.
        """
        if not name: return None
        
        # Normalization
        clean = name.strip().lower()
        if clean.startswith("http://"): clean = clean.split("://", 1)[1]
        if clean.startswith("https://"): clean = clean.split("://", 1)[1]
        # Strip port if present
        if ":" in clean:
            clean = clean.split(":")[0]
        if clean.endswith("/"): clean = clean.rstrip("/")
        # Strip path if present
        if "/" in clean:
            clean = clean.split("/")[0]
        
        # SCOPE CHECK: Reject if not matching target_domain
        if self.target_domain:
            if not (clean.endswith(self.target_domain) or clean == self.target_domain):
                # Out of scope, reject silently
                return None
        
        node_id = clean
        
        # Check if exists as SUBDOMAIN
        existing = next((n for n in self.nodes if n["id"] == node_id and n["type"] == "SUBDOMAIN"), None)
        if existing:
            return node_id
            
        # Create
        self._add_node(
            node_id=node_id,
            node_type="SUBDOMAIN",
            properties={
                "name": clean,
                "priority": priority,
                "tag": tag,
                "category": category,
                "reason": reason
            }
        )
        return node_id

    def ensure_subdomain_for_url(self, url: str, source: str = "INFERRED") -> str:
        """
        V2.3: Ensure a SUBDOMAIN node exists for any URL.
        Parses the hostname and creates the node if missing.
        Returns the subdomain node_id or None if out of scope.
        """
        if not url:
            return None
        
        from urllib.parse import urlparse
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.hostname or ""
        
        if not host:
            return None
        
        return self.ensure_subdomain(
            name=host,
            priority=5,
            tag=source,
            category="INFERRED_HTTP",
        )

    def ensure_http_service_for_endpoint(self, endpoint_url: str, source: str = "INFERRED") -> str:
        """
        V2.3: Ensure both SUBDOMAIN and HTTP_SERVICE exist for an endpoint URL.
        Creates the chain: SUBDOMAIN -> HTTP_SERVICE if missing.
        Returns the HTTP_SERVICE node_id or None if out of scope.
        """
        if not endpoint_url:
            return None
        
        from urllib.parse import urlparse
        parsed = urlparse(endpoint_url if "://" in endpoint_url else f"https://{endpoint_url}")
        host = parsed.hostname or ""
        scheme = parsed.scheme or "https"
        port = parsed.port
        
        if not host:
            return None
        
        # 1. Ensure SUBDOMAIN exists
        sub_id = self.ensure_subdomain_for_url(endpoint_url, source)
        if not sub_id:
            return None  # Out of scope
        
        # 2. Build HTTP_SERVICE URL (base URL without path)
        if port and port not in (80, 443):
            base_url = f"{scheme}://{host}:{port}"
        else:
            base_url = f"{scheme}://{host}"
        
        service_id = f"http:{base_url}"
        
        # 3. Create HTTP_SERVICE if missing
        if service_id not in self._seen_nodes:
            self._add_node(
                node_id=service_id,
                node_type="HTTP_SERVICE",
                properties={
                    "url": base_url,
                    "source": source,
                }
            )
            # Link SUBDOMAIN -> HTTP_SERVICE
            self._add_edge(sub_id, service_id, "EXPOSES_HTTP")
        
        return service_id

    def _add_edge(self, source, target, relation):
        """Internal helper to add an edge safely."""
        edge_id = f"{source}-{relation}-{target}"
        if edge_id in self._seen_edges:
            return 
        
        self.edges.append({
            "from": source,
            "to": target,
            "relation": relation
        })
        self._seen_edges.add(edge_id)

    def add_subdomain_with_http(self, item: dict):
        """
        Consolidated method to add a Subdomain and its optional HTTP service.
        Expects a dict formatted by the Tech Fingerprinter.
        """
        sub_name = item.get("subdomain")
        if not sub_name:
            return

        # 1. Add Subdomain Node
        if not sub_name:
            return

        # 1. Normalize Subdomain Node
        sub_name = self.ensure_subdomain(
            name=sub_name,
            priority=item.get("priority", 5),
            tag=item.get("tag", "TECH_FINGERPRINT"),
            category=item.get("category", "ACTIVE_RECON"),
            reason=item.get("reason")
        )

        # 2. Add HTTP Service Node (if present)
        http_info = item.get("http")
        if http_info and http_info.get("url"):
            service_id = f"http:{http_info.get('url')}"
            
            self._add_node(
                node_id=service_id,
                node_type="HTTP_SERVICE",
                properties={
                    "url": http_info.get("url"),
                    "status_code": http_info.get("status_code"),
                    "technologies": http_info.get("technologies", []),
                    "ip": http_info.get("ip"),
                    "title": http_info.get("title")
                }
            )
            
            # 3. Link them
            self._add_edge(sub_name, service_id, "EXPOSES_HTTP")

    def add_js_analysis(self, js_data: dict, parent_url: str):
        """
        Phase 3: Add JS Files, Endpoints, and Secrets found on a page.
        """
        if not js_data:
            return

        # 1. Recover / Create HTTP_SERVICE parent node
        http_node_id = f"http:{parent_url}"
        
        if http_node_id not in self._seen_nodes:
            self._add_node(
                node_id=http_node_id,
                node_type="HTTP_SERVICE",
                properties={"url": parent_url}
            )

        # 2. JS_FILES
        js_files = js_data.get("js_files", [])
        for js_url in js_files:
            js_id = f"js:{js_url}"
            self._add_node(
                node_id=js_id,
                node_type="JS_FILE",
                properties={"url": js_url}
            )
            self._add_edge(http_node_id, js_id, "LOADS_JS")

        # 3. ENDPOINTS
        endpoints = js_data.get("endpoints", [])
        for ep in endpoints:
            path = ep.get("path")
            if not path: continue
            
            endpoint_id = f"endpoint:{parent_url}{path}"
            
            self._add_node(
                node_id=endpoint_id,
                node_type="ENDPOINT",
                properties={
                    "path": path,
                    "method": ep.get("method"),
                    "source_js": ep.get("source_js")
                }
            )
            self._add_edge(http_node_id, endpoint_id, "EXPOSES_ENDPOINT")

        # 4. SECRETS
        secrets = js_data.get("secrets", [])
        for sec in secrets:
            value = sec.get("value")
            if not value: continue
            
            secret_id = f"secret:{hash(value)}"
            
            self._add_node(
                node_id=secret_id,
                node_type="SECRET",
                properties={
                    "kind": sec.get("kind"),
                    "source_js": sec.get("source_js")
                }
            )
            self._add_edge(http_node_id, secret_id, "LEAKS_SECRET")

    def add_dns_resolution(self, subdomain: str, ips: List[str], dns_records: Dict):
        """Adds IP nodes and links them to the subdomain."""
        if not subdomain: return
        
        # Ensure Subdomain Node exists
        if not subdomain: return
        
        # Ensure Subdomain Node exists (Normalized)
        sub_id = self.ensure_subdomain(subdomain, priority=6, tag="DNS_DISCOVERED", category="PASSIVE_DNS")
        if not sub_id: return
        
        # Add IPs
        for ip in ips:
            ip_node_id = f"ip:{ip}"
            self._add_node(
                node_id=ip_node_id,
                node_type="IP_ADDRESS",
                properties={"ip": ip}
            )
            self._add_edge(subdomain, ip_node_id, "RESOLVES_TO")

        # Add other records as DNS_RECORD nodes
        for rtype, values in dns_records.items():
            if rtype in ["A", "AAAA"]: continue
            for val in values:
                rec_id = f"dns:{rtype}:{val}"
                self._add_node(
                    node_id=rec_id,
                    node_type="DNS_RECORD",
                    properties={"type": rtype, "value": val}
                )
                self._add_edge(subdomain, rec_id, "HAS_RECORD")

    def add_asn_info(self, ip: str, asn_info: Dict):
        """Adds ASN node and links it to the IP."""
        if not ip: return
        
        asn_code = asn_info.get("asn", "UNKNOWN")
        org_name = asn_info.get("name", "UNKNOWN")
        desc = asn_info.get("description", "")
        
        asn_node_id = f"asn:{asn_code}"
        self._add_node(
            node_id=asn_node_id,
            node_type="ASN",
            properties={
                "asn": asn_code,
                "org": org_name,
                "description": desc,
                "country": asn_info.get("country_code")
            }
        )
        ip_node_id = f"ip:{ip}"
        self._add_edge(ip_node_id, asn_node_id, "BELONGS_TO")

    def _normalize_path(self, path: str) -> str:
        """
        Normalize endpoint path:
        1. Strip embedded full URLs (from Wayback like /http://...).
        2. Strip query parameters.
        3. Ensure leading slash.
        4. Remove trailing slash (unless root).
        """
        if not path: return ""
        
        # 0. Strip embedded protocol URLs (Wayback artifacts)
        # Pattern: /http://... or /https://... at the start
        if path.startswith("/http://") or path.startswith("/https://"):
            # Extract just the path part from the embedded URL
            from urllib.parse import urlparse
            embedded_url = path[1:]  # Remove leading /
            parsed = urlparse(embedded_url)
            path = parsed.path or "/"
            # If there's still a nested URL, try again
            if path.startswith("/http://") or path.startswith("/https://"):
                return ""  # Malformed, skip
        
        # Strip Wayback Machine .external redirects (e.g., /.external/http/www.other.com/...)
        # These are NOT real endpoints, they are Wayback's redirect tracking
        if "/.external/" in path:
            return ""  # Reject Wayback redirect artifacts entirely
        
        # Also handle paths that ARE full URLs (shouldn't happen but safety)
        if path.startswith("http://") or path.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(path)
            path = parsed.path or "/"
        
        # 1. Strip Query
        if "?" in path:
            path = path.split("?")[0]
        if "#" in path:
            path = path.split("#")[0]
            
        # 2. Leading Slash
        if not path.startswith("/"):
            path = f"/{path}"
            
        # 3. Trailing Slash
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
            
        return path

    def add_endpoint(self, path: str, method: str, source: str, origin: str, confidence: float = 0.5):
        """
        Generic method to add an ENDPOINT node.
        Includes scope check to reject external domains.
        """
        # SCOPE CHECK: If origin contains an external domain, reject
        if origin and self.target_domain:
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            host = parsed.netloc.lower()
            # Strip port
            if ":" in host:
                host = host.split(":")[0]
            if host and not (host.endswith(self.target_domain) or host == self.target_domain):
                # External domain, reject
                return
        
        path = self._normalize_path(path)
        if not path or len(path) < 2: # Ignore root /
            return

        # Deduce Method
        method = method.upper() if method else "UNKNOWN"
        
        # Determine Host/Parent - V2.3: Use ensure helper for full chain
        parent_service_id = None
        
        if origin and origin.startswith("http"):
            # V2.3: Ensure full chain SUBDOMAIN -> HTTP_SERVICE exists
            parent_service_id = self.ensure_http_service_for_endpoint(origin, source)

        endpoint_id = f"endpoint:{parent_service_id or 'unknown'}{path}"
        
        # Add Node
        self._add_node(
            node_id=endpoint_id,
            node_type="ENDPOINT",
            properties={
                "path": path,
                "method": method,
                "source": source,
                "origin": origin,
                "confidence": confidence
            }
        )
        
        # Link to Parent Service
        if parent_service_id:
            self._add_edge(parent_service_id, endpoint_id, "EXPOSES_ENDPOINT")
        if source == "JS" and origin.endswith(".js"):
            # origin might be full url
            js_node_id = f"js:{origin}"
            # Check if exists? Or strict link?
            # Let's rely on standard ID convention.
            # Only add edge if we assume the JS node was created by JsMiner
            # But add_endpoint might be called before JS node creation? 
            # Safe to add edge, graph allows "dangling" edges logic usually but here we strictly check nodes?
            # self.edges stores strings. It's fine.
            self._add_edge(js_node_id, endpoint_id, "REFERS_ENDPOINT")
        elif source == "ROBOTS":
            # No specific ROBOTS node usually, just link to service or generic
            pass
            # Maybe link to a SNAPSHOT node in future?
            pass

        return endpoint_id

    def update_endpoint_metadata(
        self,
        endpoint_id: str,
        category: str = None,
        likelihood_score: int = None,
        impact_score: int = None,
        risk_score: int = None,
        auth_required: bool = None,
        tech_stack_hint: str = None,
        behavior_hint: str = None,
        id_based_access: bool = None,
    ) -> bool:
        """
        Phase 23: Update an existing ENDPOINT node with risk metadata.
        Returns True if node was found and updated, False otherwise.
        """
        # Find the node
        node = next((n for n in self.nodes if n["id"] == endpoint_id and n["type"] == "ENDPOINT"), None)
        if not node:
            return False
        
        props = node["properties"]
        
        # Update category (validated)
        if category is not None:
            if category.upper() in self.ENDPOINT_CATEGORIES:
                props["category"] = category.upper()
        
        # Update scores (clamped)
        if likelihood_score is not None:
            props["likelihood_score"] = max(0, min(10, int(likelihood_score)))
        if impact_score is not None:
            props["impact_score"] = max(0, min(10, int(impact_score)))
        if risk_score is not None:
            props["risk_score"] = max(0, min(100, int(risk_score)))
        
        # Update boolean/string fields
        if auth_required is not None:
            # Preserve string values like "UNKNOWN", "true", "false"
            if isinstance(auth_required, str):
                props["auth_required"] = auth_required
            else:
                props["auth_required"] = bool(auth_required)
        if tech_stack_hint is not None:
            props["tech_stack_hint"] = str(tech_stack_hint)
        if behavior_hint is not None:
            if behavior_hint.upper() in self.BEHAVIOR_HINTS:
                props["behavior_hint"] = behavior_hint.upper()
        if id_based_access is not None:
            props["id_based_access"] = bool(id_based_access)
        
        return True

    def add_vulnerability(self, name: str, severity: str, tool: str, affected_node_id: str, description: str = "", evidence: str = "", confirmed: bool = False, confidence: float = 0.5):
        """
        Add a VULNERABILITY node and link it to the affected asset.
        """
        severity = severity.upper()
        vuln_id = f"vuln:{tool}:{name}:{affected_node_id}" # Simple dedup
        
        self._add_node(
            node_id=vuln_id,
            node_type="VULNERABILITY",
            properties={
                "name": name,
                "severity": severity,
                "tool": tool,
                "description": description,
                "description": description,
                "evidence": evidence,
                "confirmed": confirmed,
                "confidence": confidence
            }
        )
        
        # Link to affected node
        if affected_node_id in self._seen_nodes:
            edge_name = "AFFECTS"
            if "endpoint:" in affected_node_id: edge_name = "AFFECTS_ENDPOINT"
            elif "http:" in affected_node_id: edge_name = "AFFECTS_HTTP_SERVICE"
            elif "ip:" in affected_node_id: edge_name = "AFFECTS_IP"
            elif "js:" in affected_node_id: edge_name = "AFFECTS_FILE"
            elif "." in affected_node_id and " " not in affected_node_id: edge_name = "AFFECTS_SUBDOMAIN" # Heuristic
            
            self._add_edge(vuln_id, affected_node_id, edge_name)

    def add_parameter(self, url: str, param: str, method: str = "GET", risk: str = "INFO"):
        """
        Add a PARAMETER node linked to an ENDPOINT or HTTP_SERVICE.
        """
        # Node ID: "param:URL:PARAM_NAME"
        param_id = f"param:{url}:{param}"
        
        self._add_node(
            node_id=param_id,
            node_type="PARAMETER",
            properties={
                "name": param,
                "method": method,
                "risk": risk.upper()
            }
        )
        
        # Link to Origin
        # Try to match to an ENDPOINT or HTTP_SERVICE
        # Heuristic: Find node with ID == endpoint:url or just link to generic ID if we don't have perfect alignment
        # Logic: If 'url' is an endpoint ID, use it. If it's a raw URL, try to guess the ID.
        
        # Simplified: Assume 'url' might be the endpoint ID or we look for it.
        # But 'param_discovery_task' outputs "url". 
        # Typically we link to "endpoint:http:..." or "http:..."
        
        # Try finding the node
        origin_id = None
        if url in self._seen_nodes: 
            origin_id = url
        else:
             # Try reconstructing Endpoint ID logic or search
             # Or just trust the user provided a URL that matches an endpoint "origin" property? 
             # No, AssetGraph uses IDs. 
             # Let's assume the caller passes the proper Link ID or we can't link effectively.
             # However, given the complexity, we might just search for a node where properties.url == url or properties.path match.
             # For now, we will add the node. Linking requires exact ID. 
             # We can iterate nodes? No too slow.
             pass
             
        # Just creating the node for now is enough for the Graph context.
        # If we can link it, great.
        pass

    def add_parameter_v2(
        self,
        endpoint_id: str,
        name: str,
        location: str = "unknown",
        datatype_hint: str = "unknown",
        sensitivity: str = "LOW",
        is_critical: bool = False,
    ) -> str:
        """
        Phase 23: Add a PARAMETER node linked to an ENDPOINT with enhanced fields.
        Returns the parameter node ID.
        """
        # Validate location
        loc = location.lower() if location else "unknown"
        if loc not in self.PARAM_LOCATIONS:
            loc = "unknown"
        
        # Validate sensitivity
        sens = sensitivity.upper() if sensitivity else "LOW"
        if sens not in self.PARAM_SENSITIVITIES:
            sens = "LOW"
        
        # Node ID
        param_id = f"param:{endpoint_id}:{name}"
        
        # Check for dedup - update existing if found
        existing = next((n for n in self.nodes if n["id"] == param_id), None)
        if existing:
            # Update properties
            props = existing["properties"]
            props["location"] = loc
            props["datatype_hint"] = datatype_hint or "unknown"
            props["sensitivity"] = sens
            props["is_critical"] = bool(is_critical)
            return param_id
        
        # Create new node
        self._add_node(
            node_id=param_id,
            node_type="PARAMETER",
            properties={
                "name": name,
                "location": loc,
                "datatype_hint": datatype_hint or "unknown",
                "sensitivity": sens,
                "is_critical": bool(is_critical),
            }
        )
        
        # Link to endpoint
        if endpoint_id in self._seen_nodes:
            self._add_edge(endpoint_id, param_id, "HAS_PARAM")
        
        return param_id

    def add_endpoint_hypothesis(
        self,
        endpoint_id: str,
        title: str,
        attack_type: str,
        confidence: float = 0.5,
        priority: int = 3,
        path_id: str = None,
        chain_id: str = None,
    ) -> str:
        """
        Phase 23: Add a HYPOTHESIS node linked to a specific ENDPOINT.
        Returns the hypothesis node ID.
        """
        import hashlib
        
        # Validate attack_type
        atype = attack_type.upper() if attack_type else "UNKNOWN"
        if atype not in self.ATTACK_TYPES:
            atype = "UNKNOWN"
        
        # Clamp confidence and priority
        conf = max(0.0, min(1.0, float(confidence)))
        prio = max(1, min(5, int(priority)))
        
        # Generate ID
        h = hashlib.md5(f"{endpoint_id}:{title}:{atype}".encode()).hexdigest()[:8]
        hypo_id = f"hypo:{h}"
        
        # Create node
        self._add_node(
            node_id=hypo_id,
            node_type="HYPOTHESIS",
            properties={
                "title": title,
                "attack_type": atype,
                "confidence": conf,
                "priority": prio,
                "path_id": path_id,
                "chain_id": chain_id,
                "endpoint_id": endpoint_id,  # Reference back
            }
        )
        
        # Link to endpoint
        if endpoint_id in self._seen_nodes:
            self._add_edge(endpoint_id, hypo_id, "HAS_HYPOTHESIS")
        
        return hypo_id

    def add_org(self, name: str, country: str = None, sector: str = None, size_estimate: str = None, target_domain: str = None):
        """Add organization node with anti-pollution check."""
        # Anti-Hallucination Check
        if self._is_generic_example(name, target_domain):
            print(f"[-] Dropped Generic/Unrelated Org: {name}")
            return None

        node_id = f"org:{name.lower()}"
        properties = {
            "name": name,
            "country": country,
            "sector": sector,
            "size_estimate": size_estimate
        }
        return self._add_node(node_id, "ORG", properties)

    def add_brand(self, name: str, domain: str = None):
        """Add brand/subsidiary node."""
        node_id = f"brand:{name.lower()}"
        properties = {"name": name, "domain": domain}
        return self._add_node(node_id, "BRAND", properties)

    def add_saas_app(self, name: str, category: str = None, website: str = None, target_domain: str = None):
        """Add SaaS application node."""
        # Anti-Hallucination Check
        if self._is_generic_example(name, target_domain):
            # SaaS apps often don't contain target name (e.g. "Salesforce").
            # So we only check against FORBIDDEN generic names here, NOT target root match.
            if self._is_generic_example(name, target_root=None): # Only check forbidden list
                return None

        node_id = f"saas:{name.lower()}"
        properties = {"name": name, "category": category, "website": website}
        return self._add_node(node_id, "SAAS_APP", properties)

    def add_repository(self, url: str, platform: str = "github", visibility: str = "unknown", target_domain: str = None):
        """Add code repository node."""
        # Repos MUST contain the target name usually
        if self._is_generic_example(url, target_domain):
             print(f"[-] Dropped Generic/Unrelated Repo: {url}")
             return None

        node_id = f"repo:{url}"
        properties = {"url": url, "platform": platform, "visibility": visibility}
        return self._add_node(node_id, "REPOSITORY", properties)

    def add_leak(self, type: str, source: str, description: str, confidence: float = 0.5):
        """Add leak node."""
        import hashlib
        h = hashlib.md5(f"{type}{source}{description}".encode()).hexdigest()[:8]
        node_id = f"leak:{h}"
        properties = {
            "type": type,
            "source": source,
            "description": description,
            "confidence": confidence
        }
        return self._add_node(node_id, "LEAK", properties)

    def add_hypothesis(self, description: str, attack_family: str, confidence: float, support_ids: List[str]):
        """Add attack hypothesis node rooted in other assets."""
        import hashlib
        h = hashlib.md5(description.encode()).hexdigest()[:8]
        node_id = f"hypo:{h}"
        properties = {
            "description": description,
            "attack_family": attack_family,
            "confidence": confidence,
            "support": support_ids
        }
        nid = self._add_node(node_id, "HYPOTHESIS", properties)
        
        for sid in support_ids:
            if sid in self._seen_nodes:
                self._add_edge(node_id, sid, "HYPOTHESIS_BASED_ON")
        return nid

    # --- Edge Helpers ---
    def link_org_domain(self, org_id: str, domain_node_id: str):
        self._add_edge(org_id, domain_node_id, "ORG_OWNS_DOMAIN")

    def link_org_saas(self, org_id: str, saas_id: str):
        self._add_edge(org_id, saas_id, "ORG_USES_SAAS")

    def link_saas_endpoint(self, saas_id: str, endpoint_id: str):
        self._add_edge(saas_id, endpoint_id, "SAAS_APP_EXPOSES_ENDPOINT")

    def link_repo_result(self, repo_id: str, result_node_id: str):
        self._add_edge(repo_id, result_node_id, "REPO_CONTAINS_RESULT")
        
    def link_leak_org(self, leak_id: str, org_id: str):
        self._add_edge(leak_id, org_id, "LEAK_RELATES_TO_ORG")

    def add_attack_path(
        self,
        target_id: str,
        score: int,
        actions: List[str],
        reasons: List[str] = None,
        target_type: str = "SUBDOMAIN",
    ) -> str:
        """
        Phase 23 V2.2: Add an ATTACK_PATH node linked to a target.
        Materializes the Planner's offensive recommendations into the graph.
        
        Args:
            target_id: ID of the target node (SUBDOMAIN, HTTP_SERVICE, or ENDPOINT)
            score: Attack path score from planner
            actions: List of suggested actions (nuclei_scan, ffuf_api_fuzz, etc.)
            reasons: List of scoring reasons
            target_type: Type of target node
            
        Returns:
            Node ID of the created ATTACK_PATH node
        """
        import hashlib
        h = hashlib.md5(f"{target_id}{score}".encode()).hexdigest()[:8]
        node_id = f"attack_path:{h}"
        
        properties = {
            "target": target_id,
            "score": max(0, int(score)),
            "actions": actions if actions else [],
            "reasons": reasons if reasons else [],
            "target_type": target_type,
        }
        
        nid = self._add_node(node_id, "ATTACK_PATH", properties)
        
        # Link to target
        if target_id in self._seen_nodes:
            self._add_edge(node_id, target_id, "TARGETS")
        
        return nid


    def count_highvalue_nodes(self) -> int:
        """Count nodes that are considered high value for investigation loop."""
        high_value_types = {"ENDPOINT", "VULNERABILITY", "LEAK", "SAAS_APP", "HYPOTHESIS"}
        return sum(1 for n in self.nodes if n["type"] in high_value_types)

    def export_json(self, filepath):
        """Dump the graph to a JSON file with scope filtering."""
        
        # V2.3: Filter out-of-scope nodes before export
        def is_in_scope(node):
            node_id = node.get("id", "").lower()
            # Reject known generic/example domains
            if "example.com" in node_id or "example.org" in node_id:
                return False
            # If we have a target_domain, enforce scope for certain node types
            if self.target_domain:
                node_type = node.get("type", "")
                if node_type in ("SUBDOMAIN", "HTTP_SERVICE", "ENDPOINT"):
                    # Must contain target domain
                    return self.target_domain.lower() in node_id
            return True
        
        filtered_nodes = [n for n in self.nodes if is_in_scope(n)]
        
        # Also filter edges that reference out-of-scope nodes
        valid_node_ids = {n["id"] for n in filtered_nodes}
        filtered_edges = [
            e for e in self.edges 
            if e.get("from") in valid_node_ids and e.get("to") in valid_node_ids
        ]
        
        data = {
            "nodes": filtered_nodes,
            "edges": filtered_edges
        }
        
        dirname = os.path.dirname(filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return filepath

