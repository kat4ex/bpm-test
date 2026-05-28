import httpx
from playwright.sync_api import sync_playwright
from pathlib import Path
import json, time

class BpmSession:
    def __init__(self, base_url, username, password, cache_file="session.json"):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.cache_file = Path(cache_file)
        self._client = None
        self._expires_at = 0

    def _login_via_playwright(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(http_credentials={
                "username": self.username,
                "password": self.password,
            })
            page = context.new_page()
            page.goto(f"{self.base_url}/0/Main.aspx", wait_until="networkidle")
            # дождаться, что мы вернулись с ADFS на BPMSoft
            page.wait_for_url(f"{self.base_url}/**", timeout=30000)
            cookies = context.cookies()
            browser.close()
        
        cookie_dict = {c['name']: c['value'] for c in cookies}
        # кешируем
        self.cache_file.write_text(json.dumps({
            "cookies": cookie_dict,
            "saved_at": time.time(),
        }))
        return cookie_dict

    def _load_cached(self):
        if not self.cache_file.exists():
            return None
        data = json.loads(self.cache_file.read_text())
        # cookies из ADFS обычно живут 8 часов, берём с запасом
        if time.time() - data["saved_at"] > 6 * 3600:
            return None
        return data["cookies"]

    def _build_client(self, cookies):
        client = httpx.Client(
            base_url=self.base_url,
            cookies=cookies,
            headers={"BPMCSRF": cookies.get("BPMCSRF", "")},
            timeout=30.0,
        )
        return client

    def get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        cookies = self._load_cached() or self._login_via_playwright()
        self._client = self._build_client(cookies)
        return self._client

    def request(self, method, url, **kwargs):
        """Обёртка с авто-перелогином при 401."""
        client = self.get_client()
        r = client.request(method, url, **kwargs)
        if r.status_code in (401, 403):
            # сессия протухла — перелогиниваемся
            cookies = self._login_via_playwright()
            self._client = self._build_client(cookies)
            r = self._client.request(method, url, **kwargs)
        return r