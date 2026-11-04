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

## Проверенное состояние

На ВМ library-app запущен отдельный проект library-staging.

- Образ приложения получен из GHCR без сборки на сервере:
  ghcr.io/ssofpv/library-devops:56e6adeaf3a8108799f5f1b6e67903fe4cf5f15b.
- Создан отдельный том library-staging_postgres_data.
- Реальные настройки хранятся в ~/lr6-staging-check/.env.staging
  с правами 600, вне Git и образа.
- Миграции применены успешно.
- Контейнеры app и db имеют статус healthy.
- GET http://192.168.56.10:18000/health/ возвращает {"status": "ok"}.
- Проверены вход и создание книги, филиала и экземпляра LR6-001.
- Экземпляр отображается в списке после сохранения.

PR #97 добавил конфигурацию окружения.
Результаты запуска зафиксированы в Issue #96.

После PR #100 и успешного Actions №190 вручную развёрнута версия 56e6adeaf3a8108799f5f1b6e67903fe4cf5f15b. Проверены /version/, /health/, вход и сохранность LR6-001. Issue #99 закрыт. Автоматическое CD готовится в Issue #101; его запуск и откат ещё не подтверждены. Инструкция: [staging-cd.md](staging-cd.md). Для CD подготовлена отдельная закрытая копия настроек в /opt/library-staging; ручные команды ниже относятся к прежней папке запуска.

## Команды первого запуска

Команды выполняются на library-app из ~/lr6-staging-check.
Перед запуском должен быть подготовлен .env.staging с отдельными
секретами и настройками тестовой базы. Секреты не публикуются.

Получение готовых образов:

```bash
sudo docker compose --env-file .env.staging -f compose.staging.yaml pull

```

Запуск тестовой БД:

```bash
sudo docker compose --env-file .env.staging -f compose.staging.yaml up -d --wait db
```

Применение миграций к тестовой БД:

```bash
sudo docker compose --env-file .env.staging -f compose.staging.yaml run --rm --no-deps --pull never app python manage.py migrate --noinput
```

Запуск приложения без сборки:

```bash
sudo docker compose --env-file .env.staging -f compose.staging.yaml up -d --no-build --pull never --wait app
```

Проверка доступности:

```bash
curl --fail --show-error --max-time 10 http://192.168.56.10:18000/health/
```

После запуска необходимо отдельно проверить вход и основной
пользовательский сценарий. Статус healthy не заменяет эту проверку.