import logging
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen

# check if I really need these
import os
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

LOG_FILE = "/tmp/heartbeat.log"
INTERVAL_SECONDS = 5 # heartbeat write frequency

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    handlers=[logging.StreamHandler()],
    force=True,
)

LEASE_NAME = "controller"
LEASE_DURATION_SECONDS = 15

POD_NAME = os.environ["POD_NAME"]
POD_NAMESPACE = os.getenv("POD_NAMESPACE", "default")

config.load_incluster_config()
coordination_api = client.CoordinationV1Api()




def try_acquire_or_renew_lease() -> bool:
    now = datetime.now(timezone.utc)

    try:
        lease = coordination_api.read_namespaced_lease(
            name=LEASE_NAME,
            namespace=POD_NAMESPACE,
        )
    except ApiException as exc:
        if exc.status != 404:
            raise

        lease = client.V1Lease(
            metadata=client.V1ObjectMeta(name=LEASE_NAME),
            spec=client.V1LeaseSpec(
                holder_identity=POD_NAME,
                acquire_time=now,
                renew_time=now,
                lease_duration_seconds=LEASE_DURATION_SECONDS,
                lease_transitions=0,
            ),
        )

        try:
            coordination_api.create_namespaced_lease(
                namespace=POD_NAMESPACE,
                body=lease,
            )
            return True
        except ApiException as create_exc:
            if create_exc.status == 409:
                return False
            raise

    spec = lease.spec
    holder = spec.holder_identity
    renew_time = spec.renew_time
    duration = spec.lease_duration_seconds or LEASE_DURATION_SECONDS

    expired = (
        renew_time is None
        or now > renew_time + timedelta(seconds=duration)
    )

    if holder == POD_NAME:
        spec.renew_time = now

    elif expired:
        spec.holder_identity = POD_NAME
        spec.acquire_time = now
        spec.renew_time = now
        spec.lease_duration_seconds = LEASE_DURATION_SECONDS
        spec.lease_transitions = (spec.lease_transitions or 0) + 1

    else:
        return False

    try:
        coordination_api.replace_namespaced_lease(
            name=LEASE_NAME,
            namespace=POD_NAMESPACE,
            body=lease,
        )
        return True
    except ApiException as exc:
        if exc.status == 409:
            # The other Pod updated the Lease first.
            return False
        raise

# this would control the solar cells and batteries. currently just a placeholder that writes to a heartbeat file.
def main() -> None:
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            now = datetime.now().isoformat()
            if try_acquire_or_renew_lease():
                with open(LOG_FILE, "w", encoding="utf-8") as file:
                    file.write(now)

                logging.info("watchdog heartbeat: %s", now)
            else:
                logging.info("not active")
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logging.info("program stopped")


if __name__ == "__main__":
    main()
