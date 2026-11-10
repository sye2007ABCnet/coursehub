# Кластер Docker Swarm

## Схема

```
                Windows (Docker Desktop)
 ┌──────────────────────── сеть cluster ────────────────────────┐
 │  ┌───────────┐     ┌───────────┐     ┌───────────┐           │
 │  │  manager  │     │  worker1  │     │  worker2  │           │
 │  │ postgres  │     │  api ×N   │     │  api ×N   │           │
 │  │ backup    │     │  nginx…   │     │  nginx…   │  registry │
 │  └───────────┘     └───────────┘     └───────────┘  :5000    │
 │        └──── оверлейные сети frontend / backend ────┘        │
 └──────────────────────────────────────────────────────────────┘
   :8081 сайт   :8082 Adminer   :8083 сайт через worker1
```

Узлы кластера — контейнеры Docker-in-Docker (файл `cluster.yaml`).
Приложение описано в файле `stack.yaml`.

## Запуск

Все команды выполняются в PowerShell из корня проекта.

**1. Остановить обычный запуск через compose**, чтобы освободить порты 8081 и 8082:

```powershell
docker compose down
docker compose build          # образы coursehub-api и coursehub-nginx должны быть собраны
```

**2. Запустить узлы кластера и реестр образов:**

```powershell
docker compose -f swarm/cluster.yaml up -d
docker ps
```

**3. Отправить образы в реестр кластера:**

```powershell
powershell -ExecutionPolicy Bypass -File swarm\push-images.ps1
```

В конце скрипт выведет список образов в реестре.

**4. Объединить узлы в кластер:**

```powershell
docker exec manager docker swarm init
$token = docker exec manager docker swarm join-token -q worker
docker exec worker1 docker swarm join --token $token manager:2377
docker exec worker2 docker swarm join --token $token manager:2377
docker exec manager docker node ls
```

**5. Развернуть приложение:**

```powershell
docker exec manager docker stack deploy -c /project/swarm/stack.yaml coursehub
docker exec manager docker stack services coursehub
```

Через минуту в колонке REPLICAS у всех сервисов должно быть `N/N`.
После этого сайт открывается на http://localhost:8081, Adminer — на http://localhost:8082.

> Чтобы не писать каждый раз `docker exec manager docker`, можно задать сокращение:
> `function swarm { docker exec manager docker @args }`, а затем писать, например, `swarm node ls`.

## Демонстрации

```powershell
# на каких узлах работают реплики
docker exec manager docker service ps coursehub_api

# балансировка: в подвале сайта меняется имя контейнера при обновлении страницы
# routing mesh: сайт открывается и через рабочий узел — http://localhost:8083

# масштабирование
docker exec manager docker service scale coursehub_api=5

# отказ узла: реплики с worker1 переносятся на worker2
docker stop worker1
docker exec manager docker node ls
docker exec manager docker service ps coursehub_api
docker start worker1

# последовательное обновление (rolling update) без остановки сайта
docker exec manager docker service update --force coursehub_api

# секреты: пароль БД не виден в переменных окружения сервиса
docker exec manager docker secret ls
docker exec manager docker service inspect coursehub_api --format "{{json .Spec.TaskTemplate.ContainerSpec.Env}}"

# оверлейные сети
docker exec manager docker network ls --filter driver=overlay
```

## Остановка

```powershell
docker exec manager docker stack rm coursehub     # удалить приложение
docker compose -f swarm/cluster.yaml down         # остановить узлы (состояние сохранится)
docker compose -f swarm/cluster.yaml down -v      # удалить узлы полностью
```
