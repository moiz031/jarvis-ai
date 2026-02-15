"""CLI helper for Jarvis Super Mode."""

from __future__ import annotations

import argparse
import json
import sys

import requests


def _print(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Jarvis Super CLI")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Jarvis API base URL")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Read persisted Super state")

    onboard = sub.add_parser("onboard", help="Run one-shot onboarding")
    onboard.add_argument("--profile", default="power", choices=["basic", "power", "admin"])
    onboard.add_argument("--users", default="local-admin", help="Comma-separated allowlist users")
    onboard.add_argument("--channels", default="", help="Comma-separated channels to connect")

    connect = sub.add_parser("connect", help="Connect channel")
    connect.add_argument("channel")
    connect.add_argument("--token", default="")

    disconnect = sub.add_parser("disconnect", help="Disconnect channel")
    disconnect.add_argument("channel")

    send = sub.add_parser("send", help="Send message to channel")
    send.add_argument("channel")
    send.add_argument("target")
    send.add_argument("text")
    send.add_argument("--user", default="local-admin")

    task = sub.add_parser("task", help="Dispatch super task")
    task.add_argument("text")
    task.add_argument("--user", default="local-admin")
    task.add_argument("--confirmed", action="store_true")

    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    try:
        if args.cmd == "status":
            res = requests.get(f"{base}/api/super/state", timeout=15)
            res.raise_for_status()
            _print(res.json())
            return 0

        if args.cmd == "onboard":
            users = [x.strip() for x in args.users.split(",") if x.strip()]
            channels = [x.strip() for x in args.channels.split(",") if x.strip()]
            payload = {
                "permission_profile": args.profile,
                "allowlist_users": users,
                "connect_channels": channels,
            }
            res = requests.post(f"{base}/api/super/onboard", json=payload, timeout=15)
            res.raise_for_status()
            _print(res.json())
            return 0

        if args.cmd == "connect":
            payload = {"channel": args.channel}
            if args.token:
                payload["token"] = args.token
            res = requests.post(f"{base}/api/super/channel/connect", json=payload, timeout=15)
            res.raise_for_status()
            _print(res.json())
            return 0

        if args.cmd == "disconnect":
            res = requests.post(f"{base}/api/super/channel/disconnect", json={"channel": args.channel}, timeout=15)
            res.raise_for_status()
            _print(res.json())
            return 0

        if args.cmd == "send":
            payload = {
                "channel": args.channel,
                "target": args.target,
                "text": args.text,
                "user_id": args.user,
            }
            res = requests.post(f"{base}/api/super/channel/send", json=payload, timeout=15)
            res.raise_for_status()
            _print(res.json())
            return 0

        if args.cmd == "task":
            payload = {
                "text": args.text,
                "source": "cli",
                "user_id": args.user,
                "metadata": {"confirmed": args.confirmed},
            }
            res = requests.post(f"{base}/api/super/task", json=payload, timeout=15)
            res.raise_for_status()
            _print(res.json())
            return 0

    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
