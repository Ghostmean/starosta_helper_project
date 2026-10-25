import unittest
from datetime import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.schedule_parser import LessonTemplate, ParsedSchedule, WeekPattern


class ScheduleApiTests(unittest.TestCase):
    def setUp(self):
        self.schedule = ParsedSchedule(
            group_name="02371-ДБ",
            sheet_name="3 курс",
            lessons=[
                LessonTemplate(
                    group_name="02371-ДБ",
                    day_of_week=1,
                    week_pattern=WeekPattern.EVERY,
                    starts_at=time(8, 30),
                    ends_at=time(10, 0),
                    subject="Математический анализ",
                    instructor_name="Иванов Иван Иванович",
                    room="203",
                )
            ],
        )

    def test_health_endpoint(self):
        client = TestClient(create_app(schedule_path=Path("schedule.xls")))

        response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_schedule_endpoint_returns_configured_group(self):
        app = create_app(
            schedule_path=Path("schedule.xls"),
            course_name="3 курс",
            group_name="02371-ДБ",
        )
        with patch("backend.api.parse_course_group", return_value=self.schedule):
            response = TestClient(app).get("/api/schedule")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["course_name"], "3 курс")
        self.assertEqual(payload["group_name"], "02371-ДБ")
        self.assertEqual(payload["lessons"][0]["subject"], "Математический анализ")
        self.assertEqual(payload["lessons"][0]["week_pattern"], "EVERY")

    def test_schedule_endpoint_reports_unavailable_file(self):
        app = create_app(
            schedule_path=Path("missing.xls"),
            course_name="3 курс",
            group_name="02371-ДБ",
        )

        response = TestClient(app).get("/api/schedule")

        self.assertEqual(response.status_code, 503)
        self.assertIn("временно недоступно", response.json()["detail"].lower())

    def test_frontend_build_is_served_at_root(self):
        with TemporaryDirectory() as temp_dir:
            frontend_directory = Path(temp_dir)
            (frontend_directory / "index.html").write_text(
                "<title>Староста — расписание</title>",
                encoding="utf-8",
            )
            app = create_app(
                schedule_path=Path("schedule.xls"),
                frontend_directory=frontend_directory,
            )

            response = TestClient(app).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Староста — расписание", response.text)


if __name__ == "__main__":
    unittest.main()
