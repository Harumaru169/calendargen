import io
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr
from datetime import date, time
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from icalendar import Calendar

from calendargen.cli import main
from calendargen.schedule import TEMPLATE, generate_calendar, load_schedule

SCHEDULE = """term_start = 2026-05-04
term_end = 2026-05-11
holidays = [2026-05-05]

[time_slots]
"period 1" = { start = "08:45", end = "10:15" }
"lunch" = { start = "12:00", end = "13:15" }
"2" = { start = "13:15", end = "14:45" }

[[courses]]
title = "Monday class"
description = "Professor Smith"
weekday = "mon"
time_slot = "period 1"
location = "A101"

[[courses]]
title = "Tuesday class"
weekday = "tue"
time_slot = "lunch"

[[courses]]
title = "Wednesday class"
weekday = "wed"
time_slot = "2"

[[day_overrides]]
date = 2026-05-06
use_weekday = "mon"
"""


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.toml_path = self.directory / "calendar.toml"
        self.toml_path.write_text(SCHEDULE, encoding="utf-8")

    def test_template_is_valid_toml(self):
        data = tomllib.loads(TEMPLATE)
        self.assertEqual(data["time_slots"]["period 1"]["start"], "08:45")
        self.assertIn("lunch", data["time_slots"])
        self.assertEqual(data["courses"][0]["description"], "Professor Tsujimoto")
        self.assertEqual(
            data["day_overrides"][0]["all_day_event_title"],
            "swapped to Monday schedule",
        )
        self.toml_path.write_text(TEMPLATE, encoding="utf-8")
        load_schedule(self.toml_path)

    @patch("calendargen.schedule.get_localzone", return_value=ZoneInfo("Asia/Tokyo"))
    def test_calendar_dates_overrides_and_timezone(self, _zone):
        calendar = Calendar.from_ical(
            generate_calendar(load_schedule(self.toml_path), self.toml_path)
        )
        events = list(calendar.walk("VEVENT"))
        self.assertEqual(len(events), 3)
        self.assertEqual(
            [event.decoded("DTSTART").date() for event in events],
            [date(2026, 5, 4), date(2026, 5, 6), date(2026, 5, 11)],
        )
        self.assertEqual(
            [str(event["SUMMARY"]) for event in events], ["Monday class"] * 3
        )
        self.assertEqual(events[1].decoded("DTSTART").time(), time(8, 45))
        self.assertEqual(events[1].decoded("DTEND").time(), time(10, 15))
        self.assertEqual(
            events[1].decoded("DTSTART").utcoffset().total_seconds(), 9 * 3600
        )
        self.assertEqual(len(list(calendar.walk("VTIMEZONE"))), 1)
        self.assertEqual(events[0]["LOCATION"], "A101")
        self.assertEqual(str(events[0]["DESCRIPTION"]), "Professor Smith")
        self.assertEqual(
            [event["UID"] for event in events],
            [
                event["UID"]
                for event in Calendar.from_ical(
                    generate_calendar(load_schedule(self.toml_path), self.toml_path)
                ).walk("VEVENT")
            ],
        )

    def test_holiday_and_override_collision_is_an_error(self):
        self.toml_path.write_text(
            SCHEDULE.replace("holidays = [2026-05-05]", "holidays = [2026-05-06]"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "both holidays and day_overrides"):
            load_schedule(self.toml_path)

    @patch("calendargen.schedule.get_localzone", return_value=ZoneInfo("Asia/Tokyo"))
    def test_all_day_event_title_adds_an_event_with_or_without_a_course(self, _zone):
        for weekday, event_count in (("mon", 4), ("sun", 3)):
            with self.subTest(weekday=weekday):
                self.toml_path.write_text(
                    SCHEDULE.replace(
                        'use_weekday = "mon"',
                        f'use_weekday = "{weekday}"\nall_day_event_title = "Schedule change"',
                    ),
                    encoding="utf-8",
                )
                schedule = load_schedule(self.toml_path)
                events = list(
                    Calendar.from_ical(
                        generate_calendar(schedule, self.toml_path)
                    ).walk("VEVENT")
                )
                annotations = [
                    event
                    for event in events
                    if str(event["SUMMARY"]) == "Schedule change"
                ]
                self.assertEqual(len(annotations), 1)
                annotation = annotations[0]
                self.assertEqual(annotation.decoded("DTSTART"), date(2026, 5, 6))
                self.assertEqual(annotation.decoded("DTEND"), date(2026, 5, 7))
                self.assertEqual(len(events), event_count)
                self.assertEqual(
                    len({str(event["UID"]) for event in events}), len(events)
                )
                regenerated = Calendar.from_ical(
                    generate_calendar(schedule, self.toml_path)
                )
                self.assertEqual(
                    str(annotation["UID"]),
                    str(
                        next(
                            event
                            for event in regenerated.walk("VEVENT")
                            if str(event["SUMMARY"]) == "Schedule change"
                        )["UID"]
                    ),
                )

    def test_blank_or_missing_all_day_event_title_adds_no_event(self):
        for field in ("", 'all_day_event_title = ""', 'all_day_event_title = "   "'):
            with self.subTest(field=field):
                self.toml_path.write_text(SCHEDULE + field + "\n", encoding="utf-8")
                events = Calendar.from_ical(
                    generate_calendar(load_schedule(self.toml_path), self.toml_path)
                )
                self.assertEqual(len(list(events.walk("VEVENT"))), 3)

    def test_all_day_event_title_must_be_text(self):
        self.toml_path.write_text(
            SCHEDULE + "all_day_event_title = 42\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "all_day_event_title must be a string"):
            load_schedule(self.toml_path)

    def test_named_and_numeric_time_slots(self):
        self.toml_path.write_text(
            SCHEDULE.replace("holidays = [2026-05-05]", "holidays = []").replace(
                "date = 2026-05-06", "date = 2026-05-12"
            ),
            encoding="utf-8",
        )
        calendar = Calendar.from_ical(
            generate_calendar(load_schedule(self.toml_path), self.toml_path)
        )
        events = list(calendar.walk("VEVENT"))
        starts = [event.decoded("DTSTART") for event in events]
        self.assertNotIn("DESCRIPTION", events[1])
        self.assertEqual(
            [(start.date(), start.time()) for start in starts],
            [
                (date(2026, 5, 4), time(8, 45)),
                (date(2026, 5, 5), time(12, 0)),
                (date(2026, 5, 6), time(13, 15)),
                (date(2026, 5, 11), time(8, 45)),
            ],
        )

    def test_unknown_time_slot_is_an_error(self):
        self.toml_path.write_text(
            SCHEDULE.replace('time_slot = "period 1"', 'time_slot = "unknown"', 1),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unknown time_slot"):
            load_schedule(self.toml_path)

    def test_description_must_be_text(self):
        self.toml_path.write_text(
            SCHEDULE.replace('description = "Professor Smith"', "description = 42"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "description must be a string"):
            load_schedule(self.toml_path)

    def test_cli_init_and_gen(self):
        init_path = self.directory / "new.toml"
        ics_path = self.directory / "calendar.ics"
        with patch.object(sys, "argv", ["calendargen", "init", str(init_path)]):
            main()
        self.assertEqual(init_path.read_text(encoding="utf-8"), TEMPLATE)
        with patch.object(sys, "argv", ["calendargen", "init", str(init_path)]):
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                main()
        with patch.object(
            sys, "argv", ["calendargen", "gen", str(self.toml_path), str(ics_path)]
        ):
            main()
        self.assertEqual(
            len(list(Calendar.from_ical(ics_path.read_bytes()).walk("VEVENT"))), 3
        )


if __name__ == "__main__":
    unittest.main()
