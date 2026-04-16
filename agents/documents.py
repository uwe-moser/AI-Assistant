"""Documents agent: file management, PDFs, spreadsheets, charts."""

from agents.base import BaseAgent


class DocumentsAgent(BaseAgent):
    system_prompt = (
        "You are a document and file specialist. Read, write, and manage "
        "files in the sandbox directory. Create PDFs, work with spreadsheets "
        "(CSV/Excel), and generate charts."
    )
