"""Browser agent: Playwright-based web navigation and interaction."""

from agents.base import BaseAgent
from tools.browser import playwright_tools


class BrowserAgent(BaseAgent):
    system_prompt = (
        "You are a browser automation specialist. Navigate websites, "
        "click links, fill forms, take screenshots, and extract content "
        "from web pages using a real browser."
    )

    def __init__(self, tools):
        super().__init__(tools)
        self.browser = None
        self.playwright = None

    @classmethod
    async def create(cls):
        """Factory that launches the browser and returns a ready agent."""
        tools, browser, playwright = await playwright_tools()
        agent = cls(tools)
        agent.browser = browser
        agent.playwright = playwright
        return agent

    async def cleanup(self):
        """Close the browser and stop Playwright."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
