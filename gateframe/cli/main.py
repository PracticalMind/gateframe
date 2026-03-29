from __future__ import annotations

import argparse
import sys


def cli() -> None:
    parser = argparse.ArgumentParser(prog="gateframe", description="gateframe CLI")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="Introspect a contract file")
    inspect_parser.add_argument("contract_file", help="Path to a .py file containing contracts")

    replay_parser = subparsers.add_parser("replay", help="Replay an audit log")
    replay_parser.add_argument("audit_file", help="Path to a JSON/JSONL audit log file")

    args = parser.parse_args()

    if args.command == "inspect":
        from gateframe.cli.inspect import run_inspect

        run_inspect(args.contract_file)
    elif args.command == "replay":
        from gateframe.cli.replay import run_replay

        run_replay(args.audit_file)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    cli()
