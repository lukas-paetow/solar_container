import logging
import time
from pathlib import Path

from datetime import datetime, timezone
from urllib.request import urlopen

LOG_FILE = "/tmp/heartbeat.log"
INTERVAL_SECONDS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    handlers=[logging.StreamHandler()],
    force=True,
)


def main() -> None:
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    try:
        while True:

            timestamp = datetime.now().isoformat()

            with open(LOG_FILE, "w", encoding="utf-8") as file:
                file.write(timestamp)

            logging.info("watchdog heartbeat: %s", timestamp)
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logging.info("program stopped")


if __name__ == "__main__":
    main()
