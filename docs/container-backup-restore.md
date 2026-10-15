# Резервное копирование и восстановление PostgreSQL в контейнерах

Инструкция для Bash на учебной ВМ library-app, из корня проекта.
Исходный Compose-проект — `library-lr4-check`, файл секретов — `.env.container`.
Это отдельное окружение; PostgreSQL на прежней ВМ library-db здесь не изменяется.
Пароли, файл `.env.container` и архивы с данными не включаются в Git.

## 1. Предварительная проверка

Перед созданием окружения восстановления выполнить:

```bash
sudo -v
make container-check DOCKER="sudo -n docker"
```

Продолжать только после `CONTAINER_CHECK_OK` и возврата команды без ошибки.
Далее все команды выполняются в одной SSH-сессии. При любой ошибке остановиться:
не переходить к следующему блоку и не считать частичный файл резервной копией.
Если `sudo -n` сообщает об истёкшем подтверждении прав, выполнить `sudo -v`.

```bash
set -o pipefail
umask 077
source_compose() {
    sudo -n docker compose --env-file .env.container -f compose.yaml -p library-lr4-check "$@"
}
source_compose ps -a
```

Ожидаются существующие app и db со статусом healthy. Не менять имя исходного
проекта или параметры подключения к его БД в ходе процедуры.

## 2. Создание резервной копии

Для сравнимого снимка остановить исходное приложение. Других писателей в эту
учебную БД во время копирования быть не должно. БД продолжает работать.

```bash
source_compose stop app
mkdir -p backups
BACKUP_DIR=$(mktemp -d backups/manual-postgres-XXXXXXXX)
BACKUP="$BACKUP_DIR/postgres.dump"
source_compose run --rm --no-deps -T app python manage.py dumpdata --all | sha256sum > "$BACKUP_DIR/django-before.sha256"
source_compose exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP.partial"
```

После успешного pg_dump проверить читаемость оглавления архива:

```bash
source_compose exec -T db pg_restore --list < "$BACKUP.partial" > /dev/null
```

Только если обе команды завершились без ошибок:

```bash
mv "$BACKUP.partial" "$BACKUP"
printf 'Backup: %s\n' "$BACKUP"
cat "$BACKUP_DIR/django-before.sha256"
source_compose start app
```

`pg_restore --list` подтверждает читаемость формата, но не заменяет пробное
восстановление. При ошибке приложение может остаться остановленным: сначала
выяснить причину. Успешный файл называется postgres.dump, а не postgres.dump.partial.
Архив и контрольный отпечаток сохраняются на ВМ с закрытыми правами доступа.

## 3. Новый проект и отдельный volume для восстановления

Создать уникальное имя и проверить, что у него ещё нет контейнеров или volumes:

```bash
RESTORE_PROJECT="library-restore-$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
printf 'Restore project: %s\n' "$RESTORE_PROJECT"
sudo -n docker ps -a --filter "label=com.docker.compose.project=$RESTORE_PROJECT"
sudo -n docker volume ls --filter "label=com.docker.compose.project=$RESTORE_PROJECT"
```

В обоих списках должны быть только заголовки. Если объекты найдены, остановиться;
не удалять их и не восстанавливать в них данные.

```bash
restore_compose() {
    sudo -n docker compose --env-file .env.container -f compose.yaml -p "$RESTORE_PROJECT" "$@"
}
restore_compose up -d db
restore_compose ps -a
```

Дождаться статуса db healthy. Если статус starting, повторить только
`restore_compose ps -a` через несколько секунд. При unhealthy или exited
остановиться и прочитать `restore_compose logs --tail 50 db`.

Compose создаёт новый volume с именем `${RESTORE_PROJECT}_postgres_data`.
Используется тот же проверенный compose.yaml без external-volume и фиксированного
имени volume. Исходный `library-lr4-check_postgres_data` не подключается.
Порт БД не публикуется; постоянный сервис app в проекте восстановления не запускается.

## 4. Восстановление и сравнение

После готовности новой БД:

```bash
restore_compose exec -T db sh -c 'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --single-transaction' < "$BACKUP"
```

Только после успешного pg_restore проверить миграции и данные без запуска
веб-сервера и публикации его порта:

```bash
restore_compose run --rm --no-deps -T app python manage.py migrate --check
restore_compose run --rm --no-deps -T app python manage.py dumpdata --all | sha256sum > "$BACKUP_DIR/django-restored.sha256"
diff "$BACKUP_DIR/django-before.sha256" "$BACKUP_DIR/django-restored.sha256"
```

Нулевой код diff и отсутствие вывода означают совпадение отпечатков всех
сериализованных Django-данных на момент backup. Это не побайтовое сравнение
файлов PostgreSQL и не проверка нагрузочной производительности.
При расхождении остановиться и разобраться; не переписывать исходную БД.

Восстановление используется с тем же образом приложения, который соответствовал
backup. Если образ уже заменён или схема изменилась, сначала подобрать
соответствующую версию; не выполнять новые миграции ради сокрытия расхождения.

## 5. Завершение проверки

Остановить окружение восстановления, сохранив его volume для демонстрации:

```bash
restore_compose down
source_compose ps -a
curl --max-time 10 -i http://127.0.0.1:18000/health/
```

Ожидаются app и db исходного проекта healthy и HTTP 200.
При необходимости дать приложению время на запуск и повторить проверку.
Не добавлять `--volumes`: эта инструкция не удаляет ни исходный, ни восстановленный volume.

Сохранить для отчёта путь backup, имя проекта восстановления, оба отпечатка,
успешную проверку миграций и итоговый HTTP-ответ. Сами данные и секреты не публиковать.

## Откат после обновления приложения

Команда container-update сохраняет PostgreSQL backup перед миграциями и
previous-app-image.txt с прежним image ID. Автоматического отката нет.
Старый образ сам по себе не отменяет миграции. При неудачном обновлении сначала
остановить запись в БД, определить совместимую версию приложения и схемы,
проверить восстановление backup в отдельном volume, затем подготовить отдельный
план переключения. Не выполнять пробный pg_restore поверх исходной базы.
