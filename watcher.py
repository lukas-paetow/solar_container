from datetime import datetime, timezone
from urllib.request import urlopen
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

# for internal testing on one machine: http://host.docker.internal:port
HEARTBEAT_URL = "http://192.168.0.24:8000/heartbeat.log"

MAX_AGE_SECONDS = 15
FAILURES_BEFORE_TAKEOVER = 5
CHECK_INTERVAL_SECONDS = 5

def check_heartbeat():
    try:
        with urlopen(HEARTBEAT_URL, timeout=3) as response:
            lines = response.read().decode().splitlines()
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        if not non_empty_lines:
            raise ValueError("Heartbeat file is empty")

        timestamp_text = non_empty_lines[-1]
        heartbeat_time = datetime.fromisoformat(timestamp_text)
        age = (datetime.now() - heartbeat_time).total_seconds()
        logging.info("Controller is alive: heartbeat age %.1f seconds", age)
        return age <= MAX_AGE_SECONDS 

    except Exception as error:
        logging.error("Cannot reach controller: %s", error)
        return False

def main() -> None:
    failures = 0

    while True:

        if check_heartbeat():
            failures = 0
        else:
            failures += 1
            logging.warning("Failed heartbeat check %d/%d",failures,FAILURES_BEFORE_TAKEOVER,)


        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main() 
