import json
import logging
import os
from urllib.parse import urlparse, parse_qs

import requests
from fpdf import FPDF
from langchain.agents import Tool
from langchain_community.agent_toolkits import FileManagementToolkit, PlayWrightBrowserToolkit
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from langchain_experimental.tools import PythonREPLTool
from playwright.async_api import async_playwright
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi

from config import SANDBOX_DIR, PUSHOVER_URL, FONT_SEARCH_PATHS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy accessors for env-var-dependent globals
# ---------------------------------------------------------------------------

_serper = None


def _get_serper() -> GoogleSerperAPIWrapper:
    global _serper
    if _serper is None:
        _serper = GoogleSerperAPIWrapper()
    return _serper


def _get_pushover_credentials() -> tuple[str | None, str | None]:
    return os.getenv("PUSHOVER_TOKEN"), os.getenv("PUSHOVER_USER")


# ---------------------------------------------------------------------------
# Playwright
# ---------------------------------------------------------------------------

async def playwright_tools():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
    return toolkit.get_tools(), browser, playwright


# ---------------------------------------------------------------------------
# Push notifications
# ---------------------------------------------------------------------------

def push(text: str) -> str:
    """Send a push notification to the user."""
    token, user = _get_pushover_credentials()
    if not token or not user:
        return "Error: PUSHOVER_TOKEN or PUSHOVER_USER not configured"
    try:
        resp = requests.post(PUSHOVER_URL, data={"token": token, "user": user, "message": text})
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Push notification failed: %s", exc)
        return f"Error sending push notification: {exc}"
    return "success"


# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------

def get_file_tools():
    toolkit = FileManagementToolkit(root_dir=SANDBOX_DIR)
    return toolkit.get_tools()


# ---------------------------------------------------------------------------
# PDF tools
# ---------------------------------------------------------------------------

def read_pdf(file_path: str) -> str:
    """Read text content from a PDF file in the sandbox directory."""
    full_path = os.path.join(SANDBOX_DIR, file_path)
    if not os.path.isfile(full_path):
        return f"Error: file not found at {full_path}"
    reader = PdfReader(full_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"--- Page {i + 1} ---\n{text}")
    if not pages:
        return "The PDF contains no extractable text."
    return "\n\n".join(pages)


_UNICODE_REPLACEMENTS = {
    "\u2014": "--",   # em-dash
    "\u2013": "-",    # en-dash
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
    "\u2022": "-",    # bullet
    "\u00a0": " ",    # non-breaking space
    "\u200b": "",     # zero-width space
}


def _sanitize_for_pdf(text: str) -> str:
    """Replace Unicode characters that cause issues with built-in PDF fonts."""
    for char, repl in _UNICODE_REPLACEMENTS.items():
        text = text.replace(char, repl)
    return text


def _find_unicode_font() -> str | None:
    """Return the first available TTF font path, or None."""
    for path in FONT_SEARCH_PATHS:
        if os.path.exists(path):
            return path
    return None


def create_pdf(filename: str, content: str, title: str = "") -> str:
    """Create a PDF file in the sandbox directory.

    Args:
        filename: Output filename (e.g. 'report.pdf').
        content: The body text.
        title: Optional heading for the document.
    """
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    full_path = os.path.join(SANDBOX_DIR, filename)
    os.makedirs(SANDBOX_DIR, exist_ok=True)

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    ttf_path = _find_unicode_font()
    unicode_font = False
    if ttf_path:
        try:
            pdf.add_font("UnicodeFont", "", ttf_path)
            pdf.add_font("UnicodeFont", "B", ttf_path)
            unicode_font = True
        except Exception:
            pass

    if not unicode_font:
        title = _sanitize_for_pdf(title)
        content = _sanitize_for_pdf(content)

    font_family = "UnicodeFont" if unicode_font else "Helvetica"

    if title:
        pdf.set_font(font_family, style="B", size=16)
        pdf.multi_cell(0, 10, title, align="L")
        pdf.ln(4)

    pdf.set_font(font_family, size=11)
    for paragraph in content.split("\n"):
        if paragraph.strip() == "":
            pdf.ln(4)
        else:
            pdf.multi_cell(0, 7, paragraph)

    pdf.output(full_path)
    return f"PDF successfully created at {SANDBOX_DIR}/{filename}"


# Wrapper that accepts a JSON string for backward compatibility with LangChain Tool
def _create_pdf_from_json(input_str: str) -> str:
    """Parse JSON input and delegate to create_pdf."""
    try:
        data = json.loads(input_str)
    except json.JSONDecodeError as e:
        return f"Error: input must be valid JSON. {e}"
    return create_pdf(
        filename=data.get("filename", "output.pdf"),
        content=data.get("content", ""),
        title=data.get("title", ""),
    )


# ---------------------------------------------------------------------------
# YouTube transcripts
# ---------------------------------------------------------------------------

def get_youtube_transcript(url_or_id: str) -> str:
    """Get the transcript of a YouTube video given its URL or video ID."""
    video_id = url_or_id.strip()

    parsed = urlparse(video_id)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        qs = parse_qs(parsed.query)
        video_id = qs.get("v", [video_id])[0]
    elif parsed.hostname == "youtu.be":
        video_id = parsed.path.lstrip("/")

    ytt_api = YouTubeTranscriptApi()
    transcript = ytt_api.fetch(video_id)
    lines = [entry.text for entry in transcript.snippets]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def other_tools():
    push_tool = Tool(name="send_push_notification", func=push, description="Use this tool when you want to send a push notification")
    file_tools = get_file_tools()

    def _search(query: str) -> str:
        return _get_serper().run(query)

    tool_search = Tool(
        name="search",
        func=_search,
        description="Use this tool when you want to get the results of an online web search",
    )

    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)

    python_repl = PythonREPLTool()

    arxiv = ArxivAPIWrapper()
    arxiv_tool = ArxivQueryRun(api_wrapper=arxiv)

    pdf_tool = Tool(
        name="read_pdf",
        func=read_pdf,
        description="Read and extract text from a PDF file in the sandbox directory. Pass the file path relative to the sandbox folder.",
    )

    youtube_tool = Tool(
        name="get_youtube_transcript",
        func=get_youtube_transcript,
        description="Get the transcript of a YouTube video. Pass a YouTube URL or video ID.",
    )

    create_pdf_tool = Tool(
        name="create_pdf",
        func=_create_pdf_from_json,
        description=(
            "Create a valid, openable PDF file in the sandbox directory. "
            "ALWAYS use this tool instead of write_file when the output filename ends in .pdf. "
            "Input must be a JSON string with keys: 'filename' (e.g. 'report.pdf'), "
            "'title' (optional heading), and 'content' (the body text). "
            'Example: {"filename": "summary.pdf", "title": "My Title", "content": "Line one\\nLine two"}'
        ),
    )

    return file_tools + [push_tool, tool_search, python_repl, wiki_tool, arxiv_tool, pdf_tool, youtube_tool, create_pdf_tool]
