import httpx
from playwright.sync_api import sync_playwright
from pathlib import Path
import json, time


class BpmSession:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        cache_file: str = "session.json",
        headless: bool = True,
        extra_args: list[str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.cache_file = Path(cache_file)
        self.headless = headless
        self.extra_args = extra_args or []
        self._client: httpx.Client | None = None
        self._cookies: dict = {}

    @property
    def cookies(self) -> dict:
        return self._cookies

    def _login_via_playwright(self) -> dict:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"] + self.extra_args,
            )
            context = browser.new_context(http_credentials={
                "username": self.username,
                "password": self.password,
            })
            page = context.new_page()
            page.goto(f"{self.base_url}/0/Main.aspx", wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_url(f"{self.base_url}/**", timeout=90_000)
            self._last_url = page.url
            cookies = context.cookies()
            browser.close()

        cookie_dict = {c["name"]: c["value"] for c in cookies}
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps({
            "cookies": cookie_dict,
            "saved_at": time.time(),
        }))
        return cookie_dict

    def _load_cached(self) -> dict | None:
        if not self.cache_file.exists():
            return None
        try:
            data = json.loads(self.cache_file.read_text())
        except (json.JSONDecodeError, KeyError):
            return None
        if time.time() - data["saved_at"] > 6 * 3600:
            return None
        return data["cookies"]

    def _build_client(self, cookies: dict) -> httpx.Client:
        self._cookies = cookies
        return httpx.Client(
            base_url=self.base_url,
            cookies=cookies,
            headers={"BPMCSRF": cookies.get("BPMCSRF", "")},
            timeout=90.0,
        )

    def get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        cookies = self._load_cached() or self._login_via_playwright()
        self._client = self._build_client(cookies)
        return self._client

    def request(self, method: str, url: str, **kwargs):
        """Обёртка с авто-перелогином при 401/403."""
        client = self.get_client()
        r = client.request(method, url, **kwargs)
        if r.status_code in (401, 403):
            cookies = self._login_via_playwright()
            self._client = self._build_client(cookies)
            r = self._client.request(method, url, **kwargs)
        return r
