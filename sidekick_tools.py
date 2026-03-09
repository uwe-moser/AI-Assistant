from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from dotenv import load_dotenv
import os
import json
import csv
import io
import requests
from langchain_core.tools import Tool
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
import openpyxl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt



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


def read_spreadsheet(file_path: str) -> str:
    """Read a CSV or Excel file from the sandbox directory and return a summary with the first rows.
    Pass the file path relative to the sandbox folder (e.g. 'data.csv' or 'report.xlsx').
    """
    full_path = os.path.join("sandbox", file_path)
    if not os.path.isfile(full_path):
        return f"Error: file not found at {full_path}"

    ext = os.path.splitext(file_path)[1].lower()
    rows = []
    headers = []

    try:
        if ext == ".csv":
            with open(full_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0:
                        headers = row
                    rows.append(row)
        elif ext in (".xlsx", ".xls"):
            wb = openpyxl.load_workbook(full_path, read_only=True, data_only=True)
            ws = wb.active
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                str_row = [str(c) if c is not None else "" for c in row]
                if i == 0:
                    headers = str_row
                rows.append(str_row)
            wb.close()
        else:
            return f"Error: unsupported file type '{ext}'. Use .csv, .xlsx, or .xls."
    except Exception as e:
        return f"Error reading file: {e}"

    total_rows = len(rows)
    preview_rows = rows[:21]  # header + up to 20 data rows

    # Build a readable table
    lines = [f"File: {file_path}  |  {total_rows} rows  |  {len(headers)} columns"]
    lines.append(f"Columns: {', '.join(headers)}")
    lines.append("")

    for row in preview_rows:
        lines.append("\t".join(row))

    if total_rows > 21:
        lines.append(f"\n... ({total_rows - 21} more rows not shown)")

    return "\n".join(lines)


def write_spreadsheet(input: str) -> str:
    """Create a CSV or Excel file in the sandbox directory.
    Input must be a JSON string with keys:
      - 'filename': e.g. 'output.csv' or 'report.xlsx'
      - 'headers': list of column names, e.g. ["Name", "Age", "City"]
      - 'rows': list of lists, e.g. [["Alice", "30", "NYC"], ["Bob", "25", "LA"]]
    Example: {"filename": "people.csv", "headers": ["Name", "Age"], "rows": [["Alice", "30"], ["Bob", "25"]]}
    """
    try:
        data = json.loads(input)
    except json.JSONDecodeError as e:
        return f"Error: input must be valid JSON. {e}"

    filename = data.get("filename", "output.csv")
    headers = data.get("headers", [])
    rows = data.get("rows", [])

    os.makedirs("sandbox", exist_ok=True)
    full_path = os.path.join("sandbox", filename)
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext == ".csv":
            with open(full_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if headers:
                    writer.writerow(headers)
                writer.writerows(rows)
        elif ext in (".xlsx", ".xls"):
            wb = openpyxl.Workbook()
            ws = wb.active
            if headers:
                ws.append(headers)
            for row in rows:
                ws.append(row)
            wb.save(full_path)
        else:
            return f"Error: unsupported file type '{ext}'. Use .csv or .xlsx."
    except Exception as e:
        return f"Error writing file: {e}"

    return f"Spreadsheet successfully created at sandbox/{filename} ({len(rows)} data rows)"


def chart_data(input: str) -> str:
    """Generate a PNG chart from data and save it to the sandbox directory.
    Input must be a JSON string with keys:
      - 'filename': output filename, e.g. 'chart.png'
      - 'chart_type': one of 'bar', 'line', 'pie', 'scatter'
      - 'title': chart title (optional)
      - 'x_label': x-axis label (optional)
      - 'y_label': y-axis label (optional)
      - 'labels': list of labels for x-axis or pie slices, e.g. ["Q1", "Q2", "Q3"]
      - 'datasets': list of dataset objects, each with:
          - 'label': legend label (optional)
          - 'values': list of numbers
    Example: {"filename": "sales.png", "chart_type": "bar", "title": "Sales", "labels": ["Q1","Q2","Q3"], "datasets": [{"label": "Revenue", "values": [100,200,150]}]}
    """
    try:
        data = json.loads(input)
    except json.JSONDecodeError as e:
        return f"Error: input must be valid JSON. {e}"

    filename = data.get("filename", "chart.png")
    chart_type = data.get("chart_type", "bar")
    title = data.get("title", "")
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")
    labels = data.get("labels", [])
    datasets = data.get("datasets", [])

    if not datasets:
        return "Error: 'datasets' must contain at least one dataset with 'values'."

    os.makedirs("sandbox", exist_ok=True)
    full_path = os.path.join("sandbox", filename)

    try:
        fig, ax = plt.subplots(figsize=(10, 6))

        if chart_type == "pie":
            values = datasets[0].get("values", [])
            ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
        elif chart_type == "scatter":
            for ds in datasets:
                values = ds.get("values", [])
                x = list(range(len(values))) if not labels else list(range(len(values)))
                ax.scatter(x, values, label=ds.get("label", ""))
            if labels:
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, rotation=45, ha="right")
        elif chart_type == "line":
            for ds in datasets:
                values = ds.get("values", [])
                x = list(range(len(values)))
                ax.plot(x, values, marker="o", label=ds.get("label", ""))
            if labels:
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, rotation=45, ha="right")
        else:  # bar
            import numpy as np
            x = np.arange(len(labels)) if labels else np.arange(len(datasets[0].get("values", [])))
            width = 0.8 / len(datasets)
            for i, ds in enumerate(datasets):
                values = ds.get("values", [])
                offset = (i - len(datasets) / 2 + 0.5) * width
                ax.bar(x + offset, values, width, label=ds.get("label", ""))
            if labels:
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=45, ha="right")

        if title:
            ax.set_title(title)
        if x_label:
            ax.set_xlabel(x_label)
        if y_label:
            ax.set_ylabel(y_label)
        if any(ds.get("label") for ds in datasets) and chart_type != "pie":
            ax.legend()

        plt.tight_layout()
        fig.savefig(full_path, dpi=150)
        plt.close(fig)
    except Exception as e:
        return f"Error creating chart: {e}"

    return f"Chart successfully saved at sandbox/{filename}"


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

    read_spreadsheet_tool = Tool(
        name="read_spreadsheet",
        func=read_spreadsheet,
        description=(
            "Read a CSV or Excel (.xlsx) file from the sandbox directory and return a summary with column names and the first rows. "
            "Pass the file path relative to the sandbox folder (e.g. 'data.csv' or 'report.xlsx')."
        ),
    )

    write_spreadsheet_tool = Tool(
        name="write_spreadsheet",
        func=write_spreadsheet,
        description=(
            "Create a CSV or Excel (.xlsx) file in the sandbox directory. "
            "Input must be a JSON string with keys: 'filename' (e.g. 'output.csv'), "
            "'headers' (list of column names), and 'rows' (list of lists). "
            'Example: {"filename": "people.csv", "headers": ["Name", "Age"], "rows": [["Alice", "30"], ["Bob", "25"]]}'
        ),
    )

    chart_data_tool = Tool(
        name="chart_data",
        func=chart_data,
        description=(
            "Generate a PNG chart (bar, line, pie, or scatter) from data and save it to the sandbox directory. "
            "Input must be a JSON string with keys: 'filename', 'chart_type' (bar/line/pie/scatter), "
            "'title' (optional), 'x_label'/'y_label' (optional), 'labels' (list), "
            "and 'datasets' (list of objects with 'label' and 'values'). "
            'Example: {"filename": "sales.png", "chart_type": "bar", "title": "Sales", "labels": ["Q1","Q2"], "datasets": [{"label": "Revenue", "values": [100,200]}]}'
        ),
    )

    return file_tools + [push_tool, tool_search, python_repl, wiki_tool, arxiv_tool, pdf_tool, youtube_tool, create_pdf_tool, read_spreadsheet_tool, write_spreadsheet_tool, chart_data_tool]

