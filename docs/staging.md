# Тестовое окружение ЛР6

Окружение library-staging размещается на ВМ library-app.
Адрес приложения: http://192.168.56.10:18000.

## Изоляция

- Compose-файл: compose.staging.yaml.
- Имя проекта: library-staging.
- Отдельный том БД: library-staging_postgres_data.
- PostgreSQL не публикует порт на хосте.
- Действующий проект library-production использует отдельные ресурсы.

Не переопределять имя staging-проекта через -p или COMPOSE_PROJECT_NAME.

## Образ и настройки

Приложение использует образ ghcr.io/ssofpv/library-devops
с обязательным APP_IMAGE_TAG. Сборка приложения в staging не предусмотрена.

Шаблон настроек: deploy/staging.env.example.
Реальные секреты хранятся отдельно на сервере и не добавляются в Git.
Пустые секреты в шаблоне необходимо заполнить перед запуском.

## Проверка конфигурации

На ВМ из папки с файлами проекта:

```bash
sudo env \
  DJANGO_SECRET_KEY=config-check-only \
  POSTGRES_PASSWORD=config-check-only \
  docker compose --env-file deploy/staging.env.example \
  -f compose.staging.yaml config --quiet
```

Временные значения используются только для разбора конфигурации.
Команда не запускает контейнеры и не проверяет доступность образа.

## Состояние

Конфигурация проверена на library-app, код завершения — 0.
Развертывание, миграции, доступ к GHCR и приемка приложения
проверяются на следующем этапе.