"""
ApexFlow Orchestrator — multi-agent architecture.

The Sidekick class is the top-level orchestrator.  Instead of binding 40+
tools directly, it delegates to specialized sub-agents (research, browser,
documents, knowledge, location, system), each exposed as a single tool.

The evaluator loop is **optional**: it only runs when the user provides
explicit success criteria.
"""

from typing import Annotated, List, Any, Optional, Dict
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import Tool
from langchain_community.chat_message_histories import SQLChatMessageHistory
from pydantic import BaseModel, Field

from config import DB_PATH, CHECKPOINTS_DB_PATH, DEFAULT_MODEL
from user_profile import UserProfile

from agents.research import ResearchAgent
from agents.browser import BrowserAgent
from agents.documents import DocumentsAgent
from agents.knowledge import KnowledgeAgent
from agents.location import LocationAgent
from agents.system import SystemAgent

from tools.research import get_tools as get_research_tools
from tools.documents import get_tools as get_documents_tools
from tools.knowledge_tools import get_tools as get_knowledge_tools
from tools.location import get_tools as get_location_tools
from tools.system import get_tools as get_system_tools

import uuid
import aiosqlite
import asyncio
from datetime import datetime


# ---------------------------------------------------------------------------
# State & schemas
# ---------------------------------------------------------------------------

class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    has_explicit_criteria: bool
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool


class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(
        description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
    )


class ProfileFact(BaseModel):
    key: str = Field(description="Snake_case fact name, e.g. 'name', 'location', 'preferred_output_format'")
    value: str = Field(description="The fact value, concise and specific")


