"""Base class for specialized sub-agents."""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from config import DEFAULT_MODEL


class BaseAgent:
    """A lightweight ReAct agent with a focused set of tools.

    Subclasses override ``system_prompt`` to define the agent's persona.
    The orchestrator wraps each agent's ``run()`` method as a LangChain Tool.
    """

    system_prompt: str = "You are a helpful assistant."

    def __init__(self, tools):
        self.tools = tools
        llm = ChatOpenAI(model=DEFAULT_MODEL)
        self._graph = create_react_agent(llm, tools)

    async def run(self, task: str, context: str = "") -> str:
        """Execute *task* using this agent's tool set and return the result."""
        system_content = self.system_prompt
        if context:
            system_content += f"\n\nContext from the orchestrator:\n{context}"

        try:
            result = await self._graph.ainvoke({
                "messages": [
                    SystemMessage(content=system_content),
                    HumanMessage(content=task),
                ]
            })
            return result["messages"][-1].content
        except Exception as e:
            return f"Error: Agent failed - {type(e).__name__}: {e}"
