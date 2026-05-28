import os
import json
from pathlib import Path
import httpx
from session import BpmSession

QUERY_URL = "/0/dataservice/json/reply/SelectQuery"
BODY_FILE = Path("body.json")


def fetch(client: httpx.Client) -> dict:
    body = json.loads(BODY_FILE.read_text(encoding="utf-8"))
    r = client.post(QUERY_URL, json=body)
    r.raise_for_status()
    return r.json()


def main():
    ssl_verify = os.environ.get("BPM_SSL_VERIFY", "true").lower() not in ("0", "false", "no")
    session = BpmSession(
        os.environ["BPM_URL"],
        os.environ["BPM_USER"],
        os.environ["BPM_PASS"],
        cache_file="/app/session_cache/session.json",
        verify=ssl_verify,
    )
    client = session.get_client()
    result = fetch(client)
    print(result)


if __name__ == "__main__":
    main()
