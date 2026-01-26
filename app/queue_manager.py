"""
Менеджер файловой очереди для надёжной доставки сообщений.
Обработка FloodWaitError и retry логика.
"""

import json
import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List
from telethon.errors import FloodWaitError
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class QueueManager:
    """Менеджер файловой очереди сообщен"""
    
    def __init__(self, config_manager: ConfigManager, queue_dir: str = 'app_data/queue'):
        """
        Инициализация менеджера очереди.
        
        Args:
            config_manager: Экземпляр ConfigManager
            queue_dir: Директория для хранения очереди
        """
        self.config_mgr = config_manager
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
        logger.info(f"Queue manager инициализирован: {self.queue_dir}")
    
    def add_to_queue(self, message_data: Dict[str, Any]) -> None:
        """
        Добавляет сообщение в очередь.
        
        Args:
            message_data: Словарь с данными:
                - message: message object from Telethon
                - target_chats: List[int] - список ID целевых чатов
                - matched_rules: List[Dict] - сработавшие правила
                - forward_mode: str - 'forward' или 'copy'
        """
        timestamp = int(time.time() * 1000000)  # Микросекунды для уникальности
        filename = self.queue_dir / f"{timestamp}.json"
        
        # Сохраняем message_id и from_chat_id для forward mode
        queue_item = {
            'message_id': message_data['message'].id,
            'from_chat_id': message_data['message'].chat_id,
            'message_text': message_data['message'].text or '',
            'target_chat_ids': message_data['target_chats'],
            'matched_rules': [r['rule_name'] for r in message_data['matched_rules']],
            'forward_mode': message_data.get('forward_mode', 'copy'),
            'timestamp': timestamp
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(queue_item, f, ensure_ascii=False, indent=2)
        
        logger.info(
            f"Сообщение добавлено в очередь: правила={queue_item['matched_rules']}, "
            f"чатов={len(queue_item['target_chat_ids'])}"
        )
    
    def get_queue_items(self) -> List[Path]:
        """
        Возвращает список файлов очереди отсортированные по времени.
        
        Returns:
            Список Path объектов
        """
        return sorted(self.queue_dir.glob('*.json'))
    
    def remove_from_queue(self, filename: Path) -> None:
        """
        Удаляет файл из очереди после успешной отправки.
        
        Args:
            filename: Path к файлу очереди
        """
        try:
            filename.unlink()
            logger.info(f"Файл очереди удалён: {filename.name}")
        except Exception as e:
            logger.error(f"Ошибка удаления файла очереди {filename}: {e}")
    
    async def send_message_safe(
        self,
        client,
        chat_id: int,
        message_data: Dict[str, Any],
        forward_mode: str = 'copy',
        rule_names: List[str] = None
    ) -> bool:
        """
        Отправляет сообщение с обработкой FloodWaitError и резолвингом ID.
        
        Args:
            client: TelegramClient instance
            chat_id: ID целевого чата
            message_data: Данные сообщения из queue_item
            forward_mode: 'forward' или 'copy'
            rule_names: Список названий сработавших правил для уведомления
            
        Returns:
            True при успехе, False при ошибке (FloodWait или другой)
        """
        try:
            # Резолвим целевую сущность (чат) для предотвращения ChatIdInvalidError
            target_peer = await client.get_input_entity(chat_id)
            
            if forward_mode == 'forward':
                # Резолвим исходную сущность
                from_peer = await client.get_input_entity(message_data['from_chat_id'])
                
                # Используем message_id и резолвленные peer'ы для пересылки
                await client.forward_messages(
                    target_peer,
                    messages=message_data['message_id'],
                    from_peer=from_peer
                )
            else:
                # Для copy просто отправляем текст
                await client.send_message(target_peer, message_data['message_text'])
            
            # Отправка уведомления о правиле (вторым сообщением)
            if rule_names:
                rules_str = ', '.join(rule_names)
                try:
                    await client.send_message(target_peer, f"ℹ️ Сработало правило: {rules_str}")
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление о правиле в {chat_id}: {e}")
            
            logger.info(f"Сообщение отправлено в {chat_id}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"FloodWaitError: нужно подождать {e.seconds} сек для {chat_id}")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка отправки в {chat_id}: {type(e).__name__}: {e}")
            return False
    
    async def process_queue(self, client) -> None:
        """
        Фоновый worker для обработки очереди.
        Запускается как asyncio task и работает бесконечно.
        
        Args:
            client: TelegramClient instance
        """
        logger.info("Queue worker запущен")
        
        while True:
            try:
                queue_items = self.get_queue_items()
                
                if not queue_items:
                    # Очередь пуста, ждём
                    await asyncio.sleep(5)
                    continue
                
                for item_file in queue_items:
                    # Читаем данные
                    try:
                        with open(item_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    except Exception as e:
                        logger.error(f"Ошибка чтения файла очереди {item_file}: {e}")
                        # Удаляем повреждённый файл
                        self.remove_from_queue(item_file)
                        continue
                    
                    # Отправляем во все target чаты
                    all_sent = True
                    for target_id in data['target_chat_ids']:
                        success = await self.send_message_safe(
                            client,
                            target_id,
                            data,
                            data.get('forward_mode', 'copy'),
                            rule_names=data.get('matched_rules')
                        )
                        
                        if not success:
                            all_sent = False
                            break
                    
                    # Если все отправлены успешно - удаляем из очереди
                    if all_sent:
                        self.remove_from_queue(item_file)
                        logger.info(
                            f"Сообщение успешно доставлено во все {len(data['target_chat_ids'])} чатов"
                        )
                    else:
                        # Если была ошибка (FloodWait) - ждём перед следующей попыткой
                        logger.info("Ожидание 60 сек перед retry...")
                        await asyncio.sleep(60)
                        break  # Прерываем цикл, начнём сначала после ожидания
                
                # Проверяем очередь каждые 5 секунд
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Ошибка в queue_worker: {e}", exc_info=True)
                await asyncio.sleep(10)
