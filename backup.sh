#!/bin/sh
# Резервное копирование базы данных.
# Параметры подключения (PGHOST, PGUSER, PGPASSWORD, PGDATABASE) pg_dump
# берёт из переменных окружения, заданных в compose.yaml.

# В кластере Swarm пароль передаётся секретом (файлом), а не переменной окружения
if [ -f /run/secrets/db_password ]; then
    PGPASSWORD=$(cat /run/secrets/db_password)
    export PGPASSWORD
fi

echo "Резервное копирование запущено, интервал ${BACKUP_INTERVAL} с"

while true; do
    FILE="/backups/coursehub_$(date +%Y-%m-%d_%H-%M-%S).dump"

    # -Fc: сжатый формат, из которого БД восстанавливается командой pg_restore
    if pg_dump -Fc -f "$FILE"; then
        echo "Создана копия: $FILE"
    else
        echo "Ошибка резервного копирования"
        rm -f "$FILE"
    fi

    # Копии старше 7 дней удаляются
    find /backups -name "*.dump" -mtime +7 -delete

    sleep "$BACKUP_INTERVAL"
done
