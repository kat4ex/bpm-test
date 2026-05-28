import os
import json
import getpass
import argparse
from pathlib import Path
import httpx
from session import BpmSession

SMOKE_URL = "/0/dataservice/json/reply/SelectQuery"
BODY_FILE = Path("body.json")

BPM_URL = os.environ.get("BPM_URL", "https://your-bpm-instance.example.com")
BPM_USER = os.environ.get("BPM_USER", "DOMAIN\\username")
BPM_PASS = os.environ.get("BPM_PASS") or getpass.getpass(f"Password for {BPM_USER}: ")
BPM_SSL_VERIFY = os.environ.get("BPM_SSL_VERIFY", "false").lower() not in ("0", "false", "no")
CACHE_FILE = "session_cache/session.json"


def smoke_test(client: httpx.Client):
    if not BODY_FILE.exists():
        print(f"[smoke] ПРОПУСК: {BODY_FILE} не найден")
        return

    body = json.loads(BODY_FILE.read_text(encoding="utf-8"))
    print(f"\n[smoke] POST {SMOKE_URL} ...")
    r = client.post(SMOKE_URL, json=body)
    print(f"[smoke] Статус: {r.status_code}")
    if r.status_code == 200:
        print(f"[smoke] OK:\n{r.text[:500]}")
    else:
        print(f"[smoke] ОШИБКА:\n{r.text[:500]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-kerberos",
        action="store_true",
        help="Disable Negotiate/Kerberos SSO to test credentials explicitly (simulates Docker)",
    )
    args = parser.parse_args()

    extra_args = ["--auth-server-allowlist="] if args.no_kerberos else []
    if args.no_kerberos:
        print("[login] Режим --no-kerberos: Kerberos/Negotiate отключён, используются явные креды")

    print(f"[login] Подключаюсь к {BPM_URL} (headless=False)...")
    session = BpmSession(BPM_URL, BPM_USER, BPM_PASS, cache_file=CACHE_FILE, headless=False, extra_args=extra_args, verify=BPM_SSL_VERIFY)
    client = session.get_client()

    print(f"[login] Финальный URL: {session._last_url}")
    print(f"[login] Получено cookies: {list(session.cookies.keys())}")
    for required in (".ASPXAUTH", "BPMCSRF"):
        if required not in session.cookies:
            print(f"[login] ВНИМАНИЕ: cookie {required!r} отсутствует — логин мог не пройти")

    smoke_test(client)
