# Модульная структура Telegram UserBot

## Общая концепция

Разбиваем монолитный `bot.py` на **5 логических модулей** для удобства поддержки при сохранении минимализма.

---

## Структура файлов

```
tlg_keywords_follower/
├── app/
│   ├── __init__.py          # Инициализация пакета
│   ├── main.py              # Точка входа, инициализация
│   ├── config_manager.py    # Управление конфигурацией
│   ├── queue_manager.py     # Файловая очередь
│   ├── handlers.py          # Обработчики событий Telegram
│   └── commands.py          # Команды управления
├── config.json              # Конфигурация
├── rules.txt                # Правила пересылки
├── .env                     # API credentials
├── Dockerfile               # Конфигурация Docker
├── docker-compose.yml       # Конфигурация Compose
├── deploy_docker.sh         # Скрипт запуска Docker
└── queue/                   # Директория очереди
```

---

## 1. main.py (50-80 строк)

**Назначение:** Точка входа, инициализация и запуск бота.

**Содержимое:**

```python
"""
Telegram UserBot - минималистичный бот для мониторинга чатов
и пересылки сообщений по правилам.
"""

import logging
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv
import os

from config_manager import ConfigManager
from queue_manager import QueueManager
from handlers import setup_handlers
from commands import setup_commands


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    
    # Загрузка credentials
    load_dotenv()
    api_id = int(os.getenv('API_ID'))
    api_hash = os.getenv('API_HASH')
    phone = os.getenv('PHONE')
    
    # Инициализация менеджера конфигурации
    config_mgr = ConfigManager()
    config_mgr.load()
    
    # Инициализация Telethon клиента
    client = TelegramClient('userbot_session', api_id, api_hash)
    
    # Инициализация очереди
    queue_mgr = QueueManager(config_mgr)
    
    # Запуск клиента
    await client.start(phone=phone)
    logger.info("Бот успешно запущен!")
    
    # Регистрация обработчиков событий
    setup_handlers(client, config_mgr, queue_mgr)
    
    # Регистрация команд управления
    setup_commands(client, config_mgr)
    
    # Запуск queue worker в фоне
    asyncio.create_task(queue_mgr.process_queue(client))
    
    # Запуск бота
    logger.info("Бот работает. Нажмите Ctrl+C для остановки.")
    await client.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
```

**Ответственность:**

- ✅ Запуск и инициализация всех компонентов
- ✅ Настройка логирования
- ✅ Создание Telethon клиента
- ✅ Координация модулей
- ✅ Graceful shutdown

---

## 2. config_manager.py (150-200 строк)

**Назначение:** Управление конфигурацией - config.json и rules.txt.

**Содержимое:**

```python
"""
Управление конфигурацией бота.
Работа с config.json и rules.txt.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """Менеджер конфигурации бота"""
    
    def __init__(self, 
                 config_file='config.json', 
                 rules_file='rules.txt'):
        self.config_file = config_file
        self.rules_file = rules_file
        self.config = {}
    
    def load(self):
        """Загружает конфигурацию из файлов"""
        self._load_config_json()
        self._load_rules_txt()
        self._validate_and_clean()
        logger.info("Конфигурация загружена успешно")
    
    def _load_config_json(self):
        """Загрузка config.json"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.warning(f"{self.config_file} не найден, создаём default")
            self._create_default_config()
    
    def _load_rules_txt(self):
        """Загрузка и парсинг rules.txt"""
        if not Path(self.rules_file).exists():
            logger.warning(f"{self.rules_file} не найден")
            self.config['rules'] = []
            return
        
        rules = []
        with open(self.rules_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                try:
                    rule = self._parse_rule_line(line)
                    if rule:
                        rules.append(rule)
                except Exception as e:
                    logger.error(f"Ошибка парсинга строки {line_num}: {e}")
        
        self.config['rules'] = rules
        logger.info(f"Загружено {len(rules)} правил из {self.rules_file}")
    
    def _parse_rule_line(self, line: str) -> Dict[str, Any]:
        """
        Парсинг строки правила.
        Формат: name: keywords -> chat_id "Name", chat_id2 "Name2" [case:on]
        """
        # Реализация парсинга
        # ...
        pass
    
    def _validate_and_clean(self):
        """
        Валидация и очистка monitored_chats.
        Убирает все target_chat_ids из monitored_chats.
        """
        # Собираем все target чаты
        all_targets = set()
        for rule in self.config.get('rules', []):
            for chat in rule.get('target_chats', []):
                all_targets.add(chat['id'])
        
        # Фильтруем monitored_chats
        monitored = self.config.get('monitored_chats', [])
        cleaned = [c for c in monitored if c['id'] not in all_targets]
        
        if len(cleaned) != len(monitored):
            removed = set(c['id'] for c in monitored) - set(c['id'] for c in cleaned)
            logger.warning(f"Удалены target чаты из monitored_chats: {removed}")
        
        self.config['monitored_chats'] = cleaned
    
    def save(self):
        """Сохраняет конфигурацию в файлы"""
        self._save_config_json()
        self._save_rules_txt()
    
    def _save_config_json(self):
        """Сохранение config.json"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def _save_rules_txt(self):
        """Сохранение rules.txt"""
        with open(self.rules_file, 'w', encoding='utf-8') as f:
            f.write("# Правила пересылки сообщений\n")
            f.write("# Формат: name: keywords -> chat_id \"Name\" [case:on]\n\n")
            
            for rule in self.config.get('rules', []):
                # Форматирование правила
                # ...
                pass
    
    def add_monitored_chat(self, chat_id: int, chat_name: str):
        """Добавляет чат в monitored_chats"""
        # Проверка дублей и target чатов
        # Добавление и сохранение
        pass
    
    def get_monitored_chat_ids(self) -> List[int]:
        """Возвращает список ID мониторимых чатов"""
        return [c['id'] for c in self.config.get('monitored_chats', [])]
    
    def get_rules(self) -> List[Dict]:
        """Возвращает список правил"""
        return self.config.get('rules', [])
    
    # Дополнительные методы для команд управления...
```

