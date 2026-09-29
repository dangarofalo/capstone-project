"""SentinelView collection agent.

Reads new security events from this computer and sends them to the SentinelView server.
Uses only the Python standard library so it is easy to install on any machine.

    python sentinel_agent.py --config config.json          # run continuously
    python sentinel_agent.py --config config.json --once   # one collection, then exit
"""
import argparse
import json
import logging
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from collectors import get_collector

BATCH_SIZE = 500
log = logging.getLogger("sentinel-agent")


def load_config(path: str) -> dict:
    # utf-8-sig also accepts files saved with a BOM (Notepad and PowerShell often add one).
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    for key in ("server_url", "api_key"):
        if not config.get(key) or "PASTE" in config[key]:
            raise SystemExit(f"config: '{key}' is missing. See config.example.json.")
    return config


def send_batch(config: dict, events: list[dict]) -> dict:
    payload = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "events": events,
    }
    request = urllib.request.Request(
        config["server_url"].rstrip("/") + "/api/ingest/events",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": config["api_key"]},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def run_once(config: dict, collector) -> None:
    events = collector.collect()
    # Always send at least one (possibly empty) batch so the server knows we're alive.
    chunks = [events[i : i + BATCH_SIZE] for i in range(0, len(events), BATCH_SIZE)] or [[]]
    accepted = duplicates = 0
    for chunk in chunks:
        result = send_batch(config, chunk)
        accepted += result["accepted"]
        duplicates += result["duplicates"]
    # Only move the checkpoint forward once the server has everything.
    collector.commit()
    log.info("Sent %d events (%d new, %d already stored)", len(events), accepted, duplicates)


def main() -> int:
    parser = argparse.ArgumentParser(description="SentinelView collection agent")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--once", action="store_true", help="collect and send once, then exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    collector = get_collector(config)
    interval = int(config.get("interval_seconds", 30))
    log.info("Agent started (source=%s, server=%s)", config.get("source", "windows"), config["server_url"])

    while True:
        try:
            run_once(config, collector)
        except PermissionError as e:
            log.error("%s", e)
            return 1
        except urllib.error.HTTPError as e:
            if e.code == 401:
                log.error("Server rejected the API key. Check api_key in your config.")
                return 1
            log.warning("Server error %s; will retry in %ss", e.code, interval)
        except (urllib.error.URLError, OSError) as e:
            # Checkpoint was not saved, so these events will be re-sent next time.
            log.warning("Could not reach server (%s); will retry in %ss", e, interval)
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
