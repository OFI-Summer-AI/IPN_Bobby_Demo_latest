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
from text_utils import normalize_query

logger = structlog.get_logger(__name__)

STOPWORDS = {
    "the", "and", "for", "with", "how", "what", "can", "help", "please", "want",
    "need", "have", "issue", "my", "our", "you", "your", "does", "when", "why",
    "from", "into", "about", "are", "this", "that", "there", "here", "some"
}

SEARCH_SYNONYMS = {
    "wifi": {"wireless", "wi-fi", "connectivity"},
    "wireless": {"wifi", "wi-fi", "connectivity"},
    "laptop": {"computer", "device", "windows"},
    "computer": {"laptop", "device", "windows"},
    "connect": {"connection", "connected", "connectivity"},
    "connection": {"connect", "connected", "connectivity"},
    "connected": {"connect", "connection", "connectivity"},
    "printer": {"printing", "print"},
    "email": {"mail", "outlook"},
    "mail": {"email", "outlook"},
    "login": {"logon", "sign-in", "signin"},
    "password": {"credentials", "login"},
}


def _search_terms(query: str, limit: int | None = None) -> list[str]:
    """Normalize a query and expand meaningful terms in stable order."""
    words = [
        re.sub(r"[^a-z0-9-]", "", word)
        for word in normalize_query(query).split()
    ]
    keywords = [word for word in words if len(word) >= 3 and word not in STOPWORDS]
    expanded = list(dict.fromkeys(
        term
        for word in keywords
        for term in (word, *sorted(SEARCH_SYNONYMS.get(word, set())))
    ))
    return expanded[:limit] if limit is not None else expanded


class SupabaseSearchClient:
    """Retrieves ITSM articles using vector RPC when available, then ranked lexical search."""

    def __init__(self):
        self.url = settings.supabase_url.rstrip("/")
        self.key = settings.supabase_service_role_key

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        clean_query = normalize_query(query)
        if not clean_query:
            return []

        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

        # Prefer the documented pgvector RPC. Existing deployments without the
        # function continue to use the lexical implementation below.
        try:
            from integrations.llm_client import get_embedding_model

            embedding_model = get_embedding_model()
            embedding = await embedding_model.aembed_query(clean_query)
            async with httpx.AsyncClient(timeout=10.0) as client:
                vector_response = await client.post(
                    f"{self.url}/rest/v1/rpc/match_documents",
                    headers=headers,
                    json={
                        "query_embedding": embedding,
                        "match_count": top_k,
                        "match_threshold": 0.7,
                    },
                )
            if vector_response.status_code == 200:
                vector_docs = [
                    {
                        "id": str(row.get("id", "")),
                        "title": row.get("title", ""),
                        "content": row.get("content", ""),
                        "category": row.get("category", "general"),
                        "source": row.get("source", "IPN IT Knowledge Base"),
                        "score": float(row.get("similarity", 0.0)),
                    }
                    for row in vector_response.json()
                    if float(row.get("similarity", 0.0)) >= 0.7
                ]
                if vector_docs:
                    logger.info(
                        "search.results",
                        provider="supabase_vector",
                        result_count=len(vector_docs[:top_k]),
                        top_score=vector_docs[0]["score"],
                    )
                    return vector_docs[:top_k]
            else:
                logger.info("supabase.vector_rpc_unavailable", status=vector_response.status_code)
        except Exception as ex:
            logger.info("supabase.vector_search_fallback", error=str(ex))

        doc_dict: dict[str, dict] = {}

        # Batch all keyword/tag conditions into one PostgREST request rather than
        # issuing a sequential network call for every synonym.
        search_terms = _search_terms(clean_query, limit=8)
        if not search_terms:
            return []
        conditions = ",".join(
            condition
            for term in search_terms
            for condition in (
                f"title.ilike.*{term}*",
                f"content.ilike.*{term}*",
                f"category.ilike.*{term}*",
                f"tags.cs.{{{term}}}",
            )
        )
        try:
            url = (
                f"{self.url}/rest/v1/itsm_knowledge?or=({conditions})"
                "&select=id,title,content,category,tags,source&limit=30"
            )
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                for row in resp.json():
                    doc_id = str(row.get("id", row.get("title")))
                    doc_dict[doc_id] = {
                        "id": doc_id,
                        "title": row.get("title", ""),
                        "content": row.get("content", ""),
                        "category": row.get("category", "general"),
                        "tags": row.get("tags", []),
                        "source": row.get("source", "IPN IT Knowledge Base"),
                        "score": 0.0,
                    }
            else:
                logger.warning("supabase.lexical_search_failed", status=resp.status_code)
        except Exception as ex:
            logger.warning("supabase.lexical_search_error", error=str(ex))

        # Score and rank documents. Results with no meaningful overlap are not
        # returned; callers can then ask for clarification or offer a ticket.
        for doc_id, doc in doc_dict.items():
            title_lower = doc["title"].lower()
            content_lower = doc["content"].lower()
            category_lower = doc["category"].lower()
            tags_lower = " ".join(doc.get("tags") or []).lower()

            score = 0.0
            for kw in search_terms:
                if kw in tags_lower:
                    score += 5.0  # Curated tags are the strongest retrieval signal
                if kw in category_lower:
                    score += 5.0  # Category match is very strong signal
                if kw in title_lower:
                    score += 4.0  # Title match is strong signal
                if kw in content_lower:
                    score += 1.0  # Content match is baseline signal

            maximum = max(len(search_terms) * 5.0, 1.0)
            doc["score"] = min(score / maximum, 1.0)

        # Sort by score descending
        sorted_docs = sorted(
            (doc for doc in doc_dict.values() if doc.get("score", 0.0) >= 0.2),
            key=lambda d: d.get("score", 0.0),
            reverse=True,
        )
        results = sorted_docs[:top_k]
        logger.info(
            "search.results",
            provider="supabase_lexical",
            result_count=len(results),
            top_score=results[0]["score"] if results else None,
        )
        return results


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
                "select": "id,title,content,source",
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
                logger.warning("azure_search.semantic_failed", status=response.status_code)
                # Preserve current Azure support when semantic ranking is not
                # configured on the index by retrying a standard keyword query.
                json_body["queryType"] = "simple"
                json_body.pop("vectorQueries", None)
                response = await client.post(
                    f"{self.endpoint}/indexes/{self.index}/docs/search?api-version=2024-05-01-preview",
                    headers={"api-key": self.api_key, "Content-Type": "application/json"},
                    json=json_body,
                    timeout=10.0,
                )
                if response.status_code != 200:
                    logger.warning("azure_search.failed", status=response.status_code)
                    return []
            data = response.json()
            results = [
                {
                    "id": str(doc.get("id", "")),
                    "title": doc.get("title", ""),
                    "content": doc.get("content", ""),
                    "source": doc.get("source", ""),
                    "score": float(doc.get("@search.rerankerScore", doc.get("@search.score", 0.0))),
                }
                for doc in data.get("value", [])
                if float(doc.get("@search.rerankerScore", doc.get("@search.score", 0.0)))
                >= (1.0 if doc.get("@search.rerankerScore") is not None else 0.01)
            ]
            logger.info(
                "search.results",
                provider="azure",
                result_count=len(results),
                top_score=results[0]["score"] if results else None,
            )
            return results


