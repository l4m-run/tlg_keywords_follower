# План тестирования проекта tlg_keywords_follower

## 1. Инструменты и стек

* **Фреймворк:** `pytest` (стандарт де-факто для Python).
* **Асинхронность:** `pytest-asyncio` (так как используется Telethon).
* **Мокинг:** `unittest.mock` (встроенный) + `pytest-mock` (обертка).
* **Покрытие:** `pytest-cov` (для отчета о покрытии кода).

## 2. Структура тестов

Создаем директорию `tests/` в корне проекта:

```text
tests/
├── __init__.py
├── conftest.py          # Общие фикстуры (mock client, mock config)
├── test_config.py       # Тесты ConfigManager
├── test_queue.py        # Тесты QueueManager
├── test_handlers.py     # Тесты логики обработчиков
└── test_commands.py     # Тесты команд управления
```

## 3. Объекты тестирования

### 3.1. ConfigManager (`app/config_manager.py`)

* **Unit-тесты:**
  * Загрузка валидного `config.json`.
  * Создание дефолтного конфига, если файла нет.
  * Парсинг строк правил из `rules.txt` (разные форматы, с названиями групп и без).
  * Валидация `monitored_chats` (удаление дубликатов и protection loop).
  * Добавление/удаление чатов в мониторинг.

### 3.2. QueueManager (`app/queue_manager.py`)

* **Unit-тесты:**
  * Добавление сообщения в очередь (проверка создания JSON файла).
  * Корректность структуры JSON (наличие message_id, chat_id и т.д.).
  * Чтение очереди (сортировка по времени).
* **Integration/Mock тесты:**
  * Симуляция `process_queue` с мокированным клиентом.
  * Проверка вызова `client.send_message` / `client.forward_messages`.
  * Обработка `FloodWaitError` (должен ждать и не удалять файл сразу).
  * Удаление файла после успешной отправки.

### 3.3. Handlers (`app/handlers.py`)

* **Unit-тесты (логика):**
  * Функция `check_message_against_rules`:
    * Совпадение по ключевым словам.
    * Проверка регистра (`case_sensitive`).
    * Частичное совпадение слов (если реализовано) или точное.
  * Функция `get_unique_target_chats` (дедупликация).
* **Flow тесты:**
  * Симуляция `NewMessage` события.
  * Проверка, что сообщение от мониторимого чата попадает в очередь.
  * Проверка, что чужие сообщения игнорируются.

### 3.4. Commands (`app/commands.py`)

* **Unit-тесты:**
  * Проверка парсинга аргументов команд.
  * Проверка формирования текста ответа (например, для `/rules`).
  * Тестирование логики добавления правил через команды.

## 4. Этапы внедрения

1. **Настройка окружения:**
    * Добавить библиотеки в `requirements.dev.txt`.
    * Создать базовый `conftest.py`.
2. **Реализация Unit-тестов (Логика):**
    * Написать тесты для парсера правил и конфига.
    * Написать тесты для менеджера очереди (файловые операции можно мокать через `tmp_path` фикстуру pytest).
3. **Реализация тестов Handlers/Commands:**
    * Написать тесты с моками Telethon Events.
4. **Запуск и CI:**
    * Настроить команду `pytest` в Makefile или скрипте.
    * (Опционально) Добавить GitHub Actions workflow.

## 5. Пример `conftest.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.config_manager import ConfigManager

@pytest.fixture
def mock_config_mgr(tmp_path):
    # Создаем временные файлы конфигов
    cfg_file = tmp_path / "config.json"
    rules_file = tmp_path / "rules.txt"
    
    # Инициализируем менеджер с временными путями
    manager = ConfigManager(str(cfg_file), str(rules_file))
    # ... предварительная запись данных ...
    return manager

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.send_message = AsyncMock()
    client.forward_messages = AsyncMock()
    return client
```
