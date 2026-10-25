from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from dotenv import load_dotenv

from .schedule_parser import (
    LessonTemplate,
    ParsedSchedule,
    ScheduleParseError,
    WeekPattern,
    list_course_groups,
    parse_course_group,
)

_WEEKDAYS = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}
_WEEK_PATTERN_LABELS = {
    WeekPattern.EVERY: "каждую неделю",
    WeekPattern.TOP: "верхняя неделя",
    WeekPattern.BOTTOM: "нижняя неделя",
}


class ScheduleSelection(StatesGroup):
    choosing_course = State()
    choosing_group = State()
    choosing_day = State()


def _keyboard(
    rows: list[list[InlineKeyboardButton]],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _course_keyboard(course_names: list[str]) -> InlineKeyboardMarkup:
    return _keyboard(
        [[InlineKeyboardButton(text=name, callback_data=f"course:{index}")]
         for index, name in enumerate(course_names)]
    )


def _group_keyboard(group_names: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=name, callback_data=f"group:{index}")
            for index, name in enumerate(
                group_names[start : start + 2],
                start=start,
            )
        ]
        for start in range(0, len(group_names), 2)
    ]
    rows.append([InlineKeyboardButton(text="К выбору курса", callback_data="back:courses")])
    return _keyboard(rows)


def _day_keyboard() -> InlineKeyboardMarkup:
    day_buttons = [
        InlineKeyboardButton(text=name, callback_data=f"day:{day}")
        for day, name in _WEEKDAYS.items()
    ]
    rows = [day_buttons[start : start + 2] for start in range(0, len(day_buttons), 2)]
    rows.append([InlineKeyboardButton(text="К выбору группы", callback_data="back:groups")])
    return _keyboard(rows)


def format_day_schedule(schedule: ParsedSchedule, day_of_week: int) -> str:
    """Format a parsed day's classes as a plain Telegram message."""
    day_name = _WEEKDAYS[day_of_week]
    lessons = sorted(
        (lesson for lesson in schedule.lessons if lesson.day_of_week == day_of_week),
        key=lambda lesson: lesson.starts_at,
    )
    lines = [f"{schedule.group_name} — {day_name}"]
    if not lessons:
        return "\n".join([*lines, "", "Пар нет."])

    for lesson in lessons:
        lines.extend(["", _format_lesson(lesson)])
    return "\n".join(lines)


def _format_lesson(lesson: LessonTemplate) -> str:
    lines = [
        f"{lesson.starts_at:%H:%M}–{lesson.ends_at:%H:%M} "
        f"({_WEEK_PATTERN_LABELS[lesson.week_pattern]})",
        lesson.subject,
    ]
    if lesson.instructor_name:
        lines.append(f"Преподаватель: {lesson.instructor_name}")
    if lesson.room:
        lines.append(f"Аудитория: {lesson.room}")
    return "\n".join(lines)


