import os
import requests
import logging
from typing import List
from config import Config
from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        Config.validate()
        self.db = SupabaseService()
        self.hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
        self.hf_api_url = "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5"
        self.headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}

    def get_embedding(self, text: str) -> List[float]:
        """Gets vector embedding from HuggingFace API for a search query."""
        if not self.hf_token:
            logger.warning("HUGGINGFACE_TOKEN not set. RAG search might fail due to rate limits.")

        try:
            response = requests.post(
                self.hf_api_url,
                headers=self.headers,
                json={"inputs": text, "options": {"wait_for_model": True}}
            )
            response.raise_for_status()

            result = response.json()
            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
                return result[0]
            elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], float):
                return result

            logger.error(f"Unexpected HF API response: {result[:50]}...")
            return []

        except Exception as e:
            logger.error(f"Failed to get embedding for query: {e}")
            return []

    def get_knowledge_base_context(self, query: str, limit: int = 3, threshold: float = 0.4) -> str:
        """Searches the knowledge base and formats the results into a context string."""
        logger.info(f"RAG Search triggered for query: '{query}'")

        # 1. Embed the query
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return ""

        # 2. Search Supabase
        results = self.db.search_knowledge_base(query_embedding, limit=limit, threshold=threshold)

        if not results:
            logger.info("RAG Search found no relevant documents.")
            return ""

        # 3. Format context
        context_parts = ["--- KNOWLEDGE BASE CONTEXT ---"]
        for i, res in enumerate(results):
            similarity = res.get('similarity', 0)
            content = res.get('content', '')
            source = res.get('metadata', {}).get('source', 'Unknown')

            # Only include if similarity is decent
            context_parts.append(f"[Source {i + 1}: {source} (Score: {similarity:.2f})]\n{content.strip()}")

        context_parts.append("------------------------------")

        logger.info(f"RAG Search found {len(results)} highly relevant match(es).")
        return "\n\n".join(context_parts)


# Singleton instance access
_rag_service = None


def get_rag_service():
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
