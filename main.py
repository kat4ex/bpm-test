import os
from session import BpmSession


def main():
    session = BpmSession(
        os.environ["BPM_URL"],
        os.environ["BPM_USER"],
        os.environ["BPM_PASS"],
        cache_file="/app/session_cache/session.json",
    )
    client = session.get_client()
    # TODO: парсер


if __name__ == "__main__":
    main()