**Ответственность:**

- ✅ Загрузка и сохранение config.json
- ✅ Парсинг rules.txt
- ✅ Валидация конфигурации
- ✅ API для доступа к настройкам
- ✅ Добавление/удаление правил и чатов

---

## 3. queue_manager.py (100-150 строк)

**Назначение:** Управление файловой очередью сообщений.

**Содержимое:**

```python
"""
Менеджер файловой очереди для надёжной доставки сообщений.
"""

import json
import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any
from telethon.errors import FloodWaitError

logger = logging.getLogger(__name__)


class QueueManager:
    """Менеджер файловой очереди"""
    
    def __init__(self, config_manager, queue_dir='queue'):
        self.config_mgr = config_manager
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
    
    def add_to_queue(self, message_data: Dict[str, Any]):
        """
        Добавляет сообщение в очередь.
        
        message_data = {
            'message': message object,
            'target_chats': [chat_id1, chat_id2, ...],
            'matched_rules': [...],
            'forward_mode': 'copy'
        }
        """
        timestamp = int(time.time() * 1000000)
        filename = self.queue_dir / f"{timestamp}.json"
        
        # Сохраняем необходимые данные (не весь message object)
        # ВАЖНО: сохраняем message_id и from_chat_id для forward mode!
        queue_item = {
            'message_id': message_data['message'].id,
            'from_chat_id': message_data['message'].chat_id,
            'message_text': message_data['message'].text,
            'target_chat_ids': message_data['target_chats'],
            'matched_rules': message_data['matched_rules'],
            'forward_mode': message_data.get('forward_mode', 'copy'),
            'timestamp': timestamp
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(queue_item, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Сообщение добавлено в очередь: {filename.name}")
    
    def get_queue_items(self):
        """Возвращает список файлов очереди (отсортированные)"""
        return sorted(self.queue_dir.glob('*.json'))
    
    def remove_from_queue(self, filename: Path):
        """Удаляет файл из очереди"""
        try:
            filename.unlink()
            logger.info(f"Файл очереди удалён: {filename.name}")
        except Exception as e:
            logger.error(f"Ошибка удаления файла очереди: {e}")
    
    async def send_message_safe(self, client, chat_id, message_data, forward_mode='copy'):
        """
        Отправляет сообщение с обработкой FloodWaitError.
        Возвращает True при успехе, False при ошибке.
        
        message_data = {
            'message_id': int,
            'from_chat_id': int,
            'message_text': str
        }
        """
        try:
            if forward_mode == 'forward':
                # Используем message_id и from_chat_id для пересылки
                await client.forward_messages(
                    chat_id,
                    messages=message_data['message_id'],
                    from_peer=message_data['from_chat_id']
                )
            else:
                # Для copy просто отправляем текст
                await client.send_message(chat_id, message_data['message_text'])
            
            return True
            
        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: нужно подождать {e.seconds} сек")
            return False
        except Exception as e:
            logger.error(f"Ошибка отправки в {chat_id}: {e}")
            return False
    
    async def process_queue(self, client):
        """
        Фоновый worker для обработки очереди.
        Запускается как asyncio task.
        """
        logger.info("Queue worker запущен")
        
        while True:
            try:
                queue_items = self.get_queue_items()
                
                for item_file in queue_items:
                    # Читаем данные
                    with open(item_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Отправляем во все target чаты
                    all_sent = True
                    for target_chat in data['target_chats']:
                        success = await self.send_message_safe(
                            client,
                            target_chat['id'],
                            data['message_text'],
                            data.get('forward_mode', 'copy')
                        )
                        
                        if not success:
                            all_sent = False
                            break
                    
                    # Если все отправлены - удаляем из очереди
                    if all_sent:
                        self.remove_from_queue(item_file)
                        logger.info(f"Сообщение успешно доставлено во все чаты")
                    else:
                        # Ждём перед повторной попыткой
                        await asyncio.sleep(60)
                        break
                
                # Проверяем очередь каждые 5 секунд
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Ошибка в queue_worker: {e}")
                await asyncio.sleep(10)
```

