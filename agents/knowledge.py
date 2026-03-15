"""Knowledge agent: personal document collection search and management."""

from agents.base import BaseAgent


class KnowledgeAgent(BaseAgent):
    system_prompt = (
        "You are a knowledge base specialist. Search, index, list, and "
        "manage the user's personal document collection. Use semantic search "
        "to find relevant information in their indexed documents."
    )
