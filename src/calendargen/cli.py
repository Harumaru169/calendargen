"""Command-line interface for CalendarGen."""

import argparse
from pathlib import Path

from .schedule import TEMPLATE, generate_calendar, load_schedule


def main() -> None:
    parser = argparse.ArgumentParser(prog="calendargen")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a sample TOML schedule")
    init.add_argument("path", type=Path, nargs="?", default=Path("calendar.toml"))

    gen = commands.add_parser("gen", help="generate an ICS file")
    gen.add_argument("toml_path", type=Path)
    gen.add_argument("ics_path", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "init":
            with args.path.open("x", encoding="utf-8") as file:
                file.write(TEMPLATE)
        else:
            schedule = load_schedule(args.toml_path)
            args.ics_path.write_bytes(generate_calendar(schedule, args.toml_path))
    except (OSError, ValueError) as error:
        parser.error(str(error))