**Ответственность:**

- ✅ Добавление сообщений в очередь
- ✅ Обработка FloodWaitError
- ✅ Фоновый worker для отправки
- ✅ Retry логика
- ✅ Персистентность очереди

---

## 4. handlers.py (100-150 строк)

**Назначение:** Обработчики Telegram событий.

**Содержимое:**

```python
"""
Обработчики событий Telegram.
"""

import logging
from telethon import events

logger = logging.getLogger(__name__)


def setup_handlers(client, config_mgr, queue_mgr):
    """Регистрирует все обработчики событий"""
    
    @client.on(events.ChatAction)
    async def handle_chat_action(event):
        """
        Обработчик добавления бота в группу.
        Автоматически добавляет чат в monitored_chats.
        """
        # Проверяем что это добавление бота
        if not event.user_added or not event.is_self:
            return
        
        try:
            # Получаем информацию о чате
            chat = await event.get_chat()
            chat_id = chat.id
            chat_name = chat.title or chat.first_name or 'Unknown'
            
            logger.info(f"Бот добавлен в чат: {chat_name} ({chat_id})")
            
            # Проверяем auto_add_chats
            if not config_mgr.config.get('auto_add_chats', False):
                logger.info("auto_add_chats выключен, пропускаем")
                return
            
            # Добавляем в monitored_chats
            config_mgr.add_monitored_chat(chat_id, chat_name)
            logger.info(f"Чат {chat_name} добавлен в monitored_chats")
            
        except Exception as e:
            logger.error(f"Ошибка в handle_chat_action: {e}")
    
    @client.on(events.NewMessage)
    async def handle_new_message(event):
        """
        Обработчик новых сообщений.
        Проверяет правила и добавляет в очередь.
        """
        # Проверяем что это мониторимый чат
        monitored_ids = config_mgr.get_monitored_chat_ids()
        if event.chat_id not in monitored_ids:
            return
        
        # Получаем текст сообщения
        text = event.message.text
        if not text:
            return
        
        # Проверяем по всем правилам
        matched_rules = check_message_against_rules(text, config_mgr.get_rules())
        
        if not matched_rules:
            return
        
        # Собираем уникальные target чаты
        target_chats = get_unique_target_chats(matched_rules)
        
        # Логируем совпадения
        rule_names = [r['rule_name'] for r in matched_rules]
        logger.info(f"Сообщение совпало с правилами: {rule_names}")
        
        # Добавляем в очередь
        message_data = {
            'message': event.message,
            'target_chats': target_chats,
            'matched_rules': matched_rules,
            'forward_mode': config_mgr.config.get('forward_mode', 'copy')
        }
        
        queue_mgr.add_to_queue(message_data)
    
    logger.info("Обработчики событий зарегистрированы")


def check_message_against_rules(text, rules):
    """Проверяет текст по всем правилам"""
    # Реализация из плана
    pass


def get_unique_target_chats(matched_rules):
    """Собирает уникальные target чаты из правил"""
    # Реализация из плана
    pass
```

**Ответственность:**

- ✅ Обработка ChatAction (автодобавление)
- ✅ Обработка NewMessage (фильтрация)
- ✅ Проверка правил
- ✅ Добавление в очередь

---

## 5. commands.py (200-250 строк)

**Назначение:** Команды управления правилами через Saved Messages.

**Содержимое:**

