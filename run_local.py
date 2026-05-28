import os
import getpass
import httpx
from session import BpmSession

BPM_URL = os.environ.get("BPM_URL", "https://your-bpm-instance.example.com")
BPM_USER = os.environ.get("BPM_USER", "DOMAIN\\username")
BPM_PASS = os.environ.get("BPM_PASS") or getpass.getpass(f"Password for {BPM_USER}: ")
CACHE_FILE = "session_cache/session.json"


def smoke_test(client: httpx.Client):
    print("\n[smoke] GET /0/odata/$metadata ...")
    r = client.get("/0/odata/$metadata")
    print(f"[smoke] Статус: {r.status_code}")
    if r.status_code == 200:
        print("[smoke] OK — сессия рабочая")
    else:
        print(f"[smoke] ОШИБКА — тело ответа:\n{r.text[:500]}")


if __name__ == "__main__":
    print(f"[login] Подключаюсь к {BPM_URL} (headless=False)...")
    session = BpmSession(BPM_URL, BPM_USER, BPM_PASS, cache_file=CACHE_FILE, headless=False)
    client = session.get_client()

    print(f"[login] Финальный URL: {session._last_url}")
    print(f"[login] Получено cookies: {list(session.cookies.keys())}")
    for required in (".ASPXAUTH", "BPMCSRF"):
        if required not in session.cookies:
            print(f"[login] ВНИМАНИЕ: cookie {required!r} отсутствует — логин мог не пройти")

    smoke_test(client)
