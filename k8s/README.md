# Кластер Kubernetes (kind)

## Схема

```
                 Windows (Docker Desktop)
 ┌──────────────── кластер coursehub (kind) ─────────────────┐
 │  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐ │
 │  │  control-plane   │  │   worker     │  │   worker2    │ │
 │  │ API-сервер, etcd,│  │ поды: api,   │  │ поды: api,   │ │
 │  │ планировщик      │  │ nginx, ...   │  │ nginx, ...   │ │
 │  └──────────────────┘  └──────────────┘  └──────────────┘ │
 │   NodePort 30081 → localhost:8081   30082 → localhost:8082│
 └───────────────────────────────────────────────────────────┘
```

| Файл | Объекты | Назначение |
|---|---|---|
| `kind-config.yaml` | — | состав кластера: 1 управляющий + 2 рабочих узла, проброс портов |
| `app/00-namespace.yaml` | Namespace | пространство имён `coursehub` |
| `app/postgres.yaml` | StatefulSet, Service | БД с постоянным томом |
| `app/redis.yaml` | Deployment, Service | сессии и кэш |
| `app/api.yaml` | Deployment, Service | 3 реплики API |
| `app/nginx.yaml` | Deployment, Service (NodePort) | 2 реплики веб-сервера, вход в кластер |
| `app/adminer.yaml` | Deployment, Service (NodePort) | администрирование БД |
| `app/backup.yaml` | CronJob, PersistentVolumeClaim | резервная копия каждые 5 минут |
| `load-images.ps1` | — | загрузка образов в узлы кластера |

Пароль БД (Secret) и файлы `init.sql` (ConfigMap) создаются командами
из тех же файлов, что и в Swarm, поэтому в манифестах они не дублируются.

## Установка инструментов (один раз)

```powershell
winget install Kubernetes.kind
winget install Kubernetes.kubectl
```

После установки нужно открыть новое окно PowerShell. Проверка: `kind version`, `kubectl version --client`.

## Запуск

Все команды выполняются из корня проекта.

**1. Освободить порты 8081 и 8082** (остановить Swarm-кластер и обычный запуск):

```powershell
docker compose -f swarm/cluster.yaml stop
docker compose down
```

**2. Создать кластер** (первый раз скачивается образ узла, это несколько минут):

```powershell
kind create cluster --config k8s/kind-config.yaml
kubectl get nodes
```

**3. Загрузить образы в узлы кластера:**

```powershell
docker compose build
powershell -ExecutionPolicy Bypass -File k8s\load-images.ps1
```

**4. Создать пространство имён, секрет и конфигурацию:**

```powershell
kubectl apply -f k8s/app/00-namespace.yaml
kubectl config set-context --current --namespace=coursehub
kubectl create secret generic db-password --from-file=password=swarm/db_password.txt
kubectl create configmap db-init --from-file=db/init.sql
```

Вторая команда делает `coursehub` пространством имён по умолчанию, поэтому дальше `-n coursehub` писать не нужно.

**5. Развернуть приложение:**

```powershell
kubectl apply -f k8s/app/
kubectl get pods -o wide
```

Когда у всех подов `STATUS` будет `Running`, а в `READY` — `1/1`, сайт открывается
на http://localhost:8081, Adminer — на http://localhost:8082.

## Демонстрации

```powershell
# все объекты проекта
kubectl get all

# поды и узлы, на которых они работают
kubectl get pods -o wide

# масштабирование
kubectl scale deployment api --replicas=5

# самовосстановление: удалённый под сразу создаётся заново
kubectl delete pod -l app=api --wait=false
kubectl get pods -l app=api

# последовательное обновление, история версий, откат
kubectl rollout restart deployment api
kubectl rollout status deployment api
kubectl rollout history deployment api
kubectl rollout undo deployment api

# вывод узла на обслуживание: поды переезжают на другой узел
# (выбирайте узел без postgres — её том привязан к своему узлу)
kubectl drain coursehub-worker --ignore-daemonsets --delete-emptydir-data
kubectl get pods -o wide
kubectl uncordon coursehub-worker

# DNS внутри кластера: api находит БД по имени сервиса
kubectl exec deploy/api -- python -c "import socket; print(socket.gethostbyname('postgres'))"

# резервное копирование: запуск задачи вне расписания и её журнал
kubectl create job backup-now --from=cronjob/backup
kubectl logs job/backup-now

# журнал API
kubectl logs -l app=api --tail=20
```

## Остановка

```powershell
kind delete cluster --name coursehub
```
