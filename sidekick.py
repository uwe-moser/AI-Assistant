import asyncio
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

import aiosqlite
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from config import CHECKPOINTS_DB_PATH, DB_PATH, DEFAULT_MODEL
from sidekick_tools import other_tools, playwright_tools
from user_profile import UserProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------

class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
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
# Static prompt fragments
# ---------------------------------------------------------------------------

_TOOL_DESCRIPTION_BLOCK = """\
    You have the following tools available:
    - Web browsing: Navigate to URLs, click links, fill forms, and extract content from web pages.
    - Web search: Search the internet using Google for up-to-date information.
    - File management: Read, write, move, copy, delete, and list files in the sandbox directory.
    - Python execution: Run Python code. Include print() statements to receive output.
    - Wikipedia: Look up general knowledge topics on Wikipedia.
    - PDF reader: Extract text from PDF files in the sandbox directory. Pass the file path relative to the sandbox folder.
    - PDF creator: Create a proper, valid PDF file in the sandbox. Pass a JSON string with 'filename', 'title', and 'content'. ALWAYS use this instead of write_file when creating .pdf files.
    - arXiv search: Search for academic papers on arXiv by topic, author, or keyword.
    - YouTube transcripts: Fetch the transcript of any YouTube video by passing its URL or video ID.
    - Push notifications: Send push notifications to alert the user."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_worker_prompt(state: State, memory_context: str) -> str:
    """Build the full system prompt for the worker node."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = f"""\
You are a helpful assistant that can use tools to complete tasks.
    You keep working on a task until either you have a question or clarification for the user, or the success criteria is met.
    The current date and time is {now}
    {memory_context}

{_TOOL_DESCRIPTION_BLOCK}

    This is the success criteria:
    {state["success_criteria"]}
    You should reply either with a question for the user about this assignment, or with your final response.
    If you have a question for the user, you need to reply by clearly stating your question. An example might be:

    Question: please clarify whether you want a summary or a detailed answer

    If you've finished, reply with the final answer, and don't ask a question; simply reply with the answer.
    """

    if state.get("feedback_on_work"):
        prompt += f"""
    Previously you thought you completed the assignment, but your reply was rejected because the success criteria was not met.
    Here is the feedback on why this was rejected:
    {state["feedback_on_work"]}
    With this feedback, please continue the assignment, ensuring that you meet the success criteria or have a question for the user."""

    return prompt


def _format_conversation(messages: List[Any]) -> str:
    """Format message list into a readable conversation string."""
    conversation = "Conversation history:\n\n"
    for message in messages:
        if isinstance(message, HumanMessage):
            conversation += f"User: {message.content}\n"
        elif isinstance(message, AIMessage):
            text = message.content or "[Tools use]"
            conversation += f"Assistant: {text}\n"
    return conversation


# ---------------------------------------------------------------------------
# Sidekick
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
        self.browser = None
        self.playwright = None
        self._profile_extractor = None

    async def setup(self):
        self._db_conn = await aiosqlite.connect(CHECKPOINTS_DB_PATH)
        self.memory = AsyncSqliteSaver(self._db_conn)
        self.tools, self.browser, self.playwright = await playwright_tools()
        self.tools += other_tools()
        worker_llm = ChatOpenAI(model=DEFAULT_MODEL)
        self.worker_llm_with_tools = worker_llm.bind_tools(self.tools)
        evaluator_llm = ChatOpenAI(model=DEFAULT_MODEL)
        self.evaluator_llm_with_output = evaluator_llm.with_structured_output(EvaluatorOutput)
        self._profile_extractor = ChatOpenAI(model=DEFAULT_MODEL).with_structured_output(ProfileUpdate)
        self.build_graph()

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
        recent_block = "\n\n    Recent conversation history:\n" + "\n".join(lines)
        return profile_block + recent_block

    async def _extract_and_update_profile(self, user_message: str, assistant_reply: str):
        """Use an LLM to extract user facts from the latest exchange and persist them."""
        existing = self.user_profile.get_all()
        existing_summary = ", ".join(f"{k}={v}" for k, v in existing.items()) if existing else "none yet"

        prompt = f"""You extract facts about a user from their conversation with an AI assistant.
