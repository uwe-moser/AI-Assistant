"""
Shared fixtures for ApexFlow agent tests.

Provides mock LLMs, tool fixtures, temporary sandbox directories,
and an in-memory SQLite database for persistence tests.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


# ---------------------------------------------------------------------------
# Temporary sandbox directory
# ---------------------------------------------------------------------------

@pytest.fixture
def sandbox(tmp_path):
    """Provide a temporary sandbox directory and patch os references."""
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    return str(sandbox_dir)


@pytest.fixture
def sandbox_cwd(tmp_path, monkeypatch):
    """Create a sandbox/ subdir and chdir into its parent so relative
    sandbox/ paths in the tool functions resolve to the temp directory."""
    (tmp_path / "sandbox").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path / "sandbox"


# ---------------------------------------------------------------------------
# Temporary SQLite database for persistence tests
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Return a path to a temporary SQLite database file."""
    return str(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Mock LLM that returns predictable responses
# ---------------------------------------------------------------------------

class MockChatLLM:
    """A fake ChatOpenAI replacement for deterministic testing."""

    def __init__(self, response_content="Mock response", tool_calls=None):
        self.response_content = response_content
        self.tool_calls = tool_calls or []
        self.last_messages = None

    def invoke(self, messages):
        self.last_messages = messages
        msg = AIMessage(content=self.response_content)
        if self.tool_calls:
            msg.tool_calls = self.tool_calls
        return msg

    def bind_tools(self, tools):
        return self

    def with_structured_output(self, schema):
        return self


class MockStructuredLLM:
    """A fake LLM that returns a Pydantic model instance."""

    def __init__(self, output):
        self._output = output

    def invoke(self, messages):
        return self._output

    def with_structured_output(self, schema):
        return self


@pytest.fixture
def mock_llm():
    return MockChatLLM()


@pytest.fixture
def mock_llm_with_tool_call():
    """LLM that returns a tool call for 'search'."""
    return MockChatLLM(
        response_content="",
        tool_calls=[{
            "id": "call_123",
            "name": "search",
            "args": {"query": "test query"},
        }],
    )


# ---------------------------------------------------------------------------
# Sample graph state
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_state():
    """A minimal valid State dict for testing graph nodes."""
    return {
        "messages": [HumanMessage(content="Hello, help me search for Python tutorials")],
        "success_criteria": "Provide a list of Python tutorials",
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": False,
    }


@pytest.fixture
def sample_state_with_feedback():
    """State with prior evaluator feedback (rejection loop)."""
    return {
        "messages": [
            HumanMessage(content="Write a haiku about testing"),
            AIMessage(content="Tests verify code"),
        ],
        "success_criteria": "Write a haiku with exactly 5-7-5 syllable structure",
        "feedback_on_work": "The haiku does not follow the 5-7-5 syllable structure.",
        "success_criteria_met": False,
        "user_input_needed": False,
    }


# ---------------------------------------------------------------------------
# Sample PDF content for testing
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_pdf(sandbox):
    """Create a simple test PDF in the sandbox and return its filename."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, text="Test PDF Content", align="C")
    pdf.ln(10)
    pdf.cell(200, 10, text="This is a test document.", align="L")

    filename = "test_document.pdf"
    filepath = os.path.join(sandbox, filename)
    pdf.output(filepath)
    return filename
