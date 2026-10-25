from __future__ import annotations

import logging
import os
from datetime import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .schedule_parser import ScheduleParseError, WeekPattern, parse_course_group

logger = logging.getLogger(__name__)

_WEEKDAYS = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}


class LessonResponse(BaseModel):
    day_of_week: int
    starts_at: time
    ends_at: time
    week_pattern: Literal["EVERY", "TOP", "BOTTOM"]
    subject: str
    instructor_name: str | None
    room: str | None


class ScheduleResponse(BaseModel):
    course_name: str
    group_name: str
    weekdays: dict[int, str]
    lessons: list[LessonResponse]


def create_app(
    schedule_path: Path | None = None,
    course_name: str | None = None,
    group_name: str | None = None,
    frontend_directory: Path | None = None,
) -> FastAPI:
    load_dotenv()
    schedule_path_value = os.getenv("SCHEDULE_XLS_PATH", "").strip()
    resolved_schedule_path = schedule_path or (
        Path(schedule_path_value).expanduser() if schedule_path_value else None
    )
    resolved_course_name = course_name or os.getenv("MINI_APP_COURSE", "3 курс")
    resolved_group_name = group_name or os.getenv("MINI_APP_GROUP", "02371-ДБ")

    app = FastAPI(
        title="Starosta Helper Mini App API",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/schedule", response_model=ScheduleResponse)
    def get_schedule() -> ScheduleResponse:
        if resolved_schedule_path is None:
            raise HTTPException(status_code=503, detail="Путь к файлу расписания не настроен.")
        try:
            schedule = parse_course_group(
                resolved_schedule_path,
                resolved_course_name,
                resolved_group_name,
            )
        except ScheduleParseError as error:
            logger.exception("Could not load configured schedule")
            raise HTTPException(
                status_code=503,
                detail="Расписание временно недоступно. Проверьте файл и настройки тестовой группы.",
            ) from error

        return ScheduleResponse(
            course_name=schedule.sheet_name,
            group_name=schedule.group_name,
            weekdays=_WEEKDAYS,
            lessons=[
                LessonResponse(
                    day_of_week=lesson.day_of_week,
                    starts_at=lesson.starts_at,
                    ends_at=lesson.ends_at,
                    week_pattern=lesson.week_pattern.value,
                    subject=lesson.subject,
                    instructor_name=lesson.instructor_name,
                    room=lesson.room,
                )
                for lesson in schedule.lessons
            ],
        )

    assets_directory = frontend_directory or Path(
        os.getenv("FRONTEND_DIST", "frontend/dist")
    )
    if assets_directory.is_dir():
        app.mount("/", StaticFiles(directory=assets_directory, html=True), name="frontend")

    return app


app = create_app()
