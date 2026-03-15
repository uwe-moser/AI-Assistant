"""Research tools: web search, Wikipedia, arXiv, YouTube transcripts."""

from langchain_core.tools import Tool
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from youtube_transcript_api import YouTubeTranscriptApi


_serper = None


def _get_serper():
    global _serper
    if _serper is None:
        _serper = GoogleSerperAPIWrapper()
    return _serper


def search(query: str) -> str:
    """Search the web using Google."""
    return _get_serper().run(query)


def get_youtube_transcript(url_or_id: str) -> str:
    """Get the transcript of a YouTube video given its URL or video ID."""
    video_id = url_or_id.strip()
    for prefix in ["https://www.youtube.com/watch?v=", "https://youtube.com/watch?v=",
                    "https://youtu.be/", "https://m.youtube.com/watch?v="]:
        if video_id.startswith(prefix):
            video_id = video_id[len(prefix):].split("&")[0].split("?")[0]
            break
    ytt_api = YouTubeTranscriptApi()
    transcript = ytt_api.fetch(video_id)
    lines = [entry.text for entry in transcript.snippets]
    return "\n".join(lines)


def get_tools():
    """Return all research tools."""
    search_tool = Tool(
        name="search",
        func=search,
        description="Search the web using Google for up-to-date information.",
    )

    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)

    arxiv = ArxivAPIWrapper()
    arxiv_tool = ArxivQueryRun(api_wrapper=arxiv)

    youtube_tool = Tool(
        name="get_youtube_transcript",
        func=get_youtube_transcript,
        description="Get the transcript of a YouTube video. Pass a YouTube URL or video ID.",
    )

    return [search_tool, wiki_tool, arxiv_tool, youtube_tool]
