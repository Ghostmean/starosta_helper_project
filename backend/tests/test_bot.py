import unittest
from datetime import time

from backend.bot import _group_keyboard, format_day_schedule
from backend.schedule_parser import LessonTemplate, ParsedSchedule, WeekPattern


class FormatDayScheduleTests(unittest.TestCase):
    def test_formats_lesson_details_and_week_pattern(self):
        schedule = ParsedSchedule(
            group_name="02121-ДБ",
            sheet_name="1 курс",
            lessons=[
                LessonTemplate(
                    group_name="02121-ДБ",
                    day_of_week=1,
                    week_pattern=WeekPattern.TOP,
                    starts_at=time(8, 30),
                    ends_at=time(10, 0),
                    subject="Математический анализ",
                    instructor_name="Иванов Иван Иванович",
                    room="203",
                )
            ],
        )

        message = format_day_schedule(schedule, 1)

        self.assertIn("02121-ДБ — Понедельник", message)
        self.assertIn("08:30–10:00 (верхняя неделя)", message)
        self.assertIn("Математический анализ", message)
        self.assertIn("Преподаватель: Иванов Иван Иванович", message)
        self.assertIn("Аудитория: 203", message)

    def test_reports_empty_day(self):
        schedule = ParsedSchedule("02121-ДБ", "1 курс", [])

        self.assertEqual(
            format_day_schedule(schedule, 7),
            "02121-ДБ — Воскресенье\n\nПар нет.",
        )

    def test_sorts_lessons_by_start_time(self):
        later = LessonTemplate(
            "02121-ДБ", 1, WeekPattern.EVERY, time(11, 50), time(13, 20),
            "Поздняя пара", None, None,
        )
        earlier = LessonTemplate(
            "02121-ДБ", 1, WeekPattern.EVERY, time(8, 30), time(10, 0),
            "Ранняя пара", None, None,
        )
        schedule = ParsedSchedule("02121-ДБ", "1 курс", [later, earlier])

        message = format_day_schedule(schedule, 1)

        self.assertLess(message.index("Ранняя пара"), message.index("Поздняя пара"))


class GroupKeyboardTests(unittest.TestCase):
    def test_callback_indices_match_group_positions_across_rows(self):
        groups = [f"group-{index}" for index in range(8)]

        keyboard = _group_keyboard(groups)

        selected_groups = [
            (button.text, button.callback_data)
            for row in keyboard.inline_keyboard[:-1]
            for button in row
        ]
        self.assertEqual(
            selected_groups,
            [(name, f"group:{index}") for index, name in enumerate(groups)],
        )


if __name__ == "__main__":
    unittest.main()
