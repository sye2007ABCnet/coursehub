-- Создание таблиц и начальных данных.
-- Скрипт выполняется контейнером PostgreSQL автоматически при ПЕРВОМ запуске,
-- когда том с данными ещё пуст (каталог /docker-entrypoint-initdb.d).

-- Расширение pgcrypto: функции crypt() и gen_salt() для хранения паролей в виде хеша
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Сотрудники (пользователи системы)
CREATE TABLE employees (
    id            SERIAL PRIMARY KEY,
    email         TEXT    NOT NULL UNIQUE,
    full_name     TEXT    NOT NULL,
    department    TEXT    NOT NULL DEFAULT '',
    password_hash TEXT    NOT NULL,
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE
);

-- Обучающие курсы
CREATE TABLE courses (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

-- Назначения курсов сотрудникам
CREATE TABLE enrollments (
    id           SERIAL PRIMARY KEY,
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    course_id    INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    deadline     DATE,
    status       TEXT NOT NULL DEFAULT 'assigned' CHECK (status IN ('assigned', 'completed')),
    completed_at TIMESTAMP,
    UNIQUE (employee_id, course_id)   -- один курс нельзя назначить сотруднику дважды
);

-- Начальные данные. Пароль хешируется алгоритмом bcrypt: crypt(пароль, gen_salt('bf'))
INSERT INTO employees (email, full_name, department, password_hash, is_admin) VALUES
    ('admin@corp.local',   'Администратор обучения',  'HR',               crypt('admin123',    gen_salt('bf')), TRUE),
    ('ivanov@corp.local',  'Иванов Иван Иванович',    'Отдел разработки', crypt('employee123', gen_salt('bf')), FALSE),
    ('petrova@corp.local', 'Петрова Анна Сергеевна',  'Бухгалтерия',      crypt('employee123', gen_salt('bf')), FALSE);

INSERT INTO courses (title, description) VALUES
    ('Информационная безопасность', 'Пароли, фишинг, работа с персональными данными.'),
    ('Охрана труда',                'Вводный инструктаж и правила безопасной работы в офисе.'),
    ('Адаптация нового сотрудника', 'Структура компании, внутренние сервисы и регламенты.');

INSERT INTO enrollments (employee_id, course_id, deadline) VALUES
    (2, 1, CURRENT_DATE + 30),
    (3, 1, CURRENT_DATE + 30),
    (2, 3, CURRENT_DATE + 14);
