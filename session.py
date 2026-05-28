import ssl
import httpx
from playwright.sync_api import sync_playwright
from pathlib import Path
import json, time


def _make_ssl_context(verify: bool | str) -> ssl.SSLContext:
    if verify is False:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context()
        if isinstance(verify, str):
            ctx.load_verify_locations(cafile=verify)
    # OP_LEGACY_SERVER_CONNECT появился в Python 3.12, для 3.10 используем raw value
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return ctx


class BpmSession:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        cache_file: str = "session.json",
        headless: bool = True,
        extra_args: list[str] | None = None,
        verify: bool | str = True,
        trust_env: bool = False,
        ca_certs_dir: str | Path | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.cache_file = Path(cache_file)
        self.headless = headless
        self.extra_args = extra_args or []
        self.verify = verify
        self.trust_env = trust_env
        self.ca_certs_dir = Path(ca_certs_dir) if ca_certs_dir else None
        self._client: httpx.Client | None = None
        self._cookies: dict = {}
        self._last_url: str = ""

    @property
    def cookies(self) -> dict:
        return self._cookies

    def _load_ca_certs(self) -> list[dict]:
        if not self.ca_certs_dir or not self.ca_certs_dir.exists():
            return []
        certs = []
        for ext in ("*.crt", "*.pem", "*.cer"):
            for path in self.ca_certs_dir.glob(ext):
                certs.append({"cert": path.read_text()})
        return certs

    def _login_via_playwright(self) -> dict:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"] + self.extra_args,
            )
            ca_certificates = self._load_ca_certs()
            context = browser.new_context(
                http_credentials={"username": self.username, "password": self.password},
                ca_certificates=ca_certificates if ca_certificates else None,
                ignore_https_errors=not ca_certificates,
            )
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
            verify=_make_ssl_context(self.verify),
            trust_env=self.trust_env,
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
