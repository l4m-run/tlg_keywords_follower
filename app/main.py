"""
Telegram UserBot - Точка входа.
Минималистичный бот для мониторинга чатов и пересылки сообщений по правилам.
"""

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telethon import TelegramClient
from dotenv import load_dotenv

from .config_manager import ConfigManager
from .queue_manager import QueueManager
from .handlers import setup_handlers
from .commands import setup_commands


async def main():
    """Главная функция запуска бота"""
    
    # Загрузка credentials из .env
    load_dotenv()
    api_id = int(os.getenv('API_ID'))
    api_hash = os.getenv('API_HASH')
    phone = os.getenv('PHONE')
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 Запуск Telegram UserBot...")
    
    # Инициализация менеджера конфигурации
    logger.info("📋 Загрузка конфигурации...")
    config_mgr = ConfigManager()
    config_mgr.load()
    
    # Инициализация Telethon клиента
    logger.info("🔗 Подключение к Telegram...")
    client = TelegramClient('userbot_session', api_id, api_hash)
    
    # Запуск клиента (авторизация при первом запуске)
    await client.start(phone=phone)
    logger.info("✅ Успешно авторизован!")
    
    # Инициализация менеджера очереди
    queue_mgr = QueueManager(config_mgr)
    
    # Регистрация обработчиков событий
    logger.info("📡 Регистрация обработчиков...")
    setup_handlers(client, config_mgr, queue_mgr)
    
    # Регистрация команд управления
    logger.info("💬 Регистрация команд...")
    setup_commands(client, config_mgr)
    
    # Запуск queue worker в фоне
    logger.info("⚙️ Запуск queue worker...")
    asyncio.create_task(queue_mgr.process_queue(client))
    
    # Информация о запуске
    rules_count = len(config_mgr.get_rules())
    monitored_count = len(config_mgr.get_monitored_chat_ids())
    logger.info("="*50)
    logger.info("✨ Бот успешно запущен!")
    logger.info(f"📊 Правил: {rules_count}")
    logger.info(f"👁 Мониторимых чатов: {monitored_count}")
    logger.info(f"📤 Режим пересылки: {config_mgr.get_forward_mode()}")
    logger.info(f"🔄 Автодобавление: {'ВКЛ' if config_mgr.get_auto_add_chats() else 'ВЫКЛ'}")
    logger.info("="*50)
    logger.info("💡 Отправляйте команды в Saved Messages (Избранное)")
    logger.info("💡 Нажмите Ctrl+C для остановки")
    logger.info("="*50)
    
    # Запуск бота (блокирующий вызов)
    await client.run_until_disconnected()


if __name__ == '__main__':
    # Настройка логирования с ротацией
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                'bot.log',
                maxBytes=10*1024*1024,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    
    # Создание директории queue/ если не существует
    Path('queue').mkdir(exist_ok=True)
    
    # Запуск бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\n👋 Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}", exc_info=True)