class ProfileUpdate(BaseModel):
    facts: List[ProfileFact] = Field(
        description="Facts learned about the user from this conversation. Empty list if nothing new."
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Sidekick:
    def __init__(self, session_id: str = None):
        self.worker_llm_with_tools = None
        self.evaluator_llm_with_output = None
        self.tools = None
        self.graph = None
        self.sidekick_id = session_id or str(uuid.uuid4())
        self._db_conn = None
        self.memory = None
        self.chat_history = SQLChatMessageHistory(
            session_id=self.sidekick_id,
            connection=f"sqlite:///{DB_PATH}",
        )
        self.user_profile = UserProfile()
        self.browser_agent = None
        self._agents: Dict[str, Any] = {}

    async def setup(self, include_browser=True):
        self._db_conn = await aiosqlite.connect(CHECKPOINTS_DB_PATH)
        self.memory = AsyncSqliteSaver(self._db_conn)

        # Create sub-agents with their tool sets
        self._agents["research"] = ResearchAgent(get_research_tools())
        self._agents["documents"] = DocumentsAgent(get_documents_tools())
        self._agents["knowledge"] = KnowledgeAgent(get_knowledge_tools())
        self._agents["system"] = SystemAgent(get_system_tools())

        location_tools = get_location_tools()
        if location_tools:
            self._agents["location"] = LocationAgent(location_tools)

        if include_browser:
            self.browser_agent = await BrowserAgent.create()
            self._agents["browser"] = self.browser_agent

        # Wrap each agent as a tool for the orchestrator
        self.tools = self._create_agent_tools()

        worker_llm = ChatOpenAI(model=DEFAULT_MODEL)
        self.worker_llm_with_tools = worker_llm.bind_tools(self.tools)

        evaluator_llm = ChatOpenAI(model=DEFAULT_MODEL)
        self.evaluator_llm_with_output = evaluator_llm.with_structured_output(EvaluatorOutput)

        self.build_graph()

    def _create_agent_tools(self) -> list:
        """Wrap each sub-agent's run() method as a LangChain Tool."""
        agent_descriptions = {
            "research": (
                "Research specialist: search the web (Google), Wikipedia, arXiv academic papers, "
                "and YouTube video transcripts for information."
            ),
            "browser": (
                "Browser specialist: navigate to URLs, click links, fill forms, take screenshots, "
                "and extract content from web pages using a real Chromium browser."
            ),
            "documents": (
                "Document specialist: read/write/manage files in the sandbox, create PDFs, "
                "read/write spreadsheets (CSV/Excel), and generate PNG charts."
            ),
            "knowledge": (
                "Knowledge base specialist: search, index, list, and remove documents in the "
                "user's personal document collection (semantic search over PDFs, text, markdown, CSV)."
            ),
            "location": (
                "Location specialist: analyze addresses for family suitability (nearby schools, "
                "supermarkets, playgrounds with walking times), calculate commute times, "
                "and search Google Places for points of interest."
            ),
            "system": (
                "System specialist: schedule recurring background tasks with cron expressions, "
                "send push notifications, list/cancel scheduled tasks, and run Python code."
            ),
        }

        tools = []
        for name, agent in self._agents.items():
            tools.append(Tool(
                name=f"{name}_agent",
                func=lambda *args, **kwargs: None,
                coroutine=agent.run,
                description=agent_descriptions[name],
            ))
        return tools

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def _get_memory_context(self) -> str:
        """Build a compact memory block: user profile + last 3 conversation pairs."""
        profile_block = self.user_profile.get_prompt_block()

        past = self.chat_history.messages[-6:]
        if not past:
            return profile_block

        lines = []
        for msg in past:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            content = msg.content[:300]
            lines.append(f"  {role}: {content}")
        recent_block = (
            "\n\n    Recent conversation history:\n" + "\n".join(lines)
        )
        return profile_block + recent_block

    async def _extract_and_update_profile(self, user_message: str, assistant_reply: str):
        """Use an LLM to extract user facts from the latest exchange and persist them."""
        extractor_llm = ChatOpenAI(model=DEFAULT_MODEL).with_structured_output(ProfileUpdate)
        existing = self.user_profile.get_all()
        existing_summary = ", ".join(f"{k}={v}" for k, v in existing.items()) if existing else "none yet"

        prompt = f"""You extract facts about a user from their conversation with an AI assistant.
Only extract facts that are explicitly stated or clearly implied about the USER (not the assistant).
Examples of good facts: name, location, occupation, interests, preferred_language, preferred_output_format, technical_level.
Do NOT repeat facts already known: {existing_summary}
Do NOT invent facts. Return an empty list if nothing new is learned.

User said: {user_message}
Assistant replied: {assistant_reply[:500]}"""

        result = extractor_llm.invoke([HumanMessage(content=prompt)])
        for fact in result.facts:
            self.user_profile.upsert(fact.key, fact.value)

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    def _build_agent_list(self) -> str:
        """Build a short list of available agents for the system prompt."""
        lines = []
        for tool in self.tools:
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    def worker(self, state: State) -> Dict[str, Any]:
        memory_context = self._get_memory_context()

        system_message = f"""You are an orchestrator that delegates tasks to specialized agents.
The current date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{memory_context}

You have these specialist agents available:
{self._build_agent_list()}

Delegate tasks to the right agent by calling them with a clear, specific instruction.
You can call multiple agents in sequence to complete complex tasks.
When an agent returns results, synthesize them into a clear response for the user.

If you need clarification from the user, ask directly without calling any agent.
"""

        if state.get("has_explicit_criteria"):
            system_message += f"""
The user provided these success criteria for this task:
{state["success_criteria"]}
"""

        if state.get("feedback_on_work"):
            system_message += f"""
Previously your response was rejected because the success criteria were not met.
Feedback: {state["feedback_on_work"]}
Please continue working to meet the criteria or ask the user for clarification."""

        messages = [
            SystemMessage(content=system_message) if isinstance(m, SystemMessage) else m
            for m in state["messages"]
        ]
        if not any(isinstance(m, SystemMessage) for m in state["messages"]):
            messages = [SystemMessage(content=system_message)] + messages

        response = self.worker_llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def worker_router(self, state: State) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        # Skip evaluator when no explicit success criteria
        if not state.get("has_explicit_criteria"):
            return "end"
        return "evaluator"

    def format_conversation(self, messages: List[Any]) -> str:
        conversation = "Conversation history:\n\n"
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                text = message.content or "[Tools use]"
                conversation += f"Assistant: {text}\n"
        return conversation

    def evaluator(self, state: State) -> State:
        last_response = state["messages"][-1].content

        system_message = """You are an evaluator that determines if a task has been completed successfully by an Assistant.
Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
and whether more input is needed from the user."""

        user_message = f"""You are evaluating a conversation between the User and Assistant.

The entire conversation is:
{self.format_conversation(state["messages"])}

The success criteria for this assignment is:
{state["success_criteria"]}

The final response from the Assistant that you are evaluating is:
{last_response}

Respond with your feedback, and decide if the success criteria is met.
Also, decide if more user input is required.

The Assistant has access to specialized agents with tools. If the Assistant says they have done something, give them the benefit of the doubt.
But reject if you feel that more work should go into this.
"""
        if state["feedback_on_work"]:
            user_message += f"Also, note that in a prior attempt, you provided this feedback: {state['feedback_on_work']}\n"
            user_message += "If the Assistant is repeating the same mistakes, respond that user input is required."

        evaluator_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        eval_result = self.evaluator_llm_with_output.invoke(evaluator_messages)
        return {
            "messages": [
                {"role": "assistant", "content": f"Evaluator Feedback: {eval_result.feedback}"}
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }

    def route_based_on_evaluation(self, state: State) -> str:
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        return "worker"

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def build_graph(self):
        graph_builder = StateGraph(State)

        graph_builder.add_node("worker", self.worker)
        graph_builder.add_node("tools", ToolNode(tools=self.tools))
        graph_builder.add_node("evaluator", self.evaluator)

        graph_builder.add_conditional_edges(
            "worker",
            self.worker_router,
            {"tools": "tools", "evaluator": "evaluator", "end": END},
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator",
            self.route_based_on_evaluation,
            {"worker": "worker", "END": END},
        )
        graph_builder.add_edge(START, "worker")

        self.graph = graph_builder.compile(checkpointer=self.memory)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_superstep(self, message, success_criteria, history):
        config = {"configurable": {"thread_id": self.sidekick_id}}

        has_explicit = bool(success_criteria and success_criteria.strip())

        state = {
            "messages": message,
            "success_criteria": success_criteria or "The answer should be clear and accurate",
            "has_explicit_criteria": has_explicit,
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }

        user_msg = {"role": "user", "content": message}
        history = history + [user_msg]
        yield history

        worker_reply_content = ""
        evaluator_feedback_content = ""

        async for chunk in self.graph.astream(state, config=config):
            for node_name, node_output in chunk.items():
                if node_name == "worker":
                    ai_msg = node_output["messages"][-1]
                    if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
                        for tc in ai_msg.tool_calls:
                            args_summary = ", ".join(
                                f"{k}={repr(v)[:80]}" for k, v in tc["args"].items()
                            )
                            tool_msg = {
                                "role": "assistant",
                                "content": f"**{tc['name']}**({args_summary})",
                                "metadata": {"title": f"\U0001f916 Delegating to: {tc['name']}"},
                            }
                            history = history + [tool_msg]
                        yield history
                    else:
                        worker_reply_content = ai_msg.content

                elif node_name == "tools":
                    for tool_result in node_output["messages"]:
                        content = tool_result.content if hasattr(tool_result, "content") else str(tool_result)
                        truncated = content[:500] + ("..." if len(content) > 500 else "")
                        tool_name = tool_result.name if hasattr(tool_result, "name") else "agent"
                        result_msg = {
                            "role": "assistant",
                            "content": truncated,
                            "metadata": {"title": f"\U0001f4cb Result: {tool_name}"},
                        }
                        history = history + [result_msg]
                    yield history

                elif node_name == "evaluator":
                    evaluator_feedback_content = node_output["messages"][-1]["content"] if node_output.get("messages") else ""

        if worker_reply_content:
            reply = {"role": "assistant", "content": worker_reply_content}
            history = history + [reply]
            yield history

        if evaluator_feedback_content:
            feedback = {"role": "assistant", "content": evaluator_feedback_content}
            history = history + [feedback]
            yield history

        # Persist to long-term memory
        if worker_reply_content:
            self.chat_history.add_user_message(message)
            self.chat_history.add_ai_message(worker_reply_content)
            await self._extract_and_update_profile(message, worker_reply_content)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        if self.browser_agent:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.browser_agent.cleanup())
            except RuntimeError:
                asyncio.run(self.browser_agent.cleanup())
        if self._db_conn:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._db_conn.close())
            except RuntimeError:
                asyncio.run(self._db_conn.close())
