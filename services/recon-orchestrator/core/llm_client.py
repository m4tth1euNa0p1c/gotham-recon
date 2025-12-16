"""
LLM Client Abstraction
Unified interface for Ollama and OpenAI providers
Includes CrewAI native LLM integration
"""
import os
import requests
from typing import Optional

# CrewAI native LLM import
try:
    from crewai import LLM as CrewAILLM
    CREWAI_LLM_AVAILABLE = True
except ImportError:
    CrewAILLM = None
    CREWAI_LLM_AVAILABLE = False


def get_crewai_llm():
    """
    Get a CrewAI-native LLM for agents.
    Uses CrewAI's built-in LLM class with Ollama's OpenAI-compatible endpoint.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model = os.getenv("MODEL_NAME", "qwen2.5:14b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

    if not CREWAI_LLM_AVAILABLE:
        raise ImportError("CrewAI LLM class not available")

    if provider == "ollama":
        # Use CrewAI's native LLM class with Ollama's OpenAI-compatible endpoint
        # CRITICAL: Must use /v1 suffix for OpenAI-compatible endpoint
        ollama_v1_url = f"{base_url}/v1"
        print(f"[LLM] Using CrewAI native LLM with model={model} base_url={ollama_v1_url}")
        return CrewAILLM(
            model=model,
            base_url=ollama_v1_url,
            api_key="not-needed",  # Ollama doesn't need API key
            temperature=0.7,
        )
    else:
        # OpenAI or compatible
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI provider")
        print(f"[LLM] Using CrewAI native LLM with OpenAI model={model}")
        return CrewAILLM(
            model=model,
            base_url=api_base,
            api_key=api_key,
            temperature=0.7,
        )


class LLMClient:
    """Unified LLM client supporting Ollama and OpenAI"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.model_name = os.getenv("MODEL_NAME", "qwen2.5:14b")
        self.coder_model_name = os.getenv("OLLAMA_CODER_MODEL", "qwen2.5-coder:7b")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.timeout = int(os.getenv("LLM_TIMEOUT", "300"))

    def is_available(self) -> bool:
        """Check if LLM service is available"""
        try:
            if self.provider == "ollama":
                resp = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
                return resp.status_code == 200
            elif self.provider == "openai":
                return bool(self.openai_api_key)
            return False
        except Exception:
            return False

    def chat(self, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> str:
        """
        Send a chat completion request to the LLM

        Args:
            system_prompt: System context/instructions
            user_prompt: User message/query
            model: Optional model override

        Returns:
            LLM response text
        """
        if self.provider == "ollama":
            return self._chat_ollama(system_prompt, user_prompt, model)
        elif self.provider == "openai":
            return self._chat_openai(system_prompt, user_prompt, model)
        else:
            raise RuntimeError(f"Unsupported LLM_PROVIDER: {self.provider}")

    def _chat_ollama(self, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> str:
        """Send request to Ollama API"""
        model = model or self.model_name
        prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"

        resp = requests.post(
            f"{self.ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 4096,
                }
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    def chat_coder(self, prompt: str) -> str:
        """
        Send a coding-specific request using the coder model

        Args:
            prompt: The coding task/question

        Returns:
            Code/response from the coder model
        """
        if self.provider == "ollama":
            resp = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.coder_model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temp for code
                        "num_predict": 4096,
                    }
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        else:
            # Fallback to main chat for non-ollama
            return self.chat(
                "You are an expert Python developer. Write clean, secure code.",
                prompt
            )

    def _chat_openai(self, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> str:
        """Send request to OpenAI-compatible API"""
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        model = model or self.model_name

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
        }

        resp = requests.post(
            f"{self.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def analyze_endpoint(self, endpoint_data: dict) -> dict:
        """
        Use LLM to analyze an endpoint and enrich with intelligence

        Args:
            endpoint_data: Endpoint information dict

        Returns:
            Enriched endpoint data with LLM analysis
        """
        system_prompt = """You are a senior security analyst specializing in web application security.
Analyze the given endpoint and provide:
1. Risk assessment (likelihood 0-10, impact 0-10)
2. Category classification (API, ADMIN, AUTH, PUBLIC, STATIC, LEGACY)
3. Potential attack hypotheses (max 3)
4. Technology stack hints if detectable

Return ONLY valid JSON, no explanations."""

        user_prompt = f"""Analyze this endpoint:
{endpoint_data}

Return JSON with structure:
{{
    "category": "string",
    "likelihood_score": int,
    "impact_score": int,
    "risk_score": int,
    "auth_required": bool,
    "tech_stack_hint": "string or null",
    "hypotheses": [
        {{"title": "string", "attack_type": "string", "confidence": float, "priority": int}}
    ]
}}"""

        try:
            response = self.chat(system_prompt, user_prompt)
            import json
            # Try to extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception as e:
            print(f"[LLM] Analysis failed: {e}")

        return {}

    def generate_attack_plan(self, graph_summary: dict) -> list:
        """
        Generate attack plan based on asset graph

        Args:
            graph_summary: Summary of discovered assets

        Returns:
            List of prioritized attack paths
        """
        system_prompt = """You are an offensive security strategist.
Based on the reconnaissance data, identify the most promising attack vectors.
Prioritize by: ease of exploitation, potential impact, and evidence of weakness.

Return ONLY valid JSON array, no explanations."""

        user_prompt = f"""Asset Graph Summary:
{graph_summary}

Return JSON array of attack paths:
[
    {{
        "target": "subdomain or endpoint",
        "score": int (0-100),
        "actions": ["list of attack techniques"],
        "reasons": ["why this is high value"]
    }}
]"""

        try:
            response = self.chat(system_prompt, user_prompt)
            import json
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception as e:
            print(f"[LLM] Attack plan generation failed: {e}")

        return []


# Singleton instance
_llm_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """Get singleton LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
