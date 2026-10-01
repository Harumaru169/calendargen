# CalendarGen

CalendarGen turns a declarative TOML schedule into an iCalendar (`.ics`) file. It is designed for events that usually happen every week, such as university lectures. Define the term dates, class times, and weekly events once; CalendarGen expands them into individual calendar events.

## Install

Requires Python 3.12 or later.

```sh
pip install .
```

## Usage

Create a starter schedule, edit it, and generate an ICS file:

```sh
calendargen init calendar.toml
calendargen gen calendar.toml calendar.ics
```

Import `calendar.ics` into a calendar application that supports iCalendar files. `init` creates a new file and will not overwrite an existing one.

## Schedule format

```toml
term_start = 2026-10-01
term_end = 2027-01-22
holidays = [2026-11-03]

[time_slots]
"period 2" = { start = "10:30", end = "12:00" }

[[courses]]
title = "Applied Algebra"
weekday = "mon"
time_slot = "period 2"
location = "Room 201"
description = "Professor Smith"

[[day_overrides]]
date = 2026-10-15
use_weekday = "mon"
```

- `term_start` and `term_end` are inclusive TOML dates.
- `holidays` skips all events on the listed dates. It can be omitted.
- Each `time_slots` entry defines a named local start and end time. Courses refer to these names through `time_slot`.
- Each `[[courses]]` entry defines a weekly event. `title`, `weekday`, and `time_slot` are required; `location` and `description` are optional. Weekdays are `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, or `sun`.
- A `[[day_overrides]]` entry uses another weekday's course schedule on a specific date. In the example, October 15 follows the Monday schedule. Overrides are optional and cannot share a date with `holidays`.

Event times use the local timezone of the machine running CalendarGen. The generated ICS file contains one event for each occurrence within the term.

## License

MIT. See [LICENSE](LICENSE).
