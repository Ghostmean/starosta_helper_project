from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import time
from enum import Enum
from pathlib import Path
from typing import Protocol

import xlrd


class WeekPattern(str, Enum):
    EVERY = "EVERY"
    TOP = "TOP"
    BOTTOM = "BOTTOM"


class ScheduleParseError(ValueError):
    """Raised when a workbook does not match the supported schedule layout."""


class SheetLike(Protocol):
    nrows: int
    ncols: int
    merged_cells: list[tuple[int, int, int, int]]

    def cell_value(self, rowx: int, colx: int) -> object: ...


@dataclass(frozen=True)
class LessonTemplate:
    group_name: str
    day_of_week: int
    week_pattern: WeekPattern
    starts_at: time
    ends_at: time
    subject: str
    instructor_name: str | None
    room: str | None


@dataclass(frozen=True)
class ParsedSchedule:
    group_name: str
    sheet_name: str
    lessons: list[LessonTemplate]


_WEEKDAYS = {
    "ПОНЕДЕЛЬНИК": 1,
    "ВТОРНИК": 2,
    "СРЕДА": 3,
    "ЧЕТВЕРГ": 4,
    "ПЯТНИЦА": 5,
    "СУББОТА": 6,
    "ВОСКРЕСЕНЬЕ": 7,
}
_TIME_RANGE = re.compile(
    r"^\s*(\d{1,2})[.:](\d{2})\s*[-–—]\s*(\d{1,2})[.:](\d{2})\s*$"
)
_SLOT_ROWS = 4


def _text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _normalize_group_name(value: object) -> str:
    return _text(value).upper().replace("–", "-").replace("—", "-").replace("−", "-")


def _parse_time_range(value: object, *, sheet_name: str, row_number: int) -> tuple[time, time]:
    match = _TIME_RANGE.fullmatch(_text(value))
    if match is None:
        raise ScheduleParseError(
            f"Лист {sheet_name!r}, строка {row_number}: "
            f"не удалось распознать время пары {_text(value)!r}."
        )
    start_hour, start_minute, end_hour, end_minute = map(int, match.groups())
    try:
        starts_at = time(start_hour, start_minute)
        ends_at = time(end_hour, end_minute)
    except ValueError as error:
        raise ScheduleParseError(
            f"Лист {sheet_name!r}, строка {row_number}: "
            f"некорректное время пары {_text(value)!r}."
        ) from error
    if ends_at <= starts_at:
        raise ScheduleParseError(
            f"Лист {sheet_name!r}, строка {row_number}: "
            "время окончания пары должно быть позже времени начала."
        )
    return starts_at, ends_at


def _find_schedule_header(sheet: SheetLike) -> int | None:
    for row in range(sheet.nrows):
        first = _text(sheet.cell_value(row, 0)).upper()
        second = _text(sheet.cell_value(row, 1)).upper()
        if first == "ДНИ" and second == "ЧАСЫ":
            return row
    return None


def _merged_row_span(sheet: SheetLike, row: int, column: int) -> int:
    for first_row, last_row, first_column, last_column in sheet.merged_cells:
        if first_row <= row < last_row and first_column <= column < last_column:
            return last_row - first_row
    return 1


def _week_patterns(
    sheet: SheetLike,
    group_column: int,
    slot_start: int,
    subject_rows: list[int],
    *,
    sheet_name: str,
) -> list[WeekPattern]:
    offsets = [row - slot_start for row in subject_rows]
    if len(subject_rows) == 1:
        offset = offsets[0]
        if offset == 0 and _merged_row_span(sheet, subject_rows[0], group_column) == _SLOT_ROWS:
            return [WeekPattern.EVERY]
        if offset == 0:
            return [WeekPattern.TOP]
        if offset == 2:
            return [WeekPattern.BOTTOM]
    elif len(subject_rows) == 2 and offsets == [0, 2]:
        return [WeekPattern.TOP, WeekPattern.BOTTOM]

    rows = ", ".join(str(row + 1) for row in subject_rows)
    raise ScheduleParseError(
        f"Лист {sheet_name!r}, строки {rows}: "
        "неоднозначное расположение занятий группы внутри блока пары."
    )


