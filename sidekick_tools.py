from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from dotenv import load_dotenv
import os
import requests
from langchain.agents import Tool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_experimental.tools import PythonREPLTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from fpdf import FPDF



load_dotenv(override=True)
pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")
pushover_url = "https://api.pushover.net/1/messages.json"
serper = GoogleSerperAPIWrapper()

async def playwright_tools():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
    return toolkit.get_tools(), browser, playwright


def push(text: str):
    """Send a push notification to the user"""
    requests.post(pushover_url, data = {"token": pushover_token, "user": pushover_user, "message": text})
    return "success"


def get_file_tools():
    toolkit = FileManagementToolkit(root_dir="sandbox")
    return toolkit.get_tools()


def read_pdf(file_path: str) -> str:
    """Read text content from a PDF file in the sandbox directory."""
    full_path = os.path.join("sandbox", file_path)
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


def _sanitize_for_pdf(text: str) -> str:
    """Replace Unicode characters that cause issues with built-in PDF fonts."""
    replacements = {
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
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text


def create_pdf(input: str) -> str:
    """Create a proper PDF file in the sandbox directory from a title and text content.
    Input must be a JSON string with keys: 'filename', 'title' (optional), 'content'.
    Example: {"filename": "report.pdf", "title": "My Report", "content": "Text here..."}
    """
    import json
    try:
        data = json.loads(input)
    except json.JSONDecodeError as e:
        return f"Error: input must be valid JSON. {e}"

    filename = data.get("filename", "output.pdf")
    title = data.get("title", "")
    content = data.get("content", "")

    if not filename.endswith(".pdf"):
        filename += ".pdf"

    full_path = os.path.join("sandbox", filename)
    os.makedirs("sandbox", exist_ok=True)

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    # Try to use a Unicode-capable TTF font, fall back to Helvetica with sanitization
    unicode_font = False
    ttf_path = "/Library/Fonts/Arial Unicode.ttf"
    if os.path.exists(ttf_path):
        try:
            pdf.add_font("ArialUnicode", "", ttf_path)
            pdf.add_font("ArialUnicode", "B", ttf_path)
            unicode_font = True
        except Exception:
            pass

    if not unicode_font:
        title = _sanitize_for_pdf(title)
        content = _sanitize_for_pdf(content)

    font_family = "ArialUnicode" if unicode_font else "Helvetica"

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
    return f"PDF successfully created at sandbox/{filename}"


def get_youtube_transcript(url_or_id: str) -> str:
    """Get the transcript of a YouTube video given its URL or video ID."""
    video_id = url_or_id.strip()
    # Extract video ID from common URL formats
    for prefix in ["https://www.youtube.com/watch?v=", "https://youtube.com/watch?v=",
                    "https://youtu.be/", "https://m.youtube.com/watch?v="]:
        if video_id.startswith(prefix):
            video_id = video_id[len(prefix):].split("&")[0].split("?")[0]
            break
    ytt_api = YouTubeTranscriptApi()
    transcript = ytt_api.fetch(video_id)
    lines = [entry.text for entry in transcript.snippets]
    return "\n".join(lines)


async def other_tools():
    push_tool = Tool(name="send_push_notification", func=push, description="Use this tool when you want to send a push notification")
    file_tools = get_file_tools()

    tool_search = Tool(
        name="search",
        func=serper.run,
        description="Use this tool when you want to get the results of an online web search"
    )

    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)

    python_repl = PythonREPLTool()

    arxiv = ArxivAPIWrapper()
    arxiv_tool = ArxivQueryRun(api_wrapper=arxiv)

    pdf_tool = Tool(
        name="read_pdf",
        func=read_pdf,
        description="Read and extract text from a PDF file in the sandbox directory. Pass the file path relative to the sandbox folder."
    )

    youtube_tool = Tool(
        name="get_youtube_transcript",
        func=get_youtube_transcript,
        description="Get the transcript of a YouTube video. Pass a YouTube URL or video ID."
    )

    create_pdf_tool = Tool(
        name="create_pdf",
        func=create_pdf,
        description=(
            "Create a valid, openable PDF file in the sandbox directory. "
            "ALWAYS use this tool instead of write_file when the output filename ends in .pdf. "
            "Input must be a JSON string with keys: 'filename' (e.g. 'report.pdf'), "
            "'title' (optional heading), and 'content' (the body text). "
            'Example: {"filename": "summary.pdf", "title": "My Title", "content": "Line one\\nLine two"}'
        ),
    )

    return file_tools + [push_tool, tool_search, python_repl, wiki_tool, arxiv_tool, pdf_tool, youtube_tool, create_pdf_tool]

