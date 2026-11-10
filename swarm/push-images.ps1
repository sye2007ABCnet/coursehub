# Отправка образов проекта в реестр кластера (localhost:5000).
# Запуск из корня проекта:
#   powershell -ExecutionPolicy Bypass -File swarm\push-images.ps1

# локальное имя образа  ->  имя в реестре
$images = [ordered]@{
    "coursehub-api"      = "coursehub-api:1.0"
    "coursehub-nginx"    = "coursehub-nginx:1.0"
    "postgres:17-alpine" = "postgres:17-alpine"
    "redis:8.2-alpine"   = "redis:8.2-alpine"
    "adminer:6.3.0"      = "adminer:6.3.0"
}

foreach ($source in $images.Keys) {
    $target = "localhost:5000/" + $images[$source]
    docker tag $source $target
    docker push --platform linux/amd64 $target
}

# Список образов в реестре
curl.exe -s http://localhost:5000/v2/_catalog
