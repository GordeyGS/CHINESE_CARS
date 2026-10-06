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

После загрузки demo-данных интерфейс доступен по <http://127.0.0.1:8000/>. Основные разделы: `/brands/`, `/cars/`, `/articles/`, `/technologies/` и `/search/`. Для демонстрации поиска подходят запросы `BYD`, `Blade Battery`, `Zeekr 001`, `электромобиль` и `Какие электромобили BYD используют Blade Battery?`.

Поисковые поля предлагают локальный autocomplete после двух введённых символов. JSON endpoint `/search/suggest/?q=...` не вызывает Tavily. Для демонстрации исправления опечаток используйте `Zeek 001` или `Balde Battery`: система предложит близкий термин, не меняя запрос автоматически.

### Внешний поиск

Текущая интернет-выдача использует официальный Tavily Search API. Перед запуском задайте переменные окружения:

```bash
export EXTERNAL_SEARCH_PROVIDER=tavily
export EXTERNAL_SEARCH_API_KEY=your-tavily-api-key
```

Дополнительно при необходимости настраиваются `EXTERNAL_SEARCH_ENDPOINT`, `EXTERNAL_SEARCH_TIMEOUT_SECONDS`, `EXTERNAL_SEARCH_LIMIT` и `EXTERNAL_SEARCH_LANGUAGE`; для Tavily используются безопасные значения по умолчанию. Django не загружает `.env` автоматически: при ручном запуске переменные нужно экспортировать в окружение. Если провайдер или ключ отсутствует, приложение использует `NullExternalSearchProvider`: внутренний поиск продолжает работать, а сетевой запрос не выполняется.

Настройки читаются из переменных окружения. Список переменных приведён в `.env.example`; файл `.env` намеренно не отслеживается Git. Django не загружает `.env` самостоятельно, поэтому значения следует экспортировать в окружение или передать средствами IDE/контейнера. Для локального запуска без отдельного `.env` используются безопасно ограниченные development-значения, совпадающие с `compose.yaml`.

## Проверки

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check
.venv/bin/python manage.py migrate
.venv/bin/pytest
```

PostgreSQL является единственной настроенной СУБД. Автоматического переключения на SQLite нет.

## Реализованные этапы

Этап 1 включает модели данных, Django Admin, миграции, demo-команду и модельные тесты. На этапе 2 добавлены внутренний PostgreSQL Full Text Search, `pg_trgm`, поиск слова/фразы/предложения, ранжирование и адаптивная выдача с группами `Articles`, `Cars`, `Technologies`, `Videos`. На этапе 3 реализованы `ExternalSearchProvider`, текущий адаптер Tavily Search API, дополнительный адаптер Brave Search API, `NullExternalSearchProvider` и отдельная группа `External results`. На этапе 4 добавлены единый Bootstrap 5 layout, главная, каталоги и detail pages марок, моделей, модификаций, технологий и статей, базовые фильтры и пользовательская аутентификация.

Сравнение и механизм рекомендаций остаются следующими этапами.
