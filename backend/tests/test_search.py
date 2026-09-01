"""Search relevance and no-arbitrary-fallback regression tests."""
import pytest

from integrations.search_client import AzureSearchClient, InMemorySearchClient, SupabaseSearchClient


@pytest.mark.asyncio
async def test_in_memory_search_returns_relevant_document():
    results = await InMemorySearchClient().search("connect company VPN", top_k=3)
    assert results
    assert results[0]["id"] == "vpn-connect"
    assert results[0]["score"] > 0


@pytest.mark.asyncio
async def test_in_memory_search_expands_it_synonyms():
    results = await InMemorySearchClient().search("remote connection", top_k=3)
    assert results
    assert results[0]["id"] == "vpn-connect"


@pytest.mark.asyncio
async def test_in_memory_search_does_not_return_arbitrary_documents():
    results = await InMemorySearchClient().search("quantum gardening holiday", top_k=3)
    assert results == []


@pytest.mark.asyncio
async def test_empty_or_stopword_query_returns_no_documents():
    client = InMemorySearchClient()
    assert await client.search("") == []
    assert await client.search("how can you help me") == []


@pytest.mark.asyncio
async def test_azure_filters_low_relevance_and_preserves_metadata(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {
                "value": [
                    {
                        "id": "good",
                        "title": "VPN guide",
                        "content": "VPN help",
                        "source": "KB",
                        "@search.rerankerScore": 2.1,
                    },
                    {
                        "id": "weak",
                        "title": "Unrelated",
                        "content": "Other",
                        "source": "KB",
                        "@search.rerankerScore": 0.4,
                    },
                ]
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("integrations.search_client.httpx.AsyncClient", lambda *a, **k: Client())
    client = AzureSearchClient()
    client.endpoint = "https://example.search.windows.net"
    client.index = "knowledge"
    client.api_key = "test"
    results = await client.search("VPN", top_k=3)
    assert [result["id"] for result in results] == ["good"]
    assert results[0]["score"] == 2.1


@pytest.mark.asyncio
async def test_supabase_lexical_search_batches_synonyms_and_ranks_tags(monkeypatch):
    requests = []

    class Response:
        status_code = 200

        def json(self):
            return [
                {
                    "id": 7,
                    "title": "Office wireless troubleshooting",
                    "content": "Reconnect to the corporate wireless network.",
                    "category": "wifi",
                    "tags": ["wifi", "wireless", "connectivity"],
                    "source": "IPN IT Knowledge Base",
                }
            ]

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            requests.append(url)
            return Response()

    def no_embeddings():
        raise ValueError("embeddings unavailable in lexical fallback test")

    monkeypatch.setattr("integrations.llm_client.get_embedding_model", no_embeddings)
    monkeypatch.setattr("integrations.search_client.httpx.AsyncClient", lambda *a, **k: Client())
    client = SupabaseSearchClient()
    client.url = "https://example.supabase.co"
    client.key = "test"
    results = await client.search("wifi not connected", top_k=3)

    assert len(requests) == 1
    assert "tags.cs" in requests[0]
    assert [result["id"] for result in results] == ["7"]
    assert results[0]["score"] >= 0.2
