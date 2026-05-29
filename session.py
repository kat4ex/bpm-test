import ssl
import httpx
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime
import json, os, time


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


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
        kinit_realm: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.cache_file = Path(cache_file)
        self.headless = headless
        self.extra_args = extra_args or []
        self.verify = verify
        self.kinit_realm = kinit_realm
        self._client: httpx.Client | None = None
        self._cookies: dict = {}
        self._last_url: str = ""

    @property
    def cookies(self) -> dict:
        return self._cookies

    def _kinit(self) -> None:
        import krb5

        realm = self.kinit_realm
        kdc = os.environ.get("KRB5_KDC", "")
        krb5_conf = f"[libdefaults]\n    default_realm = {realm}\n    dns_lookup_kdc = true\n"
        if kdc:
            krb5_conf += f"\n[realms]\n    {realm} = {{\n        kdc = {kdc}\n    }}\n"
        Path("/etc/krb5.conf").write_text(krb5_conf)

        username = self.username
        if "\\" in username:
            _, user = username.split("\\", 1)
            username = f"{user}@{realm}"
        elif "@" not in username:
            username = f"{username}@{realm}"

        _log(f"kinit {username} ...")
        ctx = krb5.init_context()
        principal = krb5.parse_name_flags(ctx, username.encode())
        creds = krb5.get_init_creds_password(ctx, principal, self.password.encode())
        ccache = krb5.cc_default(ctx)
        krb5.cc_initialize(ctx, ccache, principal)
        krb5.cc_store_cred(ctx, ccache, creds)
        _log("Kerberos ticket получен")

    def _login_via_playwright(self) -> dict:
        if self.kinit_realm:
            self._kinit()
        _log("Запуск Chromium...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--auth-server-allowlist=*",
                ] + self.extra_args,
            )
            _log("Chromium запущен, создаю контекст...")
            context = browser.new_context(
                http_credentials={"username": self.username, "password": self.password},
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.on("framenavigated", lambda frame: (
                _log(f"nav → {frame.url}")
                if frame == page.main_frame else None
            ))
            page.on("request", lambda req: (
                _log(f"req → {req.method} {req.url[:120]}")
                if req.resource_type in ("xhr", "fetch", "document") else None
            ))
            page.on("response", lambda resp: (
                _log(f"res ← {resp.status} {resp.url[:120]}")
                if resp.request.resource_type in ("xhr", "fetch", "document") else None
            ))
            _log(f"Перехожу на {self.base_url}/0/Main.aspx ...")
            page.goto(f"{self.base_url}/0/Main.aspx", wait_until="domcontentloaded", timeout=90_000)

            _log("Жду редирект на /0/ ...")
            page.wait_for_url(f"{self.base_url}/0/**", timeout=90_000)
            self._last_url = page.url
            _log(f"Финальный URL: {self._last_url}")
            cookies = context.cookies()
            browser.close()
        _log(f"Получено cookies: {list({c['name'] for c in cookies})}")

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
