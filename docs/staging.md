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
  ghcr.io/ssofpv/library-devops:66e0572d90faf390ce4061361c4b5c3ce27a4747.
- Создан отдельный том library-staging_postgres_data.
- Настройки действующего CD хранятся в /opt/library-staging/.env.staging
  с правами 600, вне Git и образа.
- Миграции применены успешно.
- Контейнеры app и db имеют статус healthy.
- GET http://192.168.56.10:18000/health/ возвращает {"status": "ok"}.
- GET /version/ возвращает 66e0572d90faf390ce4061361c4b5c3ce27a4747.
- Проверены вход и создание книги, филиала и экземпляра LR6-001.
- Экземпляр отображается в списке после сохранения.

PR #97 добавил конфигурацию окружения.
Результаты запуска зафиксированы в Issue #96.

Результаты на 04.11.2026 подтверждены выводом команд и скриншотами Софьи:

- PR #100 добавил /version/; публикация Actions №190 и ручной запуск проверены.
- PR #102 добавил CD, одобрен Полиной и слит в main.
- Actions №193 для push main 66e0572… успешно опубликовал образ и выполнил
  автоматическое развёртывание с приёмкой через Tailscale и library-deploy.
- Неверный тег, отсутствующая переменная, недоступный registry, конфликтующий
  запуск, неуспешный healthcheck и сломанная страница экземпляров проверены
  вручную тем же серверным сценарием. Во всех случаях выпуск отклонён с кодом 1.
- После неудачных выпусков выполнен возврат на 56e6ade… с успешной приёмкой.
- В завершение восстановлена 66e0572…; приёмка успешна, LR6-001 виден в браузере
  с книгой «Проверка релиза ЛР6», филиалом «Тестовый филиал ЛР6» и статусом «Доступен».
- Issue #99 и Issue #101 закрыты. Инструкция и подробности экспериментов:
  [staging-cd.md](staging-cd.md).

Рабочая конфигурация CD находится в /opt/library-staging и принадлежит root.
Папка ~/lr6-staging-check сохранилась от первоначального ручного запуска;
её .env.staging не синхронизируется с каждым автоматическим выпуском.
Команды ниже документируют первый запуск и не заменяют текущую процедуру CD.

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
