.RECIPEPREFIX := >

ifeq ($(OS),Windows_NT)
PYTHON ?= .venv/Scripts/python.exe
else
PYTHON ?= .venv/bin/python
endif

.PHONY: setup run migrate test quality format verify

setup:
>$(PYTHON) -m pip install -r requirements-dev.txt

run:
>$(PYTHON) manage.py runserver

migrate:
>$(PYTHON) manage.py migrate

test:
>$(PYTHON) -m coverage erase
>$(PYTHON) -m coverage run manage.py test
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