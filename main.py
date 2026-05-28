import os
from session import BpmSession


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
    # TODO: парсер


if __name__ == "__main__":
    main()
