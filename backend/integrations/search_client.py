"""
Bobby — Search Client (Dual: Supabase ITSM Knowledge / Azure AI Search)
=======================================================================
Switches based on APP_ENV:
  demo       → Supabase ITSM Knowledge Base (via REST API / relevance-ranked full-text search)
  production → Azure AI Search (hybrid vector + keyword)
"""
from __future__ import annotations
import httpx
import re
import structlog
from config.settings import settings

logger = structlog.get_logger(__name__)

STOPWORDS = {
    "the", "and", "for", "with", "how", "what", "can", "help", "please", "want",
    "need", "have", "issue", "my", "our", "you", "your", "does", "when", "why",
    "from", "into", "about", "are", "this", "that", "there", "here", "some"
}


class SupabaseSearchClient:
    """Retrieves grounded ITSM articles from Supabase PostgreSQL itsm_knowledge table with relevance scoring."""

    def __init__(self):
        self.url = settings.supabase_url.rstrip("/")
        self.key = settings.supabase_service_role_key

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        clean_query = query.strip()
        if not clean_query:
            return []

        raw_words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in clean_query.lower().split()]
        keywords = [w for w in raw_words if len(w) >= 3 and w not in STOPWORDS]

        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

        doc_dict: dict[str, dict] = {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. First priority: search by each significant keyword
            for kw in (keywords if keywords else raw_words[:2]):
                try:
                    url = (
                        f"{self.url}/rest/v1/itsm_knowledge"
                        f"?or=(title.ilike.*{kw}*,content.ilike.*{kw}*,category.ilike.*{kw}*)"
                        f"&select=id,title,content,category,tags,source&limit=10"
                    )
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        for row in resp.json():
                            doc_id = str(row.get("id", row.get("title")))
                            if doc_id not in doc_dict:
                                doc_dict[doc_id] = {
                                    "title": row.get("title", ""),
                                    "content": row.get("content", ""),
                                    "category": row.get("category", "general"),
                                    "source": row.get("source", "IPN IT Knowledge Base"),
                                    "score": 0.0,
                                }
                except Exception as ex:
                    logger.warning("supabase.search_kw_error", kw=kw, error=str(ex))

            # 2. If nothing found, retrieve top standard articles
            if not doc_dict:
                try:
                    resp = await client.get(
                        f"{self.url}/rest/v1/itsm_knowledge?select=id,title,content,category,source&limit=5",
                        headers=headers
                    )
                    if resp.status_code == 200:
                        for row in resp.json():
                            doc_id = str(row.get("id", row.get("title")))
                            doc_dict[doc_id] = {
                                "title": row.get("title", ""),
                                "content": row.get("content", ""),
                                "category": row.get("category", "general"),
                                "source": row.get("source", "IPN IT Knowledge Base"),
                                "score": 0.1,
                            }
                except Exception as ex:
                    logger.error("supabase.fallback_fetch_error", error=str(ex))

        # 3. Score and rank documents by match density
        for doc_id, doc in doc_dict.items():
            title_lower = doc["title"].lower()
            content_lower = doc["content"].lower()
            category_lower = doc["category"].lower()

            score = 0.0
            for kw in keywords:
                if kw in category_lower:
                    score += 5.0  # Category match is very strong signal
                if kw in title_lower:
                    score += 4.0  # Title match is strong signal
                if kw in content_lower:
                    score += 1.0  # Content match is baseline signal

            doc["score"] = score

        # Sort by score descending
        sorted_docs = sorted(doc_dict.values(), key=lambda d: d.get("score", 0.0), reverse=True)
        return sorted_docs[:top_k]


class AzureSearchClient:
    """Azure AI Search hybrid (vector + keyword) search."""

    def __init__(self):
        self.endpoint = settings.azure_search_endpoint
        self.api_key = settings.azure_search_api_key
        self.index = settings.azure_search_index_name

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        try:
            from integrations.llm_client import get_embedding_model
            embedding_model = get_embedding_model()
            embedding = await embedding_model.aembed_query(query)
        except Exception:
            embedding = []

        async with httpx.AsyncClient() as client:
            json_body = {
                "search": query,
                "queryType": "semantic",
                "top": top_k,
                "select": "title,content,source",
            }
            if embedding:
                json_body["vectorQueries"] = [{
                    "kind": "vector",
                    "vector": embedding,
                    "fields": "contentVector",
                    "k": top_k,
                }]

            response = await client.post(
                f"{self.endpoint}/indexes/{self.index}/docs/search?api-version=2024-05-01-preview",
                headers={
                    "api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=json_body,
                timeout=10.0,
            )
            if response.status_code != 200:
                logger.warning("azure_search.failed", status=response.status_code)
                return []
            data = response.json()
            return [
                {
                    "title": doc.get("title", ""),
                    "content": doc.get("content", ""),
                    "source": doc.get("source", ""),
                }
                for doc in data.get("value", [])
            ]


class InMemorySearchClient:
    """Fallback in-memory search for local dev without any external dependencies."""

    MOCK_DOCS = [
        {
            "title": "How to connect to VPN",
            "content": "To connect to the company VPN: 1. Open GlobalProtect app. 2. Enter your employee ID. 3. Authenticate with MFA. 4. Click Connect.",
            "source": "IT Knowledge Base",
        },
        {
            "title": "Password Reset Policy",
            "content": "Passwords must be at least 12 characters, include uppercase, lowercase, number and special character. Passwords expire every 90 days.",
            "source": "IT Policy",
        },
        {
            "title": "How to request new software",
            "content": "Submit a software request ticket via Bobby or the IT portal. Include the software name, business justification, and your manager approval.",
            "source": "IT Knowledge Base",
        },
    ]

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_lower = query.lower()
        results = [
            doc for doc in self.MOCK_DOCS
            if any(word in doc["content"].lower() for word in query_lower.split())
        ]
        return results[:top_k] if results else self.MOCK_DOCS[:2]


_search_instance = None


def get_search_client():
    global _search_instance
    if _search_instance is None:
        if settings.is_production and settings.azure_search_endpoint:
            _search_instance = AzureSearchClient()
        elif settings.supabase_url and settings.supabase_service_role_key:
            _search_instance = SupabaseSearchClient()
        else:
            logger.warning("search_client.using_in_memory_fallback")
            _search_instance = InMemorySearchClient()
    return _search_instance
