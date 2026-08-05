import logging
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen

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




# checking if this current pod has the lease to control, or creating the lease
def try_acquire_or_renew_lease() -> bool:
    LEASE_NAME = "controller"
    LEASE_DURATION_SECONDS = 15
    POD_NAME = os.environ["POD_NAME"]
    POD_NAMESPACE = os.getenv("POD_NAMESPACE", "default")
    config.load_incluster_config()
    coordination_api = client.CoordinationV1Api()

    now = datetime.now(timezone.utc)

    try:
        # find existing lease
        lease = coordination_api.read_namespaced_lease(
            name=LEASE_NAME,
            namespace=POD_NAMESPACE,
        )
    except ApiException as exc:
        # 404: lease doesn't exist yet. other error would be unexpected
        if exc.status != 404:
            raise
        # create lease
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
            # lease now exists in this pod and we are good
            coordination_api.create_namespaced_lease(
                namespace=POD_NAMESPACE,
                body=lease,
            )
            return True
        except ApiException as create_exc:
            # 409 is Conflict. this is here if both pods do this at the same time
            if create_exc.status == 409:
                return False
            raise

    # get existing lease info. we will update this info
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
        # holder was other pod, now this pod takes over
        spec.holder_identity = POD_NAME
        spec.acquire_time = now
        spec.renew_time = now
        spec.lease_duration_seconds = LEASE_DURATION_SECONDS
        spec.lease_transitions = (spec.lease_transitions or 0) + 1
    else:
        # other pod has valid lease
        return False

    try:
        # actually update lease now
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

            # for general liveness check of this given pod
            with open(LOG_FILE, "w", encoding="utf-8") as file:
                file.write(now)

            if try_acquire_or_renew_lease():
                logging.info("active controller: %s", now)
                # this is where controller actions would go for true system
            else:
                logging.info("not active: %s", now)

            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logging.info("program stopped")


if __name__ == "__main__":
    main()
