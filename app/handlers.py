"""
Обработчики событий Telegram.
ChatAction для автодобавления чатов, NewMessage для фильтрации и пересылки.
"""

import logging
from telethon import events
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def setup_handlers(client, config_mgr, queue_mgr) -> None:
    """
    Регистрирует все обработчики событий Telegram.
    
    Args:
        client: TelegramClient instance
        config_mgr: ConfigManager instance
        queue_mgr: QueueManager instance
    """
    
    @client.on(events.ChatAction)
    async def handle_chat_action(event):
        """
        Обработчик добавления бота в группу.
        Автоматически добавляет чат в monitored_chats если auto_add_chats=True.
        """
        # Проверяем что это добавление бота
        if not (event.user_added and event.is_self):
            return
        
        # Проверяем настройку auto_add_chats
        if not config_mgr.get_auto_add_chats():
            logger.info("auto_add_chats выключен, пропускаем автодобавление")
            return
        
        try:
            # Получаем информацию о чате
            chat = await event.get_chat()
            chat_id = chat.id
            chat_name = chat.title or chat.first_name or 'Unknown'
            
            logger.info(f"Бот добавлен в чат: {chat_name} ({chat_id})")
            
            # Добавляем в monitored_chats (с проверкой что это не target)
            added = config_mgr.add_monitored_chat(chat_id, chat_name)
            if added:
                logger.info(f"✅ Чат {chat_name} добавлен в monitored_chats")
            
        except Exception as e:
            logger.error(f"Ошибка в handle_chat_action: {e}", exc_info=True)
    
    @client.on(events.NewMessage)
    async def handle_new_message(event):
        """
        Обработчик новых сообщений.
        Проверяет сообщения по правилам и добавляет в очередь при совпадении.
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
        rules = config_mgr.get_rules()
        matched_rules = check_message_against_rules(text, rules)
        
        if not matched_rules:
            return
        
        # Собираем уникальные target чаты
        target_chats = get_unique_target_chats(matched_rules)
        
        # Логируем совпадения
        rule_names = [r['rule_name'] for r in matched_rules]
        matched_keywords = [r['matched_keyword'] for r in matched_rules]
        logger.info(
            f"✨ Сообщение совпало с правилами: {rule_names} "
            f"(ключевые слова: {matched_keywords})"
        )
        
        # Добавляем в очередь
        message_data = {
            'message': event.message,
            'target_chats': target_chats,
            'matched_rules': matched_rules,
            'forward_mode': config_mgr.get_forward_mode()
        }
        
        queue_mgr.add_to_queue(message_data)
    
    logger.info("✅ Обработчики событий зарегистрированы")


def check_message_against_rules(text: str, rules: List[Dict]) -> List[Dict[str, Any]]:
    """
    Проверяет текст по всем правилам.
    
    Args:
        text: Текст сообщения
        rules: Список правил
        
    Returns:
        Список сработавших правил с информацией о совпадениях
    """
    if not text:
        return []
    
    matched_rules = []
    
    for rule in rules:
        keywords = rule.get('keywords', [])
        case_sensitive = rule.get('case_sensitive', False)
        
        # Подготовка текста для поиска
        check_text = text if case_sensitive else text.lower()
        check_keywords = keywords if case_sensitive else [k.lower() for k in keywords]
        
        # Проверка совпадений
        for keyword in check_keywords:
            if keyword in check_text:
                matched_rules.append({
                    'rule_name': rule.get('name', 'unnamed'),
                    'matched_keyword': keyword,
                    'target_chat_ids': rule.get('target_chat_ids', [])
                })
                break  # Одного совпадения достаточно для правила
    
    return matched_rules


def get_unique_target_chats(matched_rules: List[Dict]) -> List[int]:
    """
    Собирает уникальные target чаты из всех сработавших правил.
    Дедупликация по ID чата.
    
    Args:
        matched_rules: Список сработавших правил
        
    Returns:
        Список уникальных chat_id
    """
    seen_ids = set()
    unique_chats = []
    
    for rule in matched_rules:
        for chat_id in rule['target_chat_ids']:
            if chat_id not in seen_ids:
                seen_ids.add(chat_id)
                unique_chats.append(chat_id)
    
    return unique_chats