Only extract facts that are explicitly stated or clearly implied about the USER (not the assistant).
Examples of good facts: name, location, occupation, interests, preferred_language, preferred_output_format, technical_level.
Do NOT repeat facts already known: {existing_summary}
Do NOT invent facts. Return an empty list if nothing new is learned.

User said: {user_message}
Assistant replied: {assistant_reply[:500]}"""

        result = self._profile_extractor.invoke([HumanMessage(content=prompt)])
        for fact in result.facts:
            self.user_profile.upsert(fact.key, fact.value)

    def worker(self, state: State) -> Dict[str, Any]:
        memory_context = self._get_memory_context()
        system_message = _build_worker_prompt(state, memory_context)

        # Prepend a fresh SystemMessage, filtering out any old ones
        filtered = [m for m in state["messages"] if not isinstance(m, SystemMessage)]
        messages = [SystemMessage(content=system_message)] + filtered

        response = self.worker_llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def worker_router(self, state: State) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "evaluator"

    def evaluator(self, state: State) -> dict[str, Any]:
        last_response = state["messages"][-1].content

        system_message = """You are an evaluator that determines if a task has been completed successfully by an Assistant.
    Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
    and whether more input is needed from the user."""

        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

    The entire conversation with the assistant, with the user's original request and all replies, is:
    {_format_conversation(state["messages"])}

    The success criteria for this assignment is:
    {state["success_criteria"]}

    And the final response from the Assistant that you are evaluating is:
    {last_response}

    Respond with your feedback, and decide if the success criteria is met by this response.
    Also, decide if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help.

    The Assistant has access to a tool to write files. If the Assistant says they have written a file, then you can assume they have done so.
    Overall you should give the Assistant the benefit of the doubt if they say they've done something. But you should reject if you feel that more work should go into this.

    """
        if state["feedback_on_work"]:
            user_message += f"Also, note that in a prior attempt from the Assistant, you provided this feedback: {state['feedback_on_work']}\n"
            user_message += "If you're seeing the Assistant repeating the same mistakes, then consider responding that user input is required."

        evaluator_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        eval_result = self.evaluator_llm_with_output.invoke(evaluator_messages)
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Evaluator Feedback on this answer: {eval_result.feedback}",
                }
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }

    def route_based_on_evaluation(self, state: State) -> str:
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        return "worker"

    def build_graph(self):
        graph_builder = StateGraph(State)

        graph_builder.add_node("worker", self.worker)
        graph_builder.add_node("tools", ToolNode(tools=self.tools))
        graph_builder.add_node("evaluator", self.evaluator)

        graph_builder.add_conditional_edges(
            "worker", self.worker_router, {"tools": "tools", "evaluator": "evaluator"}
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator", self.route_based_on_evaluation, {"worker": "worker", "END": END}
        )
        graph_builder.add_edge(START, "worker")

        self.graph = graph_builder.compile(checkpointer=self.memory)

    async def run_superstep(self, message, success_criteria, history):
        config = {"configurable": {"thread_id": self.sidekick_id}}

        state = {
            "messages": message,
            "success_criteria": success_criteria or "The answer should be clear and accurate",
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
                                "metadata": {"title": f"Calling tool: {tc['name']}"},
                            }
                            history = history + [tool_msg]
                        yield history
                    else:
                        worker_reply_content = ai_msg.content

                elif node_name == "tools":
                    for tool_result in node_output["messages"]:
                        content = tool_result.content if hasattr(tool_result, "content") else str(tool_result)
                        truncated = content[:500] + ("..." if len(content) > 500 else "")
                        tool_name = tool_result.name if hasattr(tool_result, "name") else "tool"
                        result_msg = {
                            "role": "assistant",
                            "content": truncated,
                            "metadata": {"title": f"Result: {tool_name}"},
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

    async def _async_cleanup(self):
        """Close browser and DB resources asynchronously."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self._db_conn:
            await self._db_conn.close()

    def cleanup(self):
        """Release all resources, handling both running and absent event loops."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_cleanup())
        except RuntimeError:
            asyncio.run(self._async_cleanup())
