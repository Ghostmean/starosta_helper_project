BEGIN;

CREATE TYPE week_type AS ENUM ('TOP', 'BOTTOM');
CREATE TYPE week_pattern AS ENUM ('EVERY', 'TOP', 'BOTTOM');
CREATE TYPE import_status AS ENUM ('UPLOADED', 'VALIDATED', 'PUBLISHED', 'FAILED');
CREATE TYPE lesson_status AS ENUM ('SCHEDULED', 'CANCELLED');
CREATE TYPE group_role_code AS ENUM ('STAROSTA', 'DEPUTY');
CREATE TYPE student_mark AS ENUM ('PRESENT', 'LATE', 'ABSENT');
CREATE TYPE absence_reason AS ENUM ('ILLNESS', 'OTHER');
CREATE TYPE reviewed_mark AS ENUM ('PRESENT', 'LATE', 'EXCUSED', 'UNEXCUSED');

CREATE TABLE semesters (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT semesters_valid_dates CHECK (ends_on >= starts_on),
    CONSTRAINT semesters_name_unique UNIQUE (name)
);

CREATE TABLE semester_week_calendar (
    semester_id BIGINT NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    calendar_date DATE NOT NULL,
    week_type week_type NOT NULL,
    PRIMARY KEY (semester_id, calendar_date)
);

CREATE TABLE study_groups (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app_users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    telegram_username VARCHAR(64),
    first_name VARCHAR(128),
    last_name VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE students (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    app_user_id BIGINT UNIQUE REFERENCES app_users(id) ON DELETE SET NULL,
    full_name VARCHAR(200) NOT NULL,
    student_number VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE group_memberships (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES study_groups(id) ON DELETE RESTRICT,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    starts_on DATE NOT NULL,
    ends_on DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT group_memberships_valid_dates CHECK (ends_on IS NULL OR ends_on >= starts_on),
    CONSTRAINT group_memberships_id_group_student_unique UNIQUE (id, group_id, student_id)
);

CREATE INDEX group_memberships_active_idx
    ON group_memberships (group_id, student_id, starts_on, ends_on);

CREATE TABLE group_roles (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    membership_id BIGINT NOT NULL REFERENCES group_memberships(id) ON DELETE CASCADE,
    role group_role_code NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE,
    CONSTRAINT group_roles_valid_dates CHECK (ends_on IS NULL OR ends_on >= starts_on),
    CONSTRAINT group_roles_membership_role_start_unique UNIQUE (membership_id, role, starts_on)
);

CREATE TABLE schedule_imports (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    semester_id BIGINT NOT NULL REFERENCES semesters(id) ON DELETE RESTRICT,
    uploaded_by_user_id BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
    file_name VARCHAR(255) NOT NULL,
    storage_key TEXT NOT NULL,
    status import_status NOT NULL DEFAULT 'UPLOADED',
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    CONSTRAINT schedule_imports_published_at_check
        CHECK ((status = 'PUBLISHED') = (published_at IS NOT NULL))
);

CREATE UNIQUE INDEX schedule_imports_one_published_per_semester
    ON schedule_imports (semester_id)
    WHERE status = 'PUBLISHED';

CREATE TABLE lesson_templates (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    schedule_import_id BIGINT NOT NULL REFERENCES schedule_imports(id) ON DELETE RESTRICT,
    day_of_week SMALLINT NOT NULL,
    week_pattern week_pattern NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    subject VARCHAR(200) NOT NULL,
    instructor_name VARCHAR(200),
    room VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT lesson_templates_valid_weekday CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT lesson_templates_valid_times CHECK (ends_at > starts_at)
);

CREATE INDEX lesson_templates_import_idx ON lesson_templates (schedule_import_id);

CREATE TABLE lesson_template_groups (
    lesson_template_id BIGINT NOT NULL REFERENCES lesson_templates(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL REFERENCES study_groups(id) ON DELETE RESTRICT,
    PRIMARY KEY (lesson_template_id, group_id)
);

CREATE TABLE lesson_instances (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lesson_template_id BIGINT REFERENCES lesson_templates(id) ON DELETE RESTRICT,
    original_date DATE,
    lesson_date DATE NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    status lesson_status NOT NULL DEFAULT 'SCHEDULED',
    cancellation_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT lesson_instances_template_origin_check CHECK (
        (lesson_template_id IS NULL AND original_date IS NULL)
        OR (lesson_template_id IS NOT NULL AND original_date IS NOT NULL)
    ),
    CONSTRAINT lesson_instances_valid_times CHECK (ends_at > starts_at),
    CONSTRAINT lesson_instances_cancellation_reason_check CHECK (
        status = 'CANCELLED' OR cancellation_reason IS NULL
    )
);

CREATE UNIQUE INDEX lesson_instances_template_origin_unique
    ON lesson_instances (lesson_template_id, original_date)
    WHERE lesson_template_id IS NOT NULL;

CREATE INDEX lesson_instances_date_idx ON lesson_instances (lesson_date, starts_at);

CREATE TABLE lesson_instance_groups (
    lesson_instance_id BIGINT NOT NULL REFERENCES lesson_instances(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL REFERENCES study_groups(id) ON DELETE RESTRICT,
    PRIMARY KEY (lesson_instance_id, group_id)
);

CREATE TABLE attendance (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lesson_instance_id BIGINT NOT NULL REFERENCES lesson_instances(id) ON DELETE RESTRICT,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    student_mark student_mark NOT NULL,
    absence_reason absence_reason,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_mark reviewed_mark,
    reviewed_by_user_id BIGINT REFERENCES app_users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ,
    CONSTRAINT attendance_one_per_student_per_lesson UNIQUE (lesson_instance_id, student_id),
    CONSTRAINT attendance_absence_reason_check CHECK (
        student_mark = 'ABSENT' OR absence_reason IS NULL
    ),
    CONSTRAINT attendance_review_fields_check CHECK (
        (reviewed_mark IS NULL AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL)
        OR (reviewed_mark IS NOT NULL AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

CREATE INDEX attendance_student_idx ON attendance (student_id, submitted_at DESC);

CREATE TABLE telegram_chats (
    id BIGINT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    chat_type VARCHAR(32) NOT NULL DEFAULT 'group',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE telegram_chat_groups (
    telegram_chat_id BIGINT NOT NULL REFERENCES telegram_chats(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL REFERENCES study_groups(id) ON DELETE CASCADE,
    PRIMARY KEY (telegram_chat_id, group_id)
);

COMMIT;
