import os

def load_summary(domain: str, knowledge_dir: str = None) -> str | None:
    """
    Loads the content of a past mission summary for a given domain.
    """
    if not knowledge_dir:
        # Resolve 'knowledge' relative to this file's location in src/recon_gotham/core
        # Target: src/../knowledge = recon_gotham/knowledge
        # Actually 'knowledge' is usually at the root or under recon_gotham depending on structure.
        # Based on main.py: os.path.join(base_path, '..', '..', 'knowledge', ...)
        # base_path of main.py is src/recon_gotham
        # So knowledge is at root/knowledge or root/recon_gotham/knowledge?
        # main.py says: os.path.join(base_path, '..', '..', 'knowledge') -> Root/knowledge
        
        # This file is in src/recon_gotham/core
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Up to src/recon_gotham -> up to src -> up to root
        knowledge_dir = os.path.join(current_dir, '..', '..', '..', 'knowledge')
    
    filename = f"{domain}_summary.md"
    filepath = os.path.join(knowledge_dir, filename)
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None
    return None

def extract_high_value_context(summary_text: str) -> dict:
    """
    Parses summary text to find previously identified high-value targets or keywords.
    Returns a dict with 'keywords' found and potentially 'active_targets'.
    """
    context = {
        "keywords": [],
        "targets": []
    }
    
    if not summary_text:
        return context
        
    # Simple Keyword Heuristics
    # We look for sections or lines indicating high value
    high_value_keywords = [
        "AUTH_PORTAL", "BACKUP", "ADMIN", "API_ENDPOINT", "HIGH_VALUE", 
        "CRITICAL", "VULNERABLE", "EXPOSED"
    ]
    
    for kw in high_value_keywords:
        if kw in summary_text.upper():
            context["keywords"].append(kw)
            
    # Maybe extract subdomains listed in "Strategic Attack Plan"
    # They are usually formatted as "### N. subdomain.com"
    content_lines = summary_text.splitlines()
    in_plan = False
    
    for line in content_lines:
        if "Strategic Attack Plan" in line:
            in_plan = True
            continue
        
        if in_plan and line.strip().startswith("###"):
            # Extract subdomain from "### 1. subdomain.com"
            parts = line.split(" ", 2)
            if len(parts) > 2:
                target = parts[2].strip()
                context["targets"].append(target)
    
    return context
