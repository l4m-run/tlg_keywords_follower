"""
Менеджер файловой очереди для надёжной доставки сообщений.
Обработка FloodWaitError и retry логика.
"""

import json
import time
import asyncio
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set

from telethon.errors import (
    FloodWaitError, ChatIdInvalidError, ChannelPrivateError, 
    UserBannedInChannelError, ChatWriteForbiddenError
)
# Импортируем только стандартные исключения, если они не из Telethon
# Telethon errors usually inherit from RPCError -> Exception

from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

# Максимальное количество попыток для временных ошибок
MAX_RETRIES = 5

# Временные ошибки (будем повторять)
TEMPORARY_ERRORS = (FloodWaitError, TimeoutError, ConnectionError)

# Постоянные ошибки (пропускаем чат)
PERMANENT_ERRORS = (
    ChatIdInvalidError,
    ChannelPrivateError, 
    UserBannedInChannelError,
    ChatWriteForbiddenError,
)


class QueueManager:
    """Менеджер файловой очереди сообщений"""
    
    def __init__(self, config_manager: ConfigManager, queue_dir: str = 'app_data/queue'):
        """
        Инициализация менеджера очереди.
        
        Args:
            config_manager: Экземпляр ConfigManager
            queue_dir: Директория для хранения очереди
        """
        self.config_mgr = config_manager
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        self.failed_dir = self.queue_dir.parent / 'queue_failed'
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        
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
        timestamp = int(time.time() * 1000000)
        filename = self.queue_dir / f"{timestamp}.json"
        
        # Сохраняем message_id и from_chat_id для forward mode
        # Добавляем tracking поля: sent_chat_ids и retry_count
        queue_item = {
            'message_id': message_data['message'].id,
            'from_chat_id': message_data['message'].chat_id,
            'message_text': message_data['message'].text or '',
            'target_chat_ids': message_data['target_chats'],
            'sent_chat_ids': [],  # Список ID чатов, куда успешно отправлено
            'matched_rules': [r['rule_name'] for r in message_data['matched_rules']],
            'forward_mode': message_data.get('forward_mode', 'copy'),
            'timestamp': timestamp,
            'retry_count': 0  # Счетчик попыток отправки
        }
        
        self._save_queue_item(filename, queue_item)
        
        logger.info(
            f"Сообщение добавлено в очередь: правила={queue_item['matched_rules']}, "
            f"чатов={len(queue_item['target_chat_ids'])}"
        )
    
    def get_queue_items(self) -> List[Path]:
        """Возвращает список файлов очереди отсортированные по времени."""
        return sorted(self.queue_dir.glob('*.json'))
    
    def remove_from_queue(self, filename: Path) -> None:
        """Удаляет файл из очереди после успешной отправки."""
        try:
            filename.unlink()
            logger.info(f"Файл очереди удалён: {filename.name}")
        except Exception as e:
            logger.error(f"Ошибка удаления файла очереди {filename}: {e}")

    def move_to_failed(self, filename: Path) -> None:
        """Перемещает файл в директорию failed."""
        try:
            dest = self.failed_dir / filename.name
            shutil.move(str(filename), str(dest))
            logger.warning(f"Сообщение перемещено в failed (limit exceeded): {filename.name}")
        except Exception as e:
            logger.error(f"Ошибка перемещения в failed {filename}: {e}")

    def _save_queue_item(self, filename: Path, data: Dict[str, Any]) -> None:
        """Сохраняет обновленные данные элемента очереди."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения файла очереди {filename}: {e}")

    def _load_queue_item(self, filename: Path) -> Optional[Dict[str, Any]]:
        """Загружает данные из файла очереди."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения файла очереди {filename}: {e}")
            return None
    
    async def send_message_safe(
        self,
        client,
        chat_id: int,
        message_data: Dict[str, Any],
        forward_mode: str = 'copy',
        rule_names: List[str] = None
    ) -> Tuple[bool, str]:
        """
        Отправляет сообщение с обработкой ошибок.
        
        Returns:
            (success: bool, error_type: str)
            error_type: 'none' | 'permanent' | 'unknown'
            (TEMPORARY_ERRORS are raised to be handled by caller)
        """
        try:
            # Резолвим целевую сущность (чат)
            try:
                target_peer = await client.get_input_entity(chat_id)
            except ValueError:
                # Если не удалось зарезолвить entitty -> вероятно нет доступа или чат не найден
                # Считаем это постоянной ошибкой для данного chat_id
                logger.error(f"Could not resolve entity for chat_id {chat_id}")
                return False, 'permanent'

            if forward_mode == 'forward':
                try:
                    from_peer = await client.get_input_entity(message_data['from_chat_id'])
                except ValueError:
                     logger.error(f"Could not resolve source chat {message_data['from_chat_id']}")
                     return False, 'permanent'

                await client.forward_messages(
                    target_peer,
                    messages=message_data['message_id'],
                    from_peer=from_peer
                )
            else:
                await client.send_message(target_peer, message_data['message_text'])
            
            # Отправка уведомления о правиле (вторым сообщением) - опционально, ошибки тут не блокируют основную
            if rule_names:
                rules_str = ', '.join(rule_names)
                try:
                    await client.send_message(target_peer, f"ℹ️ Сработало правило: {rules_str}")
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление о правиле в {chat_id}: {e}")
            
            logger.info(f"Сообщение отправлено в {chat_id}")
            return True, 'none'
            
        except TEMPORARY_ERRORS as e:
            wait = getattr(e, 'seconds', 0)
            logger.warning(f"Temporary error sending to {chat_id} (wait={wait}): {e}")
            raise e  # Re-raise to handle retry/sleep in loop
            
        except PERMANENT_ERRORS as e:
            logger.error(f"Permanent error sending to {chat_id}: {type(e).__name__}: {e}")
            return False, 'permanent'
            
        except Exception as e:
            logger.error(f"Unknown error sending to {chat_id}: {type(e).__name__}: {e}")
            return False, 'unknown'
    
    async def process_queue(self, client) -> None:
        """
        Фоновый worker для обработки очереди.
        """
        logger.info("Queue worker запущен")
        
        while True:
            try:
                queue_items = self.get_queue_items()
                
                if not queue_items:
                    # Очередь пуста, короткий сон
                    await asyncio.sleep(1)
                    continue
                
                for item_file in queue_items:
                    data = self._load_queue_item(item_file)
                    if data is None:
                        # Файл битый
                        self.remove_from_queue(item_file)
                        continue
                    
                    # Фильтруем получателей
                    sent_ids = set(data.get('sent_chat_ids', []))
                    all_targets = data.get('target_chat_ids', [])
                    
                    # Target chat ids filter: only those not in sent_ids
                    pending_ids = [tid for tid in all_targets if tid not in sent_ids]
                    
                    if not pending_ids:
                        self.remove_from_queue(item_file)
                        continue
                    
                    flood_wait_seconds = 0
                    should_retry = False
                    
                    for target_id in pending_ids:
                        try:
                            success, error_type = await self.send_message_safe(
                                client,
                                target_id,
                                data,
                                data.get('forward_mode', 'copy'),
                                rule_names=data.get('matched_rules')
                            )
                            
                            if success:
                                sent_ids.add(target_id)
                                data['sent_chat_ids'] = list(sent_ids)
                                self._save_queue_item(item_file, data)
                            elif error_type == 'permanent':
                                # При постоянной ошибке тоже считаем "обработанным", чтобы не зацикливаться
                                logger.warning(f"Skipping chat {target_id} due to permanent error")
                                sent_ids.add(target_id)
                                data['sent_chat_ids'] = list(sent_ids)
                                self._save_queue_item(item_file, data)
                            elif error_type == 'unknown':
                                should_retry = True
                                break # Stop and retry later
                                
                        except FloodWaitError as e:
                            flood_wait_seconds = getattr(e, 'seconds', 60)
                            logger.warn(f"FloodWait hit: {flood_wait_seconds}s")
                            should_retry = True
                            break
                        except Exception as e:
                            # Другие временные ошибки (ConnectionError etc)
                            logger.warn(f"Temporary error hit: {e}")
                            should_retry = True
                            break
                    
                    if should_retry:
                        # Увеличиваем счетчик попыток только если прервали цикл
                        data['retry_count'] = data.get('retry_count', 0) + 1
                        self._save_queue_item(item_file, data)
                        
                        if data['retry_count'] >= MAX_RETRIES:
                            logger.error(f"Max retries exceeded for {item_file.name}")
                            self.move_to_failed(item_file)
                        else:
                            if flood_wait_seconds > 0:
                                wait_time = flood_wait_seconds + 2
                                logger.info(f"Sleeping for FloodWait: {wait_time}s")
                                await asyncio.sleep(wait_time)
                            else:
                                await asyncio.sleep(5) # Default retry delay
                        
                        # Прерываем обработку текущего пакета, чтобы дать chance другим или повторить этот
                        # В данной реализации мы остаемся в while True и возьмем этот же файл (или следующий)
                        # Лучше всего сделать break из for loop, чтобы перечитать очередь
                        break 
                    
                    # Если прошли цикл без should_retry -> значит все pending_ids обработаны (успешно или перманентно)
                    # Проверяем на всякий случай
                    if len(set(data['sent_chat_ids'])) >= len(all_targets):
                         self.remove_from_queue(item_file)
                         logger.info(f"Сообщение {item_file.name} полностью обработано")
                
                # Небольшая пауза между проходами по списку файлов (если список был), 
                # но если очередь большая, лучше молотить подряд. 
                # Сделаем 0.1 сек чтобы не грузить CPU в tight loop
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Critical error in queue_worker: {e}", exc_info=True)
                await asyncio.sleep(5)
