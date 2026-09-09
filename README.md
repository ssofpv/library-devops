# library-devops
Учебный проект «Библиотека» по дисциплине «Методология и практики DevOps»

## Документация

[Описание проекта «Библиотека»](docs/project-description.md)
[Правила внесения изменений](CONTRIBUTING.md)

## Текущее состояние

Создан каркас приложения на Django и Django REST Framework.

Реализован служебный адрес GET /health/.
Он проверяет, что приложение отвечает на HTTP-запросы.
Доступность базы данных этот адрес не проверяет.

Добавлены два автоматических теста:
- успешный GET-запрос к /health/;
- запрет POST-запроса к /health/.

Предметные модули библиотеки пока не реализованы.
Сейчас используется стандартная настройка SQLite.
Команды make и CI пока не настроены.

## Локальный запуск в Windows PowerShell

Все команды выполняются из основной папки репозитория,
в которой находится manage.py.

### 1. Создание виртуального окружения

```powershell
py -m venv .venv
```

Если окружение .venv уже создано, повторять этот шаг не нужно.

### 2. Установка зависимостей

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Настройка окружения

Если файла .env ещё нет, создайте его из образца:

```powershell
Copy-Item .env.example .env
```

Сгенерируйте собственный секретный ключ:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Откройте .env и вставьте полученное значение после DJANGO_SECRET_KEY=.
Не публикуйте ключ и не добавляйте .env в Git.

### 4. Подготовка стандартных таблиц базы данных

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Команда создаёт стандартные таблицы Django в локальной SQLite-базе.
Модели авторов, книг, филиалов и экземпляров пока не добавлены.

### 5. Проверка конфигурации

```powershell
.\.venv\Scripts\python.exe manage.py check
```

### 6. Запуск сервера

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Откройте http://127.0.0.1:8000/health/

Ожидаемый ответ:

```json
{"status": "ok"}
```

Главная страница по адресу / пока не реализована и возвращает 404.

Для остановки сервера нажмите Ctrl+C в терминале.

## Автоматические тесты

```powershell
.\.venv\Scripts\python.exe manage.py test config
```

Ожидаемый результат: два теста завершились успешно, в конце вывода — OK.