```python
"""
Команды управления правилами.
Работают только в Saved Messages (from_users='me').
"""

import logging
from telethon import events

logger = logging.getLogger(__name__)


def setup_commands(client, config_mgr):
    """Регистрирует команды управления"""
    
    @client.on(events.NewMessage(from_users='me', pattern=r'^/\w+'))
    async def handle_commands(event):
        """Роутер команд"""
        text = event.text.strip()
        
        # Парсинг команды
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''
        
        # Роутинг
        if command in ['/rules', '/list']:
            await cmd_list_rules(event, config_mgr)
        elif command == '/rule':
            await cmd_show_rule(event, config_mgr, args)
        elif command == '/test':
            await cmd_test_message(event, config_mgr, args)
        elif command == '/add_rule':
            await cmd_add_rule(event, config_mgr, args)
        elif command == '/add_keywords':
            await cmd_add_keywords(event, config_mgr, args)
        elif command == '/add_group':
            await cmd_add_group(event, config_mgr, args)
        elif command == '/remove_rule':
            await cmd_remove_rule(event, config_mgr, args)
        elif command == '/reload':
            await cmd_reload(event, config_mgr)
        elif command == '/monitored_chats':
            await cmd_monitored_chats(event, config_mgr)
        elif command == '/help':
            await cmd_help(event)
        else:
            await event.reply(f"❌ Неизвестная команда: {command}\n\nИспользуйте /help")
    
    logger.info("Команды управления зарегистрированы")


async def cmd_list_rules(event, config_mgr):
    """Показывает список всех правил"""
    rules = config_mgr.get_rules()
    
    if not rules:
        await event.reply("📋 Нет активных правил")
        return
    
    text = f"📋 Активные правила ({len(rules)}):\n\n"
    
    for i, rule in enumerate(rules, 1):
        # Форматирование правила
        pass
    
    await event.reply(text)


async def cmd_show_rule(event, config_mgr, rule_name):
    """Показывает детали правила"""
    # Реализация
    pass


async def cmd_add_rule(event, config_mgr, args):
    """Создаёт новое правило"""
    # Реализация
    pass


async def cmd_reload(event, config_mgr):
    """Перечитывает конфигурацию"""
    try:
        config_mgr.load()
        rules_count = len(config_mgr.get_rules())
        await event.reply(f"✅ Конфигурация перезагружена\n\n📊 Правил: {rules_count}")
    except Exception as e:
        await event.reply(f"❌ Ошибка: {e}")


# Остальные команды...
```

**Ответственность:**

- ✅ Все команды управления правилами
- ✅ Роутинг команд
- ✅ Форматирование ответов
- ✅ Обработка ошибок

---

## Преимущества модульной структуры

### ✅ Читаемость

- Файлы по 100-200 строк вместо 600+
- Понятное разделение ответственности
- Легко найти нужный код

### ✅ Поддерживаемость

- Изменения в одном модуле не затрагивают другие
- Легко добавлять новые команды
- Простое расширение функционала

### ✅ Тестируемость

- Каждый модуль можно тестировать отдельно
- Легко мокать зависимости
- Юнит-тесты проще писать

### ✅ Минимализм сохранён

- Всего 5 Python файлов
- Нет сложных абстракций
- Прямолинейная архитектура
- Минимум зависимостей между модулями

---

## Взаимодействие модулей

```
main.py
  ├─ создаёт ConfigManager
  ├─ создаёт QueueManager(config_mgr)
  ├─ создаёт TelegramClient
  ├─ setup_handlers(client, config_mgr, queue_mgr)
  └─ setup_commands(client, config_mgr)

handlers.py
  ├─ использует config_mgr для проверки правил
  └─ использует queue_mgr для добавления сообщений

commands.py
  └─ использует config_mgr для управления правилами

queue_manager.py
  ├─ использует config_mgr для настроек
  └─ независим от handlers и commands
```

**Зависимости:**

- `main.py` → все модули
- `handlers.py` → `config_manager`, `queue_manager`
- `commands.py` → `config_manager`
- `queue_manager.py` → `config_manager`
- `config_manager.py` → ничего (базовый модуль)

**Итого:** Простая однонаправленная структура зависимостей.

---

## Импорты между модулями

```python
# main.py
from config_manager import ConfigManager
from queue_manager import QueueManager
from handlers import setup_handlers
from commands import setup_commands

# handlers.py
# Нет прямых импортов других модулей
# Всё передаётся через параметры

# commands.py
# Нет прямых импортов других модулей
# Всё передаётся через параметры

# queue_manager.py
# Нет прямых импортов других модулей
# config_mgr передаётся в конструктор

# config_manager.py
# Только стандартная библиотека
```

**Принцип:** Dependency Injection через параметры, а не прямые импорты модулей друг в друга.

---

## Миграция с монолита

Если у вас уже есть `bot.py`:

1. Создайте новые файлы модулей
2. Скопируйте соответствующие блоки кода
3. Добавьте импорты
4. Переименуйте `bot.py` → `bot_old.py` (backup)
5. Тестируйте новую версию
6. Удалите `bot_old.py` после проверки

**Время миграции:** ~30-60 минут
