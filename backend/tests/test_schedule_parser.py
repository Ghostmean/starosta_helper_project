import unittest
from datetime import time

from backend.schedule_parser import ScheduleParseError, WeekPattern, parse_sheet


class FakeSheet:
    def __init__(self, rows: list[list[object]], merged_cells=(), name="test"):
        self.rows = rows
        self.nrows = len(rows)
        self.ncols = max(map(len, rows), default=0)
        self.merged_cells = list(merged_cells)
        self.name = name

    def cell_value(self, rowx: int, colx: int) -> object:
        if rowx >= self.nrows or colx >= len(self.rows[rowx]):
            return ""
        return self.rows[rowx][colx]


def schedule_sheet(*, subject_rows: dict[int, str], merged_cells=()) -> FakeSheet:
    rows: list[list[object]] = [[""] * 5 for _ in range(10)]
    rows[0][0] = "Дни"
    rows[0][1] = "Часы"
    rows[0][2] = "02121-ДБ"
    rows[1][0] = "ПОНЕДЕЛЬНИК"
    rows[1][1] = "08.30-10.00"
    for row, subject in subject_rows.items():
        rows[row][2] = subject
        rows[row][3] = "Преподаватель"
        rows[row][4] = "101"
    return FakeSheet(rows, merged_cells, name="1 курс")


class ParseSheetTests(unittest.TestCase):
    def test_parses_group_and_every_week_class(self):
        sheet = schedule_sheet(
            subject_rows={1: "  лек.   Математика "},
            merged_cells=[(1, 5, 2, 3)],
        )

        result = parse_sheet(sheet, "02121-ДБ")

        self.assertIsNotNone(result)
        lesson = result.lessons[0]
        self.assertEqual(result.group_name, "02121-ДБ")
        self.assertEqual(lesson.subject, "лек. Математика")
        self.assertEqual(lesson.day_of_week, 1)
        self.assertEqual(lesson.week_pattern, WeekPattern.EVERY)
        self.assertEqual(lesson.starts_at, time(8, 30))
        self.assertEqual(lesson.ends_at, time(10, 0))
        self.assertEqual(lesson.instructor_name, "Преподаватель")
        self.assertEqual(lesson.room, "101")

    def test_parses_upper_and_lower_week_classes(self):
        sheet = schedule_sheet(subject_rows={1: "Алгебра", 3: "Геометрия"})

        result = parse_sheet(sheet, "02121-ДБ")

        self.assertEqual(
            [lesson.week_pattern for lesson in result.lessons],
            [WeekPattern.TOP, WeekPattern.BOTTOM],
        )

    def test_returns_none_when_group_is_not_on_sheet(self):
        self.assertIsNone(parse_sheet(schedule_sheet(subject_rows={}), "99999-ДБ"))

    def test_rejects_ambiguous_class_position(self):
        sheet = schedule_sheet(subject_rows={2: "Алгебра"})

        with self.assertRaisesRegex(ScheduleParseError, "неоднозначное расположение"):
            parse_sheet(sheet, "02121-ДБ")


if __name__ == "__main__":
    unittest.main()
