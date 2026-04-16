"""Research agent: web search, Wikipedia, arXiv, YouTube transcripts."""

from agents.base import BaseAgent


class ResearchAgent(BaseAgent):
    system_prompt = (
        "You are a research specialist. Use your tools to find information "
        "from the web, Wikipedia, arXiv, and YouTube transcripts. "
        "Return comprehensive, well-organized findings."
    )
