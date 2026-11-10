// Клиентская часть: обращается к API по адресу /api/... через nginx

let token = localStorage.getItem("token");

// Отправка запроса к API с токеном авторизации
async function api(path, method = "GET", body = null) {
  const resp = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
    body: body ? JSON.stringify(body) : null,
  });
  document.getElementById("served-by").textContent = resp.headers.get("X-Served-By");
  const data = await resp.json();
  if (!resp.ok) {
    if (path !== "/me") alert(data.detail);   // при проверке сохранённого входа ошибку не показываем
    throw new Error(data.detail);
  }
  return data;
}

// Защита от вставки HTML-кода в данные
function esc(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

// Построение таблицы: headers — заголовки, rows — массив строк (массивов ячеек)
function table(id, headers, rows) {
  document.getElementById(id).innerHTML =
    "<tr>" + headers.map((h) => `<th>${h}</th>`).join("") + "</tr>" +
    rows.map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") + "</tr>").join("");
}

function value(id) {
  return document.getElementById(id).value;
}

// ---------- Вход и выход ----------

async function login() {
  const data = await api("/login", "POST", { email: value("email"), password: value("password") });
  token = data.token;
  localStorage.setItem("token", token);
  showPage(data.user);
}

async function logout() {
  await api("/logout", "POST");
  localStorage.removeItem("token");
  location.reload();
}

function showPage(user) {
  document.getElementById("login").classList.add("hidden");
  document.getElementById("userbox").classList.remove("hidden");
  document.getElementById("username").textContent = user.full_name;
  if (user.is_admin) {
    document.getElementById("admin").classList.remove("hidden");
    loadAdmin();
  } else {
    document.getElementById("employee").classList.remove("hidden");
    loadMyCourses();
  }
}

// ---------- Страница сотрудника ----------

async function loadMyCourses() {
  const items = await api("/my-courses");
  table("my-courses", ["Курс", "Описание", "Срок", "Статус"], items.map((e) => [
    esc(e.course), esc(e.description), e.deadline || "—",
    e.status === "completed"
      ? '<span class="done">пройден</span>'
      : `<button onclick="complete(${e.id})">Отметить пройденным</button>`,
  ]));
}

async function complete(id) {
  await api(`/enrollments/${id}/complete`, "POST");
  loadMyCourses();
}

// ---------- Страница администратора ----------

async function loadAdmin() {
  const courses = await api("/courses");
  const employees = await api("/employees");
  const enrollments = await api("/enrollments");

  table("courses", ["№", "Название", "Описание"], courses.map((c) => [c.id, esc(c.title), esc(c.description)]));
  table("employees", ["ФИО", "Email", "Подразделение"],
    employees.map((e) => [esc(e.full_name), esc(e.email), esc(e.department)]));
  table("enrollments", ["Сотрудник", "Курс", "Срок", "Статус"], enrollments.map((e) => [
    esc(e.employee), esc(e.course), e.deadline || "—", e.status === "completed" ? "пройден" : "назначен",
  ]));

  document.getElementById("en-employee").innerHTML = employees.filter((e) => !e.is_admin)
    .map((e) => `<option value="${e.id}">${esc(e.full_name)}</option>`).join("");
  document.getElementById("en-course").innerHTML = courses
    .map((c) => `<option value="${c.id}">${esc(c.title)}</option>`).join("");
}

async function addCourse() {
  await api("/courses", "POST", { title: value("course-title"), description: value("course-desc") });
  loadAdmin();
}

async function addEmployee() {
  await api("/employees", "POST", {
    full_name: value("emp-name"), email: value("emp-email"),
    department: value("emp-dept"), password: value("emp-pass"),
  });
  loadAdmin();
}

async function addEnrollment() {
  await api("/enrollments", "POST", {
    employee_id: Number(value("en-employee")), course_id: Number(value("en-course")),
    deadline: value("en-deadline") || null,
  });
  loadAdmin();
}

// При открытии страницы: если токен сохранён, пользователь уже вошёл
if (token) {
  api("/me").then(showPage).catch(() => localStorage.removeItem("token"));
}
