"""Read a class schedule and turn it into an iCalendar file."""

import tomllib
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from icalendar import Calendar, Event
from tzlocal import get_localzone

TEMPLATE = """term_start = 2026-10-01
term_end = 2027-01-22
holidays = [2026-10-12, 2026-11-03]

[time_slots]
"period 1" = { start = "08:45", end = "10:15" }
"period 2" = { start = "10:30", end = "12:00" }
"lunch" = { start = "12:00", end = "13:15" }
"period 3" = { start = "13:15", end = "14:45" }
"period 4" = { start = "15:00", end = "16:30" }
"period 5" = { start = "16:45", end = "18:15" }

[[courses]]
title = "Applied Algebra"
description = "Professor Tsujimoto"
weekday = "mon"
time_slot = "period 2"
location = "Lecture Room 2, Research Building No.8"

[[courses]]
title = "Fluid Mechanics"
description = "Professor Taguchi"
weekday = "tue"
time_slot = "period 2"
location = "Lecture Room 4, Research Building No.8"

[[day_overrides]]
date = 2026-10-15
use_weekday = "mon"

[[day_overrides]]
date = 2026-11-26
use_weekday = "tue"
"""

WEEKDAYS = {
    name: number
    for number, name in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))
}


def _date(value: object, name: str) -> date:
    if type(value) is not date:
        raise ValueError(f"{name} must be a TOML date")
    return value


def _weekday(value: object, name: str) -> int:
    if not isinstance(value, str) or value not in WEEKDAYS:
        raise ValueError(f"{name} must be one of: {', '.join(WEEKDAYS)}")
    return WEEKDAYS[value]


def _clock(value: object, name: str) -> time:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a time string such as '08:45'")
    try:
        result = time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a time string such as '08:45'") from error
    if result.tzinfo is not None:
        raise ValueError(f"{name} must be a local time without an offset")
    return result


def load_schedule(path: Path) -> dict:
    """Load and check the fields needed to generate the calendar."""
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"invalid TOML in {path}: {error}") from error

    start = _date(data.get("term_start"), "term_start")
    end = _date(data.get("term_end"), "term_end")
    if end < start:
        raise ValueError("term_end must not precede term_start")

    holidays = data.get("holidays", [])
    if not isinstance(holidays, list):
        raise ValueError("holidays must be a list of TOML dates")
    holidays = {_date(day, "holidays item") for day in holidays}

    time_slots = data.get("time_slots")
    if not isinstance(time_slots, dict) or not time_slots:
        raise ValueError("time_slots must contain at least one time slot")
    parsed_time_slots = {}
    for name, time_slot in time_slots.items():
        if not name.strip() or not isinstance(time_slot, dict):
            raise ValueError(f"invalid time slot: {name!r}")
        begins = _clock(time_slot.get("start"), f"time slot {name!r} start")
        ends = _clock(time_slot.get("end"), f"time slot {name!r} end")
        if ends <= begins:
            raise ValueError(f"time slot {name!r} end must be after start")
        parsed_time_slots[name] = (begins, ends)

    courses = data.get("courses")
    if not isinstance(courses, list):
        raise ValueError("courses must be a list of tables")
    parsed_courses = []
    for index, course in enumerate(courses, start=1):
        if not isinstance(course, dict):
            raise ValueError(f"course {index} must be a table")
        title = course.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"course {index} needs a title")
        weekday = _weekday(course.get("weekday"), f"course {index} weekday")
        time_slot = course.get("time_slot")
        if not isinstance(time_slot, str) or time_slot not in parsed_time_slots:
            raise ValueError(f"course {index} refers to an unknown time_slot")
        location = course.get("location")
        if location is not None and not isinstance(location, str):
            raise ValueError(f"course {index} location must be a string")
        description = course.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError(f"course {index} description must be a string")
        parsed_courses.append((title, weekday, time_slot, location, description))

    overrides = data.get("day_overrides", [])
    if not isinstance(overrides, list):
        raise ValueError("day_overrides must be a list of tables")
    parsed_overrides = {}
    for index, override in enumerate(overrides, start=1):
        if not isinstance(override, dict):
            raise ValueError(f"day_overrides item {index} must be a table")
        day = _date(override.get("date"), f"day_overrides item {index} date")
        if day in holidays:
            raise ValueError(f"{day} appears in both holidays and day_overrides")
        if day in parsed_overrides:
            raise ValueError(f"duplicate day_overrides date: {day}")
        parsed_overrides[day] = _weekday(
            override.get("use_weekday"), f"day_overrides item {index} use_weekday"
        )

    return {
        "start": start,
        "end": end,
        "holidays": holidays,
        "time_slots": parsed_time_slots,
        "courses": parsed_courses,
        "overrides": parsed_overrides,
    }


def generate_calendar(schedule: dict, source: Path) -> bytes:
    """Generate one VEVENT per course occurrence."""
    local_zone = get_localzone()
    calendar = Calendar()
    calendar.add("prodid", "-//CalendarGen//EN")
    calendar.add("version", "2.0")

    day = schedule["start"]
    while day <= schedule["end"]:
        if day not in schedule["holidays"]:
            weekday = schedule["overrides"].get(day, day.weekday())
            for index, (
                title,
                course_weekday,
                time_slot,
                location,
                description,
            ) in enumerate(schedule["courses"]):
                if weekday != course_weekday:
                    continue
                begins, ends = schedule["time_slots"][time_slot]
                event = Event()
                event.add("summary", title)
                event.add("dtstart", datetime.combine(day, begins, local_zone))
                event.add("dtend", datetime.combine(day, ends, local_zone))
                event.add("dtstamp", datetime.now(UTC))
                event.add(
                    "uid",
                    f"{uuid5(NAMESPACE_URL, f'{source.resolve()}:{index}:{day}')}@calendargen",
                )
                if location:
                    event.add("location", location)
                if description is not None:
                    event.add("description", description)
                calendar.add_component(event)
        day += timedelta(days=1)

    calendar.add_missing_timezones(
        first_date=schedule["start"],
        last_date=schedule["end"] + timedelta(days=1),
    )
    return calendar.to_ical()