def parse_sheet(sheet: SheetLike, group_name: str) -> ParsedSchedule | None:
    """Parse one course sheet; return None when it has no schedule header or group."""
    header_row = _find_schedule_header(sheet)
    if header_row is None:
        return None

    wanted_group = _normalize_group_name(group_name)
    group_columns = [
        column
        for column in range(2, sheet.ncols)
        if _normalize_group_name(sheet.cell_value(header_row, column)) == wanted_group
    ]
    if not group_columns:
        return None
    if len(group_columns) > 1:
        raise ScheduleParseError(f"На листе расписания группа {group_name!r} указана несколько раз.")

    group_column = group_columns[0]
    if group_column + 2 >= sheet.ncols:
        raise ScheduleParseError(
            f"На листе расписания у группы {group_name!r} не хватает столбцов "
            "для преподавателя и аудитории."
        )

    sheet_name = str(getattr(sheet, "name", ""))
    day_of_week: int | None = None
    slots: list[tuple[int, time, time, int]] = []

    for row in range(header_row + 1, sheet.nrows):
        day_text = _text(sheet.cell_value(row, 0)).upper()
        if day_text:
            day_of_week = _WEEKDAYS.get(day_text)

        time_text = _text(sheet.cell_value(row, 1))
        if not time_text:
            continue
        if _TIME_RANGE.fullmatch(time_text) is None:
            continue
        if day_of_week is None:
            raise ScheduleParseError(
                f"Лист {sheet_name!r}, строка {row + 1}: перед временем пары "
                "не найден распознаваемый день недели."
            )
        starts_at, ends_at = _parse_time_range(
            time_text,
            sheet_name=sheet_name,
            row_number=row + 1,
        )
        slots.append((row, starts_at, ends_at, day_of_week))

    lessons: list[LessonTemplate] = []
    for slot_index, (slot_start, starts_at, ends_at, slot_day) in enumerate(slots):
        next_slot = slots[slot_index + 1][0] if slot_index + 1 < len(slots) else sheet.nrows
        slot_end = min(slot_start + _SLOT_ROWS, next_slot)
        subject_rows = [
            row
            for row in range(slot_start, slot_end)
            if _text(sheet.cell_value(row, group_column))
        ]
        if not subject_rows:
            continue

        patterns = _week_patterns(
            sheet,
            group_column,
            slot_start,
            subject_rows,
            sheet_name=sheet_name,
        )
        for row, pattern in zip(subject_rows, patterns, strict=True):
            subject = _text(sheet.cell_value(row, group_column))
            instructor = _text(sheet.cell_value(row, group_column + 1)) or None
            room = _text(sheet.cell_value(row, group_column + 2)) or None
            lessons.append(
                LessonTemplate(
                    group_name=_text(sheet.cell_value(header_row, group_column)),
                    day_of_week=slot_day,
                    week_pattern=pattern,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    subject=subject,
                    instructor_name=instructor,
                    room=room,
                )
            )

    return ParsedSchedule(
        group_name=_text(sheet.cell_value(header_row, group_column)),
        sheet_name=sheet_name,
        lessons=lessons,
    )


def list_course_groups(path: str | Path) -> dict[str, list[str]]:
    """Return course sheet names and the group headers found on each sheet."""
    workbook = _open_workbook(path)
    courses: dict[str, list[str]] = {}
    for sheet in workbook.sheets():
        header_row = _find_schedule_header(sheet)
        if header_row is None:
            continue
        groups = [
            _text(sheet.cell_value(header_row, column))
            for column in range(2, sheet.ncols)
            if _text(sheet.cell_value(header_row, column))
        ]
        if groups:
            courses[sheet.name] = groups
    return courses


def parse_course_group(
    path: str | Path,
    course_name: str,
    group_name: str,
) -> ParsedSchedule:
    """Parse a group from a specific course sheet."""
    workbook = _open_workbook(path)
    try:
        sheet = workbook.sheet_by_name(course_name)
    except xlrd.XLRDError as error:
        raise ScheduleParseError(f"Лист курса {course_name!r} не найден.") from error
    schedule = parse_sheet(sheet, group_name)
    if schedule is None:
        raise ScheduleParseError(
            f"Группа {group_name!r} не найдена на листе {course_name!r}."
        )
    return schedule


def _open_workbook(path: str | Path) -> xlrd.book.Book:
    workbook_path = Path(path)
    if workbook_path.suffix.lower() != ".xls":
        raise ScheduleParseError("Поддерживается только формат Excel .xls.")
    if not workbook_path.is_file():
        raise ScheduleParseError(f"Файл расписания не найден: {workbook_path}")
    try:
        return xlrd.open_workbook(str(workbook_path), formatting_info=True)
    except (OSError, xlrd.XLRDError) as error:
        raise ScheduleParseError(f"Не удалось открыть Excel-файл: {error}") from error


def parse_schedule(path: str | Path, group_name: str) -> ParsedSchedule:
    """Load a legacy .xls workbook and parse the requested study group."""
    workbook = _open_workbook(path)
    parsed_schedules = [
        parsed
        for sheet in workbook.sheets()
        if (parsed := parse_sheet(sheet, group_name)) is not None
    ]
    if not parsed_schedules:
        raise ScheduleParseError(f"Группа {group_name!r} не найдена в файле расписания.")
    if len(parsed_schedules) > 1:
        sheets = ", ".join(repr(parsed.sheet_name) for parsed in parsed_schedules)
        raise ScheduleParseError(
            f"Группа {group_name!r} найдена на нескольких листах: {sheets}."
        )
    return parsed_schedules[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Разобрать расписание группы из Excel .xls.")
    parser.add_argument("file", type=Path, help="Путь к файлу .xls")
    parser.add_argument("group", help="Название группы из заголовка Excel, например 02121-ДБ")
    args = parser.parse_args()

    try:
        schedule = parse_schedule(args.file, args.group)
    except ScheduleParseError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(schedule), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
