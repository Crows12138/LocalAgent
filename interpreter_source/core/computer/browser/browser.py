import threading
import time
import platform

import html2text
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class Browser:
    """
    Browser automation using Selenium WebDriver.

    Supports multiple browsers: chrome, edge, firefox

    Usage:
        browser = interpreter.computer.browser
        browser.browser_type = "edge"  # Use Edge instead of Chrome
        browser.go_to_url("https://example.com")
    """

    # Supported browsers
    CHROME = "chrome"
    EDGE = "edge"
    FIREFOX = "firefox"

    def __init__(self, computer):
        self.computer = computer
        self._driver = None
        self._browser_type = "edge"  # Default to Edge on Windows
        self._headless = False
        self._use_profile = False  # Use user's browser profile (with login sessions)

    @property
    def browser_type(self):
        """Get current browser type."""
        return self._browser_type

    @browser_type.setter
    def browser_type(self, value):
        """
        Set browser type. Options: 'chrome', 'edge', 'firefox'
        If driver is already running, it will be restarted on next use.
        """
        if value.lower() not in [self.CHROME, self.EDGE, self.FIREFOX]:
            raise ValueError(f"Unsupported browser: {value}. Use 'chrome', 'edge', or 'firefox'")
        if self._driver is not None:
            self.quit()
            self._driver = None
        self._browser_type = value.lower()

    @property
    def use_profile(self):
        """Whether to use user's browser profile (with login sessions)."""
        return self._use_profile

    @use_profile.setter
    def use_profile(self, value):
        """
        Set whether to use user's browser profile.

        When True, the browser will use your existing profile with:
        - Saved logins and passwords
        - Cookies and sessions
        - Extensions
        - Bookmarks

        Note: You must close all other browser windows first!
        """
        if self._driver is not None:
            self.quit()
            self._driver = None
        self._use_profile = bool(value)

    @property
    def driver(self):
        if self._driver is None:
            self.setup(self._headless)
        return self._driver

    @driver.setter
    def driver(self, value):
        self._driver = value

    def search(self, query, max_results=5):
        """
        Searches the web using DuckDuckGo (free, no API key required).
        Returns formatted search results with title, link, and snippet.

        Requires: pip install ddgs
        """
        try:
            from ddgs import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        'title': r.get('title', ''),
                        'link': r.get('href', ''),
                        'snippet': r.get('body', '')
                    })

            if results:
                output = f"Search results for '{query}':\n\n"
                for i, r in enumerate(results, 1):
                    output += f"{i}. {r['title']}\n"
                    output += f"   URL: {r['link']}\n"
                    output += f"   {r['snippet']}\n\n"
                return output
            else:
                return f"No results found for '{query}'"

        except ImportError:
            return "Error: ddgs not installed. Run: pip install ddgs"
        except Exception as e:
            return f"Search failed: {str(e)}"

    def fast_search(self, query):
        """
        Alias for search() - DuckDuckGo search is already fast.
        """
        return self.search(query)

    def setup(self, headless=False):
        """
        Setup the browser driver.

        Args:
            headless: Run browser without UI (background mode)
        """
        self._headless = headless

        try:
            if self._browser_type == self.EDGE:
                self._setup_edge(headless)
            elif self._browser_type == self.CHROME:
                self._setup_chrome(headless)
            elif self._browser_type == self.FIREFOX:
                self._setup_firefox(headless)
            else:
                raise ValueError(f"Unknown browser type: {self._browser_type}")

            print(f"Browser started: {self._browser_type}")

        except Exception as e:
            print(f"Failed to start {self._browser_type}: {e}")
            print("Tip: Make sure the browser is installed and webdriver-manager is up to date")
            self._driver = None

    def _setup_edge(self, headless):
        """Setup Microsoft Edge browser."""
        import os
        options = webdriver.EdgeOptions()

        if headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # Use user's profile if requested (includes logins, cookies, etc.)
        if self._use_profile:
            user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
            if os.path.exists(user_data_dir):
                options.add_argument(f"--user-data-dir={user_data_dir}")
                options.add_argument("--profile-directory=Default")
                print(f"Using Edge profile: {user_data_dir}")
            else:
                print(f"Warning: Edge profile not found at {user_data_dir}")

        # Try system driver first (no network needed)
        try:
            self._driver = webdriver.Edge(options=options)
            return
        except Exception:
            pass

        # Fallback to webdriver-manager (needs network)
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        service = EdgeService(EdgeChromiumDriverManager().install())
        self._driver = webdriver.Edge(service=service, options=options)

    def _setup_chrome(self, headless):
        """Setup Google Chrome browser."""
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        service = ChromeService(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=options)

    def _setup_firefox(self, headless):
        """Setup Mozilla Firefox browser."""
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager

        options = webdriver.FirefoxOptions()
        if headless:
            options.add_argument("--headless")

        service = FirefoxService(GeckoDriverManager().install())
        self._driver = webdriver.Firefox(service=service, options=options)

    def go_to_url(self, url):
        """Navigate to a URL"""
        self.driver.get(url)
        time.sleep(1)

    def search_google(self, query, delays=True):
        """Perform a Google search"""
        self.driver.get("https://www.perplexity.ai")
        # search_box = self.driver.find_element(By.NAME, 'q')
        # search_box.send_keys(query)
        # search_box.send_keys(Keys.RETURN)
        body = self.driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.COMMAND + "k")
        time.sleep(0.5)
        active_element = self.driver.switch_to.active_element
        active_element.send_keys(query)
        active_element.send_keys(Keys.RETURN)
        if delays:
            time.sleep(3)

    def analyze_page(self, intent):
        """
        Extract HTML, list interactive elements, and analyze with AI.
        Uses the currently configured model (works with local models like Qwen).
        """
        html_content = self.driver.page_source
        text_content = html2text.html2text(html_content)

        # Truncate content if too long (for smaller context windows)
        max_content_len = 8000
        if len(text_content) > max_content_len:
            text_content = text_content[:max_content_len] + "\n...[truncated]"

        elements = (
            self.driver.find_elements(By.TAG_NAME, "a")
            + self.driver.find_elements(By.TAG_NAME, "button")
            + self.driver.find_elements(By.TAG_NAME, "input")
            + self.driver.find_elements(By.TAG_NAME, "select")
        )

        # Limit elements to avoid context overflow
        elements_info = []
        for idx, elem in enumerate(elements[:50]):  # Max 50 elements
            text = elem.text.strip()
            if text:  # Only include elements with text
                elements_info.append({
                    "id": idx,
                    "text": text[:100],  # Truncate long text
                    "tag": elem.tag_name,
                })

        ai_query = f"""Analyze this webpage for the intent: "{intent}"

Page Content (truncated):
{text_content}

Interactive Elements (id, tag, text):
{elements_info}

Instructions:
1. If the requested information is on the page, return it directly
2. Otherwise, list the top 5 most relevant interactive elements with their ID and suggested action
3. Be concise"""

        # Use current model (no switching) - works with local models
        response = self.computer.ai.chat(ai_query)

        print(response)
        print(
            "\nUse the element IDs above to interact with the page."
        )

    def click_element(self, element_id):
        """
        Click an interactive element by its ID (from analyze_page output).

        Args:
            element_id: The numeric ID from analyze_page results
        """
        elements = (
            self.driver.find_elements(By.TAG_NAME, "a")
            + self.driver.find_elements(By.TAG_NAME, "button")
            + self.driver.find_elements(By.TAG_NAME, "input")
            + self.driver.find_elements(By.TAG_NAME, "select")
        )

        if 0 <= element_id < len(elements):
            elements[element_id].click()
            time.sleep(1)
            return f"Clicked element {element_id}"
        else:
            return f"Element {element_id} not found (max: {len(elements)-1})"

    def type_text(self, element_id, text):
        """
        Type text into an input element.

        Args:
            element_id: The numeric ID from analyze_page results
            text: Text to type
        """
        elements = (
            self.driver.find_elements(By.TAG_NAME, "a")
            + self.driver.find_elements(By.TAG_NAME, "button")
            + self.driver.find_elements(By.TAG_NAME, "input")
            + self.driver.find_elements(By.TAG_NAME, "select")
        )

        if 0 <= element_id < len(elements):
            elements[element_id].clear()
            elements[element_id].send_keys(text)
            return f"Typed '{text}' into element {element_id}"
        else:
            return f"Element {element_id} not found"

    def get_page_text(self):
        """
        Get the text content of the current page (no AI analysis).
        Useful for quick content extraction.
        """
        html_content = self.driver.page_source
        text_content = html2text.html2text(html_content)
        return text_content

    def screenshot(self, path=None):
        """
        Take a screenshot of the current page.

        Args:
            path: Optional path to save. If None, returns base64.
        """
        if path:
            self.driver.save_screenshot(path)
            return f"Screenshot saved to {path}"
        else:
            return self.driver.get_screenshot_as_base64()

    def quit(self):
        """Close the browser"""
        self.driver.quit()
