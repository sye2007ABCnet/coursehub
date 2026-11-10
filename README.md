# CourseHub — платформа для управления обучающими курсами

Учебный проект курсовой работы «Настройка и администрирование платформы для
управления обучающими курсами в корпоративной среде».

## Контейнеры

| № | Контейнер | Образ | Назначение |
|---|---|---|---|
| 1 | nginx | свой (nginx:1.30-alpine) | веб-сервер: отдаёт страницу, передаёт `/api/` в api |
| 2 | api | свой (python:3.12-slim) | серверная часть на FastAPI |
| 3 | postgres | postgres:17-alpine | база данных |
| 4 | redis | redis:8.2-alpine | сессии пользователей и кэш списка курсов |
| 5 | backup | postgres:17-alpine | резервное копирование БД по расписанию |
| 6 | adminer | adminer:6.3.0 | веб-интерфейс для администрирования БД |

## Структура

```
coursehub/
├── .github/workflows/ci-cd.yml  конвейер CI/CD
├── compose.yaml        описание всех контейнеров, сетей и томов
├── .env.example        шаблон настроек (порты, пароли)
├── backup.sh           скрипт резервного копирования
├── swarm/              кластер Docker Swarm (см. swarm/README.md)
│   ├── cluster.yaml    узлы кластера (manager, worker1, worker2) и реестр образов
│   ├── stack.yaml      приложение для развёртывания в кластере
│   ├── push-images.ps1 отправка образов в реестр кластера
│   └── db_password.txt секрет: пароль БД (в Git не добавляется)
├── k8s/                кластер Kubernetes (см. k8s/README.md)
│   ├── kind-config.yaml  узлы кластера kind (1 управляющий + 2 рабочих)
│   ├── load-images.ps1   загрузка образов в узлы кластера
│   └── app/              манифесты приложения
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py         весь код API
├── db/
│   └── init.sql        создание таблиц и начальных данных
└── nginx/
    ├── Dockerfile
    ├── nginx.conf
    └── html/           интерфейс: index.html, app.js
```

## Запуск

```powershell
copy .env.example .env
docker compose up -d --build
docker compose ps
```

- Сайт: http://localhost:8081
- Adminer: http://localhost:8082
- Учётные записи: `admin@corp.local` / `admin123` (администратор),
  `ivanov@corp.local` / `employee123` (сотрудник).

Остановка: `docker compose down`. Удаление вместе с данными БД: `docker compose down -v`.

## Adminer

На странице входа указать:

| Поле | Значение |
|---|---|
| Движок | PostgreSQL |
| Сервер | postgres (подставлен автоматически) |
| Имя пользователя | значение POSTGRES_USER из .env |
| Пароль | значение POSTGRES_PASSWORD из .env |
| База данных | значение POSTGRES_DB из .env |

## Резервные копии

Копии появляются в папке `backups` проекта каждые `BACKUP_INTERVAL` секунд,
копии старше 7 дней удаляются.

```powershell
docker compose logs backup                       # журнал копирования
# восстановление из копии (имя файла подставить своё)
docker compose exec backup pg_restore --clean -d coursehub /backups/coursehub_2026-11-04_20-00-00.dump
```

## Полезные команды

```powershell
docker compose logs -f api                       # журнал api
docker compose up -d --scale api=3               # три реплики api
docker compose restart nginx                     # nginx узнаёт адреса новых реплик
docker network inspect coursehub_backend         # кто подключён к внутренней сети
docker compose exec redis redis-cli keys "*"     # сессии и кэш в Redis
```

## CI/CD (GitHub Actions)

Конвейер описан в файле `.github/workflows/ci-cd.yml` и запускается при каждой
отправке изменений в ветку `main`.

| Этап | Где выполняется | Что делает |
|---|---|---|
| lint | серверы GitHub | проверяет код Python (ruff), Dockerfile (hadolint), compose.yaml и манифесты Kubernetes (kubeconform) |
| test | серверы GitHub | запускает все контейнеры через `docker compose` и проверяет вход, список курсов и отказ при неверном пароле |
| build | серверы GitHub | собирает образы api и nginx и публикует их в GitHub Container Registry с тегами `sha-<коммит>` и `latest` |
| deploy | ваш компьютер (self-hosted runner) | скачивает новые образы, загружает их в кластер kind и выполняет последовательное обновление |

Если любой этап завершился ошибкой, следующие не выполняются: непроверенный код не попадёт в кластер.

### Настройка (один раз)

**1. Создать репозиторий на GitHub** и отправить в него проект:

```powershell
git init
git add .
git commit -m "CourseHub"
git branch -M main
git remote add origin https://github.com/<логин>/coursehub.git
git push -u origin main
```

Этапы lint, test и build начнут выполняться сразу (вкладка **Actions**). Этап deploy будет ждать раннер.

**2. Установить self-hosted runner** — программу, которая выполняет задания GitHub на вашем компьютере:

1. В репозитории: **Settings → Actions → Runners → New self-hosted runner**, выбрать **Windows, x64**.
2. GitHub покажет команды. Выполнить их в PowerShell в отдельной папке, например `C:\actions-runner`
   (скачивание архива, распаковка, `config.cmd --url ... --token ...`). На вопросы мастера настройки можно отвечать Enter.
3. На вопрос о запуске в виде службы (run as service) ответить **N**.
4. Запустить раннер: `.\run.cmd`. Окно должно оставаться открытым, в нём появится `Listening for Jobs`.

Раннер запускается от имени вашего пользователя, поэтому ему доступны Docker Desktop, kind и kubectl.
Кластер kind с развёрнутым приложением должен быть запущен (см. `k8s/README.md`).

### Проверка

Внести любое изменение, например заголовок в `nginx/html/index.html`, затем:

```powershell
git commit -am "Изменён заголовок"
git push
```

Во вкладке **Actions** видно выполнение всех этапов. После завершения обновлённая страница
открывается на http://localhost:8081, а команда `kubectl get pods` показывает новые поды.
