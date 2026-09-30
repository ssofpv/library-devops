.RECIPEPREFIX := >

ifeq ($(OS),Windows_NT)
PYTHON ?= .venv/Scripts/python.exe
else
PYTHON ?= .venv/bin/python
endif

.PHONY: setup run migrate backup restore test quality format verify

setup:
>$(PYTHON) -m pip install -r requirements-dev.txt
>$(PYTHON) manage.py migrate

run:
>$(PYTHON) manage.py runserver

migrate:
>$(PYTHON) manage.py migrate

BACKUP_DIR ?= backups
BACKUP_FILE ?= $(BACKUP_DIR)/db.sqlite3.backup

backup:
>$(PYTHON) -c "from pathlib import Path; import shutil; src=Path('db.sqlite3'); dst=Path('$(BACKUP_FILE)'); assert src.exists(), 'Database db.sqlite3 not found'; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); print(f'Backup created: {dst}')"

restore:
>$(PYTHON) -c "from pathlib import Path; import shutil; src=Path('$(BACKUP_FILE)'); dst=Path('db.sqlite3'); assert src.exists(), f'Backup not found: {src}'; shutil.copy2(src, dst); print(f'Database restored from: {src}')"

test:
>$(PYTHON) -m coverage erase
>$(PYTHON) -m coverage run manage.py test --settings=config.settings_test
>$(PYTHON) -m coverage report
>$(PYTHON) -m coverage xml

quality:
>$(PYTHON) -m ruff check .
>$(PYTHON) -m ruff format --check .

format:
>$(PYTHON) -m ruff check . --select I --fix
>$(PYTHON) -m ruff format .

verify:
>$(MAKE) quality
>$(PYTHON) manage.py check
>$(PYTHON) manage.py makemigrations --check --dry-run
>$(MAKE) test