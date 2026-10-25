# Проектирование базы данных

Первая версия схемы рассчитана на PostgreSQL. Она разделяет шаблон повторяющегося расписания и конкретную пару в календаре, чтобы поддержать верхние и нижние недели, переносы и отмены.

## ER-диаграмма

```mermaid
erDiagram
    SEMESTERS ||--o{ SEMESTER_WEEK_CALENDAR : defines
    SEMESTERS ||--o{ SCHEDULE_IMPORTS : receives
    SCHEDULE_IMPORTS ||--o{ LESSON_TEMPLATES : contains
    LESSON_TEMPLATES ||--o{ LESSON_TEMPLATE_GROUPS : applies_to
    STUDY_GROUPS ||--o{ LESSON_TEMPLATE_GROUPS : attends
    LESSON_TEMPLATES ||--o{ LESSON_INSTANCES : generates
    LESSON_INSTANCES ||--o{ LESSON_INSTANCE_GROUPS : applies_to
    STUDY_GROUPS ||--o{ LESSON_INSTANCE_GROUPS : attends
    STUDY_GROUPS ||--o{ GROUP_MEMBERSHIPS : has
    STUDENTS ||--o{ GROUP_MEMBERSHIPS : joins
    GROUP_MEMBERSHIPS ||--o{ GROUP_ROLES : grants
    APP_USERS o|--o| STUDENTS : links
    APP_USERS ||--o{ SCHEDULE_IMPORTS : uploads
    APP_USERS ||--o{ ATTENDANCE : reviews
    LESSON_INSTANCES ||--o{ ATTENDANCE : records
    STUDENTS ||--o{ ATTENDANCE : submits
    TELEGRAM_CHATS ||--o{ TELEGRAM_CHAT_GROUPS : connects
    STUDY_GROUPS ||--o{ TELEGRAM_CHAT_GROUPS : uses

    SEMESTERS {
        bigint id PK
        varchar name
        date starts_on
        date ends_on
    }
    SEMESTER_WEEK_CALENDAR {
        bigint semester_id PK, FK
        date calendar_date PK
        week_type week_type
    }
    STUDY_GROUPS {
        bigint id PK
        varchar name UK
    }
    APP_USERS {
        bigint id PK
        bigint telegram_user_id UK
    }
    STUDENTS {
        bigint id PK
        bigint app_user_id UK, FK
        varchar full_name
    }
    GROUP_MEMBERSHIPS {
        bigint id PK
        bigint group_id FK
        bigint student_id FK
        date starts_on
        date ends_on
    }
    GROUP_ROLES {
        bigint id PK
        bigint membership_id FK
        role_code role
        date starts_on
        date ends_on
    }
    SCHEDULE_IMPORTS {
        bigint id PK
        bigint semester_id FK
        import_status status
        varchar file_name
    }
    LESSON_TEMPLATES {
        bigint id PK
        bigint schedule_import_id FK
        smallint day_of_week
        week_pattern week_pattern
        time starts_at
        time ends_at
        varchar subject
        varchar instructor_name
        varchar room
    }
    LESSON_TEMPLATE_GROUPS {
        bigint lesson_template_id PK, FK
        bigint group_id PK, FK
    }
    LESSON_INSTANCES {
        bigint id PK
        bigint lesson_template_id FK
        date original_date
        date lesson_date
        time starts_at
        time ends_at
        lesson_status status
    }
    LESSON_INSTANCE_GROUPS {
        bigint lesson_instance_id PK, FK
        bigint group_id PK, FK
    }
    ATTENDANCE {
        bigint id PK
        bigint lesson_instance_id FK
        bigint student_id FK
        student_mark student_mark
        absence_reason absence_reason
        reviewed_mark reviewed_mark
        bigint reviewed_by_user_id FK
    }
    TELEGRAM_CHATS {
        bigint id PK
        varchar title
    }
    TELEGRAM_CHAT_GROUPS {
        bigint telegram_chat_id PK, FK
        bigint group_id PK, FK
    }
```

## Основные правила

- `semester_week_calendar` содержит дату и тип недели (`TOP` — верхняя, `BOTTOM` — нижняя) для каждой даты семестра. Соответствие не выводится из чётности номера недели.
- Шаблон занятия хранит день недели, время и `week_pattern`: `EVERY`, `TOP` или `BOTTOM`. В шаблонных занятиях участвуют одна или несколько групп.
- При публикации расписания шаблоны разворачиваются в `lesson_instances` на конкретные даты. В таблице конкретных занятий сохраняются группы, чтобы последующие изменения шаблона не меняли историю. У перенесённой пары `original_date` остаётся прежней, а `lesson_date` указывает новую дату. Для разовой пары шаблон и исходная дата не задаются.
- Отменённая пара остаётся в базе со статусом `CANCELLED`. Это сохраняет историю и позволяет не создавать отметки для отменённых занятий.
- Список студентов и Telegram-пользователи разделены. У студента может пока не быть связанного аккаунта; список можно заполнить вручную или загрузить из текстового файла.
- Членство в группе имеет даты действия. Не следует удалять бывших студентов: завершайте членство, чтобы сохранить историю посещаемости.
- Один чат Telegram можно связать с несколькими группами, а группа может иметь несколько чатов.
- Для каждого студента и конкретной пары допускается не более одной записи посещаемости. `student_mark` — самоотметка (`PRESENT`, `LATE`, `ABSENT`); причина отсутствия (`ILLNESS`, `OTHER`) необязательна. Болезнь — причина, не итоговый статус. Староста проверяет отметку и задаёт `reviewed_mark` (`PRESENT`, `LATE`, `EXCUSED`, `UNEXCUSED`).
- Диагнозы и медицинские документы не хранятся. Проверка полномочий старосты и доступ к персональным данным должны выполняться приложением.
- Excel-файл хранится вне базы; `schedule_imports.storage_key` содержит ссылку на защищённое хранилище. История импорта позволяет отслеживать загрузки и ошибки.

## План развёртывания расписания

1. Загрузить Excel и создать запись `schedule_imports` со статусом `UPLOADED`.
2. Разобрать таблицу, проверить группы, даты и интервалы; сохранить выявленные ошибки.
3. Сохранить проверенные шаблоны занятий и участвующие группы.
4. Для дат семестра свериться с календарём верхних и нижних недель и создать конкретные пары.
5. После проверки сделать импорт активным, установив ему статус `PUBLISHED`. В одном семестре может быть только один опубликованный импорт.

Для новых версий расписания создаётся новый импорт. Приложение должно обновлять или пересоздавать только будущие пары; прошедшие пары и посещаемость сохраняются как история.
