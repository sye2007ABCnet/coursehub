"""CourseHub API — серверная часть платформы корпоративного обучения.

Запуск: uvicorn main:app --host 0.0.0.0 --port 8000
"""

import json
import os
import secrets
import socket
from pathlib import Path

import psycopg
import redis
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from psycopg.rows import dict_row
from pydantic import BaseModel

# Настройки берутся из переменных окружения, которые задаются в compose.yaml
DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
SESSION_TTL = 8 * 60 * 60   # сессия действует 8 часов
CACHE_TTL = 30              # список курсов кэшируется на 30 секунд
HOSTNAME = socket.gethostname()  # имя контейнера, показывает, какая реплика ответила

# В кластере Swarm пароль БД передаётся не переменной окружения, а секретом:
# файлом /run/secrets/db_password. Если файла нет (обычный docker compose),
# пароль берётся из DATABASE_URL.
SECRET_FILE = "/run/secrets/db_password"
DB_PASSWORD = Path(SECRET_FILE).read_text().strip() if os.path.exists(SECRET_FILE) else None

# Документация API (Swagger UI) доступна через nginx: http://localhost:8081/api/docs
app = FastAPI(title="CourseHub API", docs_url="/api/docs", openapi_url="/api/openapi.json")
cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def db(sql: str, params: tuple = ()) -> list[dict]:
    """Выполнить SQL-запрос к PostgreSQL и вернуть строки результата."""
    with psycopg.connect(DATABASE_URL, password=DB_PASSWORD, row_factory=dict_row) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


@app.middleware("http")
async def add_hostname(request: Request, call_next):
    """Добавляет в каждый ответ заголовок с именем контейнера."""
    response = await call_next(request)
    response.headers["X-Served-By"] = HOSTNAME
    return response


# ---------- Авторизация ----------
# После входа сервер выдаёт случайный токен и сохраняет его в Redis.
# Так как Redis общий для всех реплик api, сессия работает на любой из них.

def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ")
    data = cache.get(f"session:{token}") if token else None
    if data is None:
        raise HTTPException(401, "Требуется вход в систему")
    return json.loads(data)


def admin_only(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "Доступно только администратору")
    return user


class LoginForm(BaseModel):
    email: str
    password: str


@app.post("/api/login")
def login(form: LoginForm):
    # Пароль проверяет сама СУБД: crypt() хеширует введённый пароль с той же солью
    rows = db("""SELECT id, full_name, is_admin FROM employees
                 WHERE email = %s AND password_hash = crypt(%s, password_hash)""",
              (form.email, form.password))
    if not rows:
        raise HTTPException(401, "Неверный email или пароль")
    token = secrets.token_hex(16)
    cache.setex(f"session:{token}", SESSION_TTL, json.dumps(rows[0]))
    return {"token": token, "user": rows[0]}


@app.post("/api/logout")
def logout(authorization: str = Header(default="")):
    cache.delete(f"session:{authorization.removeprefix('Bearer ')}")
    return {"status": "ok"}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


# ---------- Служебное ----------

@app.get("/api/health")
def health():
    """Проверка работоспособности: доступны ли база данных и Redis."""
    db("SELECT 1")
    cache.ping()
    return {"status": "ok", "host": HOSTNAME}


# ---------- Курсы ----------

class CourseForm(BaseModel):
    title: str
    description: str = ""


@app.get("/api/courses")
def list_courses(response: Response, user: dict = Depends(current_user)):
    cached = cache.get("cache:courses")
    if cached:
        response.headers["X-Cache"] = "HIT"     # ответ взят из Redis
        return json.loads(cached)
    courses = db("SELECT id, title, description FROM courses ORDER BY id")
    cache.setex("cache:courses", CACHE_TTL, json.dumps(courses))
    response.headers["X-Cache"] = "MISS"        # ответ получен из PostgreSQL
    return courses


@app.post("/api/courses", status_code=201)
def create_course(form: CourseForm, user: dict = Depends(admin_only)):
    row = db("INSERT INTO courses (title, description) VALUES (%s, %s) RETURNING id",
             (form.title, form.description))
    cache.delete("cache:courses")   # список изменился — кэш сбрасывается
    return row[0]


# ---------- Сотрудники ----------

class EmployeeForm(BaseModel):
    email: str
    full_name: str
    department: str = ""
    password: str


@app.get("/api/employees")
def list_employees(user: dict = Depends(admin_only)):
    return db("SELECT id, email, full_name, department, is_admin FROM employees ORDER BY full_name")


@app.post("/api/employees", status_code=201)
def create_employee(form: EmployeeForm, user: dict = Depends(admin_only)):
    try:
        row = db("""INSERT INTO employees (email, full_name, department, password_hash)
                    VALUES (%s, %s, %s, crypt(%s, gen_salt('bf'))) RETURNING id""",
                 (form.email, form.full_name, form.department, form.password))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Сотрудник с таким email уже есть") from None
    return row[0]


# ---------- Назначения курсов ----------

class EnrollmentForm(BaseModel):
    employee_id: int
    course_id: int
    deadline: str | None = None   # дата в формате ГГГГ-ММ-ДД


ENROLLMENTS_SQL = """
    SELECT en.id, en.deadline, en.status, en.completed_at,
           e.full_name AS employee, c.title AS course, c.description
    FROM enrollments en
    JOIN employees e ON e.id = en.employee_id
    JOIN courses c ON c.id = en.course_id
"""


@app.get("/api/enrollments")
def list_enrollments(user: dict = Depends(admin_only)):
    return db(ENROLLMENTS_SQL + " ORDER BY e.full_name, c.title")


@app.post("/api/enrollments", status_code=201)
def create_enrollment(form: EnrollmentForm, user: dict = Depends(admin_only)):
    try:
        row = db("INSERT INTO enrollments (employee_id, course_id, deadline) VALUES (%s, %s, %s) RETURNING id",
                 (form.employee_id, form.course_id, form.deadline or None))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Этот курс уже назначен сотруднику") from None
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(404, "Сотрудник или курс не найден") from None
    return row[0]


@app.get("/api/my-courses")
def my_courses(user: dict = Depends(current_user)):
    return db(ENROLLMENTS_SQL + " WHERE en.employee_id = %s ORDER BY en.id", (user["id"],))


@app.post("/api/enrollments/{enrollment_id}/complete")
def complete(enrollment_id: int, user: dict = Depends(current_user)):
    # Условие employee_id = текущий пользователь: отметить можно только свой курс
    rows = db("""UPDATE enrollments SET status = 'completed', completed_at = now()
                 WHERE id = %s AND employee_id = %s RETURNING id""",
              (enrollment_id, user["id"]))
    if not rows:
        raise HTTPException(404, "Назначение не найдено")
    return {"status": "completed"}
