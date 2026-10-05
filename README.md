# Chinese automotive industry knowledge base

Учебный Django-проект базы знаний по китайскому автопрому.

## Локальный запуск

Требуются Python 3.12+ и Docker.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
docker compose up -d db
.venv/bin/python manage.py migrate
.venv/bin/python manage.py load_demo_data
.venv/bin/python manage.py runserver
```

Настройки читаются из переменных окружения. Список переменных приведён в `.env.example`; файл `.env` намеренно не отслеживается Git. Django не загружает `.env` самостоятельно, поэтому значения следует экспортировать в окружение или передать средствами IDE/контейнера. Для локального запуска без отдельного `.env` используются безопасно ограниченные development-значения, совпадающие с `compose.yaml`.

## Проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check
.venv/bin/python manage.py migrate
.venv/bin/pytest
```

PostgreSQL является единственной настроенной СУБД. Автоматического переключения на SQLite нет.

## Границы этапа 1

Реализованы модели данных, Django Admin, миграции, demo-команда и модельные тесты. Полнотекстовый поиск, внешний поисковый API, пользовательский frontend, сравнение и механизм рекомендаций отложены на следующие этапы.
