from datetime import datetime, timezone
from urllib.request import urlopen
import time
import logging
import os
import shlex
import subprocess
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)


load_dotenv()

NODE_ID = os.environ["NODE_ID"]
HEARTBEAT_URL = os.environ["HEARTBEAT_URL"]
REMOTE_SSH_HOST = os.environ["REMOTE_SSH_HOST"]
SSH_KEY = os.environ["SSH_KEY"]
PROJECT_DIR = os.environ["PROJECT_DIR"]
DIR_THIS_MACHINE = os.environ["DIR_THIS_MACHINE"]
SSH_USER = "lukas"



# for internal testing on one machine: http://host.docker.internal:port
#HEARTBEAT_URL = "http://192.168.0.24:8000/heartbeat.log"
#HEARTBEAT_URL = "http://192.168.0.22:8000/heartbeat.log" # pc address # 


MAX_AGE_SECONDS = 15
FAILURES_BEFORE_TAKEOVER = 2
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

def prep_command(command: str) -> str:
    return f"cd {shlex.quote(PROJECT_DIR)} && {command}" # weird characters in path would break manual quotes



def ssh_command(host: str, command: str) -> subprocess.CompletedProcess[str]:
    # returns an object with result of command

    logging.info("SSH %s: %s", host, command)
    return subprocess.run(
        [                 
            "ssh",
            "-i", SSH_KEY, # key specific to me
            "-o", "IdentitiesOnly=yes",
            "-o", "BatchMode=yes", # no interaction prompts
            "-o", "ConnectTimeout=5",
            "-o", "StrictHostKeyChecking=accept-new", # avoid first-time prompt
            f"{SSH_USER}@{host}",
            command,
        ],  
        text=True, # convert any outputs into text we can use
        capture_output=True, # don't print in terminal, capture it for us
    )



def start_local_controller():
    subprocess.run(
        ["docker", "compose", "--profile", "controller", "up", "-d", "controller", "heartbeat-server"],
        check=True,
        cwd=DIR_THIS_MACHINE, 
    )


def takeover():
    # stop controller on other
    # start controller here
    # start watcher on other
    # stop this watcher. should happen automatically


    logging.warning("Starting takeover")

    # stop controller on other machine
    remote_stop = ssh_command(
        REMOTE_SSH_HOST,
        prep_command("docker compose stop controller heartbeat-server"),
    )
    logging.warning(remote_stop) # might remove this additional output


    # end takeover here if host reachable but controller can't be stopped
    remote_reachable = remote_stop.returncode != 255
    if remote_reachable and remote_stop.returncode != 0:
        logging.error("Remote host was reachable, but its controller could not be stopped: %s",
                      remote_stop.stderr.strip())
        return False

    start_local_controller()

     
    if remote_reachable:
        remote_watcher = ssh_command(
            REMOTE_SSH_HOST,
            prep_command("nohup python watcher.py > watcher.log 2>&1 < /dev/null &"), 
            # errors in log
        )
    else:
        logging.warning("Remote host is unreachable; proceeding with local takeover")


    logging.warning("Takeover completed")
    return True




def main() -> None:
    failures = 0

    while True:

        if check_heartbeat():
            failures = 0
        else:
            failures += 1
            logging.warning("Failed heartbeat check %d/%d",failures,FAILURES_BEFORE_TAKEOVER,)

            if failures >= FAILURES_BEFORE_TAKEOVER:
                takeover()
                return


        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main() 