class InMemorySearchClient:
    """Fallback in-memory search for local dev without any external dependencies."""

    MOCK_DOCS = [
        {
            "id": "vpn-connect",
            "title": "How to connect to VPN",
            "content": "To connect to the company VPN: 1. Open GlobalProtect app. 2. Enter your employee ID. 3. Authenticate with MFA. 4. Click Connect.",
            "source": "IT Knowledge Base",
            "score": 0.0,
        },
        {
            "id": "password-policy",
            "title": "Password Reset Policy",
            "content": "Passwords must be at least 12 characters, include uppercase, lowercase, number and special character. Passwords expire every 90 days.",
            "source": "IT Policy",
            "score": 0.0,
        },
        {
            "id": "software-request",
            "title": "How to request new software",
            "content": "Submit a software request ticket via Bobby or the IT portal. Include the software name, business justification, and your manager approval.",
            "source": "IT Knowledge Base",
            "score": 0.0,
        },
    ]

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        terms = _search_terms(query)
        if not terms:
            return []
        results = []
        for source_doc in self.MOCK_DOCS:
            doc = dict(source_doc)
            title = doc["title"].lower()
            content = doc["content"].lower()
            matches = sum(2 if term in title else 1 if term in content else 0 for term in terms)
            if matches:
                doc["score"] = min(matches / max(len(terms) * 2, 1), 1.0)
                results.append(doc)
        ranked = sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
        logger.info(
            "search.results",
            provider="in_memory",
            result_count=len(ranked),
            top_score=ranked[0]["score"] if ranked else None,
        )
        return ranked


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
        logger.info("search.provider_selected", provider=type(_search_instance).__name__)
    return _search_instance
