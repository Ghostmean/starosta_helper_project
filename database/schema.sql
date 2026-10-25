-- Requires MySQL 8.0.16+ for enforced CHECK constraints.
-- Store application timestamps in UTC.

CREATE TABLE semesters (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT semesters_valid_dates CHECK (ends_on >= starts_on),
    CONSTRAINT semesters_name_unique UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE semester_week_calendar (
    semester_id BIGINT NOT NULL,
    calendar_date DATE NOT NULL,
    week_type ENUM('TOP', 'BOTTOM') NOT NULL,
    PRIMARY KEY (semester_id, calendar_date),
    CONSTRAINT semester_week_calendar_semester_fk
        FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE study_groups (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT study_groups_name_unique UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE app_users (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    telegram_username VARCHAR(64),
    first_name VARCHAR(128),
    last_name VARCHAR(128),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT app_users_telegram_user_unique UNIQUE (telegram_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE students (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    app_user_id BIGINT,
    full_name VARCHAR(200) NOT NULL,
    student_number VARCHAR(50),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT students_app_user_unique UNIQUE (app_user_id),
    CONSTRAINT students_app_user_fk
        FOREIGN KEY (app_user_id) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE group_memberships (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    group_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT group_memberships_valid_dates
        CHECK (ends_on IS NULL OR ends_on >= starts_on),
    CONSTRAINT group_memberships_id_group_student_unique
        UNIQUE (id, group_id, student_id),
    CONSTRAINT group_memberships_group_fk
        FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE RESTRICT,
    CONSTRAINT group_memberships_student_fk
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    INDEX group_memberships_active_idx (group_id, student_id, starts_on, ends_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE group_roles (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    membership_id BIGINT NOT NULL,
    role ENUM('STAROSTA', 'DEPUTY') NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE,
    CONSTRAINT group_roles_valid_dates
        CHECK (ends_on IS NULL OR ends_on >= starts_on),
    CONSTRAINT group_roles_membership_role_start_unique
        UNIQUE (membership_id, role, starts_on),
    CONSTRAINT group_roles_membership_fk
        FOREIGN KEY (membership_id) REFERENCES group_memberships(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE schedule_imports (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    semester_id BIGINT NOT NULL,
    uploaded_by_user_id BIGINT,
    file_name VARCHAR(255) NOT NULL,
    storage_key TEXT NOT NULL,
    status ENUM('UPLOADED', 'VALIDATED', 'PUBLISHED', 'FAILED')
        NOT NULL DEFAULT 'UPLOADED',
    error_summary TEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    published_at DATETIME(6),
    published_semester_id BIGINT GENERATED ALWAYS AS (
        CASE WHEN status = 'PUBLISHED' THEN semester_id ELSE NULL END
    ) STORED,
    CONSTRAINT schedule_imports_published_at_check CHECK (
        (status = 'PUBLISHED' AND published_at IS NOT NULL)
        OR (status <> 'PUBLISHED' AND published_at IS NULL)
    ),
    CONSTRAINT schedule_imports_one_published_per_semester
        UNIQUE (published_semester_id),
    CONSTRAINT schedule_imports_semester_fk
        FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE RESTRICT,
    CONSTRAINT schedule_imports_uploaded_by_fk
        FOREIGN KEY (uploaded_by_user_id) REFERENCES app_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE lesson_templates (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    schedule_import_id BIGINT NOT NULL,
    day_of_week TINYINT UNSIGNED NOT NULL,
    week_pattern ENUM('EVERY', 'TOP', 'BOTTOM') NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    subject VARCHAR(200) NOT NULL,
    instructor_name VARCHAR(200),
    room VARCHAR(100),
    notes TEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT lesson_templates_valid_weekday CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT lesson_templates_valid_times CHECK (ends_at > starts_at),
    CONSTRAINT lesson_templates_import_fk
        FOREIGN KEY (schedule_import_id) REFERENCES schedule_imports(id) ON DELETE RESTRICT,
    INDEX lesson_templates_import_idx (schedule_import_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE lesson_template_groups (
    lesson_template_id BIGINT NOT NULL,
    group_id BIGINT NOT NULL,
    PRIMARY KEY (lesson_template_id, group_id),
    CONSTRAINT lesson_template_groups_template_fk
        FOREIGN KEY (lesson_template_id) REFERENCES lesson_templates(id) ON DELETE CASCADE,
    CONSTRAINT lesson_template_groups_group_fk
        FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE lesson_instances (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    lesson_template_id BIGINT,
    original_date DATE,
    lesson_date DATE NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    status ENUM('SCHEDULED', 'CANCELLED') NOT NULL DEFAULT 'SCHEDULED',
    cancellation_reason TEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT lesson_instances_template_origin_check CHECK (
        (lesson_template_id IS NULL AND original_date IS NULL)
        OR (lesson_template_id IS NOT NULL AND original_date IS NOT NULL)
    ),
    CONSTRAINT lesson_instances_valid_times CHECK (ends_at > starts_at),
    CONSTRAINT lesson_instances_cancellation_reason_check
        CHECK (status = 'CANCELLED' OR cancellation_reason IS NULL),
    CONSTRAINT lesson_instances_template_origin_unique
        UNIQUE (lesson_template_id, original_date),
    CONSTRAINT lesson_instances_template_fk
        FOREIGN KEY (lesson_template_id) REFERENCES lesson_templates(id) ON DELETE RESTRICT,
    INDEX lesson_instances_date_idx (lesson_date, starts_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE lesson_instance_groups (
    lesson_instance_id BIGINT NOT NULL,
    group_id BIGINT NOT NULL,
    PRIMARY KEY (lesson_instance_id, group_id),
    CONSTRAINT lesson_instance_groups_instance_fk
        FOREIGN KEY (lesson_instance_id) REFERENCES lesson_instances(id) ON DELETE CASCADE,
    CONSTRAINT lesson_instance_groups_group_fk
        FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE attendance (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    lesson_instance_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    student_mark ENUM('PRESENT', 'LATE', 'ABSENT') NOT NULL,
    absence_reason ENUM('ILLNESS', 'OTHER'),
    submitted_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    reviewed_mark ENUM('PRESENT', 'LATE', 'EXCUSED', 'UNEXCUSED'),
    reviewed_by_user_id BIGINT,
    reviewed_at DATETIME(6),
    CONSTRAINT attendance_one_per_student_per_lesson
        UNIQUE (lesson_instance_id, student_id),
    CONSTRAINT attendance_absence_reason_check
        CHECK (student_mark = 'ABSENT' OR absence_reason IS NULL),
    CONSTRAINT attendance_review_fields_check CHECK (
        (reviewed_mark IS NULL AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL)
        OR (reviewed_mark IS NOT NULL AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)
    ),
    CONSTRAINT attendance_lesson_instance_fk
        FOREIGN KEY (lesson_instance_id) REFERENCES lesson_instances(id) ON DELETE RESTRICT,
    CONSTRAINT attendance_student_fk
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    CONSTRAINT attendance_reviewed_by_fk
        FOREIGN KEY (reviewed_by_user_id) REFERENCES app_users(id) ON DELETE RESTRICT,
    INDEX attendance_student_idx (student_id, submitted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE telegram_chats (
    id BIGINT NOT NULL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    chat_type VARCHAR(32) NOT NULL DEFAULT 'group',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    linked_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE telegram_chat_groups (
    telegram_chat_id BIGINT NOT NULL,
    group_id BIGINT NOT NULL,
    PRIMARY KEY (telegram_chat_id, group_id),
    CONSTRAINT telegram_chat_groups_chat_fk
        FOREIGN KEY (telegram_chat_id) REFERENCES telegram_chats(id) ON DELETE CASCADE,
    CONSTRAINT telegram_chat_groups_group_fk
        FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
