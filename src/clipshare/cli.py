"""CLI entry point for Clipshare."""

import argparse
import sys

from .daemon import Daemon


def cmd_start(args: argparse.Namespace) -> None:
    daemon = Daemon()
    daemon.start()


def cmd_daemon(args: argparse.Namespace) -> None:
    """Run daemon in foreground (internal command)."""
    daemon = Daemon()
    daemon.run_daemon()


def cmd_list(args: argparse.Namespace) -> None:
    daemon = Daemon()
    daemon.list_devices()


def cmd_pair(args: argparse.Namespace) -> None:
    daemon = Daemon()
    daemon.pair(args.device_name)


def cmd_name(args: argparse.Namespace) -> None:
    daemon = Daemon()
    daemon.set_name(args.new_name)


def cmd_stop(args: argparse.Namespace) -> None:
    daemon = Daemon()
    daemon.stop_daemon()


def cmd_status(args: argparse.Namespace) -> None:
    daemon = Daemon()
    daemon.status()


def main() -> None:
    # Handle --daemon flag first (internal use)
    if "--daemon" in sys.argv:
        daemon = Daemon()
        daemon.run_daemon()
        return

    parser = argparse.ArgumentParser(
        prog="clipshare",
        description="LAN Clipboard Sync Tool - share clipboard across Windows and macOS",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start
    p_start = subparsers.add_parser("start", help="Start the sync daemon")
    p_start.set_defaults(func=cmd_start)

    # list
    p_list = subparsers.add_parser("list", help="List online devices")
    p_list.set_defaults(func=cmd_list)

    # pair
    p_pair = subparsers.add_parser("pair", help="Pair with a device")
    p_pair.add_argument("device_name", help="Target device name to pair with")
    p_pair.set_defaults(func=cmd_pair)

    # name
    p_name = subparsers.add_parser("name", help="Set local device name")
    p_name.add_argument("new_name", help="New device name")
    p_name.set_defaults(func=cmd_name)

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop the daemon")
    p_stop.set_defaults(func=cmd_stop)

    # status
    p_status = subparsers.add_parser("status", help="Show daemon status")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()