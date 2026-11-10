# Загрузка образов в узлы кластера kind.
# Узлы не скачивают образы из интернета: они копируются с компьютера.
# Запуск из корня проекта:
#   powershell -ExecutionPolicy Bypass -File k8s\load-images.ps1

# Собственным образам присваивается версия 1.0
docker tag coursehub-api coursehub-api:1.0
docker tag coursehub-nginx coursehub-nginx:1.0

$images = "coursehub-api:1.0", "coursehub-nginx:1.0", "postgres:17-alpine", "redis:8.2-alpine", "adminer:6.3.0"

foreach ($image in $images) {
    Write-Host "Загрузка $image"
    docker save --platform linux/amd64 -o image.tar $image
    kind load image-archive image.tar --name coursehub
}
Remove-Item image.tar