def create_dispatcher(schedule_path: Path, webapp_url: str | None = None) -> Dispatcher:
    courses = list_course_groups(schedule_path)
    course_names = list(courses)
    if not course_names:
        raise ScheduleParseError("В файле расписания не найдены листы курсов и группы.")

    router = Router()

    @router.message(CommandStart())
    async def start_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        if webapp_url:
            await message.answer(
                "Откройте тестовое расписание группы в Mini App "
                "или выберите другую группу командой /schedule.",
                reply_markup=_keyboard(
                    [[
                        InlineKeyboardButton(
                            text="Открыть Mini App",
                            web_app=WebAppInfo(url=webapp_url),
                        )
                    ]]
                ),
            )
            return
        await show_course_selection(message, state, course_names)

    @router.message(Command("schedule"))
    async def start_schedule(message: Message, state: FSMContext) -> None:
        await state.clear()
        await show_course_selection(message, state, course_names)

    async def show_course_selection(
        message: Message,
        state: FSMContext,
        course_names: list[str],
    ) -> None:
        await state.set_state(ScheduleSelection.choosing_course)
        await message.answer("Выберите курс:", reply_markup=_course_keyboard(course_names))

    @router.message(Command("cancel"))
    async def cancel_selection(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Выбор расписания отменён. Нажмите /schedule, чтобы начать снова.")

    @router.callback_query(
        ScheduleSelection.choosing_course,
        F.data.startswith("course:"),
    )
    async def choose_course(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            index = int((callback.data or "").split(":", maxsplit=1)[1])
            course_name = course_names[index]
        except (ValueError, IndexError):
            await callback.answer("Курс не найден. Начните выбор заново.", show_alert=True)
            await state.clear()
            return

        group_names = courses[course_name]
        await state.update_data(course_name=course_name, group_names=group_names)
        await state.set_state(ScheduleSelection.choosing_group)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(
                f"Курс: {course_name}\nВыберите группу:",
                reply_markup=_group_keyboard(group_names),
            )

    @router.callback_query(ScheduleSelection.choosing_group, F.data == "back:courses")
    async def back_to_courses(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(ScheduleSelection.choosing_course)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(
                "Выберите курс:",
                reply_markup=_course_keyboard(course_names),
            )

    @router.callback_query(
        ScheduleSelection.choosing_group,
        F.data.startswith("group:"),
    )
    async def choose_group(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        group_names = data.get("group_names", [])
        try:
            index = int((callback.data or "").split(":", maxsplit=1)[1])
            group_name = group_names[index]
        except (ValueError, IndexError, TypeError):
            await callback.answer("Группа не найдена. Начните выбор заново.", show_alert=True)
            await state.clear()
            return

        await state.update_data(group_name=group_name)
        await state.set_state(ScheduleSelection.choosing_day)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(
                f"Группа: {group_name}\nВыберите день недели:",
                reply_markup=_day_keyboard(),
            )

    @router.callback_query(ScheduleSelection.choosing_day, F.data == "back:groups")
    async def back_to_groups(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        group_names = data.get("group_names", [])
        course_name = data.get("course_name", "")
        await state.set_state(ScheduleSelection.choosing_group)
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(
                f"Курс: {course_name}\nВыберите группу:",
                reply_markup=_group_keyboard(group_names),
            )

    @router.callback_query(
        ScheduleSelection.choosing_day,
        F.data.startswith("day:"),
    )
    async def choose_day(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            day_of_week = int((callback.data or "").split(":", maxsplit=1)[1])
            if day_of_week not in _WEEKDAYS:
                raise ValueError
            schedule = parse_course_group(
                schedule_path,
                data["course_name"],
                data["group_name"],
            )
        except ScheduleParseError as error:
            await callback.answer("Не удалось прочитать расписание.", show_alert=True)
            if isinstance(callback.message, Message):
                await callback.message.answer(f"Ошибка при чтении расписания: {error}")
            await state.clear()
            return
        except (ValueError, KeyError):
            await callback.answer(
                "Выбор устарел. Нажмите /schedule и начните заново.",
                show_alert=True,
            )
            await state.clear()
            return

        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer(format_day_schedule(schedule, day_of_week))
            await callback.message.answer(
                "Выберите другой день или вернитесь к выбору группы:",
                reply_markup=_day_keyboard(),
            )
        await state.set_state(ScheduleSelection.choosing_day)

    @router.callback_query()
    async def ignore_stale_callback(callback: CallbackQuery) -> None:
        await callback.answer("Запустите выбор расписания командой /schedule.")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def run_bot() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    schedule_path_value = os.getenv("SCHEDULE_XLS_PATH", "").strip()
    webapp_url = os.getenv("TELEGRAM_WEBAPP_URL", "").strip() or None
    if not token:
        raise RuntimeError("Укажите токен бота в переменной TELEGRAM_BOT_TOKEN.")
    if not schedule_path_value:
        raise RuntimeError("Укажите путь к расписанию в переменной SCHEDULE_XLS_PATH.")

    schedule_path = Path(schedule_path_value).expanduser()
    dispatcher = create_dispatcher(schedule_path, webapp_url)
    bot = Bot(token=token)
    try:
        if webapp_url:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть приложение",
                    web_app=WebAppInfo(url=webapp_url),
                )
            )
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bot())
