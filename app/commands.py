"""
Команды управления правилами через Telegram Saved Messages.
"""

import logging
from telethon import events
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


def setup_commands(client, config_mgr: ConfigManager) -> None:
    """
    Регистрирует команды управления правилами.
    Команды работают только в Saved Messages (from_users='me').
    
    Args:
        client: TelegramClient instance
        config_mgr: ConfigManager instance
    """
    
    @client.on(events.NewMessage(from_users='me', pattern=r'^/\w+'))
    async def handle_commands(event):
        """Роутер команд управления"""
        text = event.text.strip()
        
        # Парсинг команды и аргументов
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''
        
        try:
            # Роутинг команд
            if command in ['/rules', '/list']:
                await cmd_list_rules(event, config_mgr)
            
            elif command == '/monitored_chats':
                await cmd_monitored_chats(event, config_mgr)
            
            elif command == '/add_chat':
                await cmd_add_chat(event, config_mgr)
            
            elif command == '/test':
                await cmd_test_message(event, config_mgr, args)
            
            elif command == '/reload':
                await cmd_reload(event, config_mgr)
            
            elif command == '/help':
                await cmd_help(event)
            
            else:
                # Неизвестная команда
                await event.reply(
                    f"❌ Неизвестная команда: {command}\n\n"
                    f"Используйте /help для списка команд"
                )
        
        except Exception as e:
            logger.error(f"Ошибка выполнения команды {command}: {e}", exc_info=True)
            await event.reply(f"❌ Ошибка: {e}")
    
    logger.info("✅ Команды управления зарегистрированы")


async def cmd_list_rules(event, config_mgr) -> None:
    """Показывает список всех правил"""
    rules = config_mgr.get_rules()
    
    if not rules:
        await event.reply("📋 Нет активных правил")
        return
    
    text = f"📋 Активные правила ({len(rules)}):\n\n"
    
    for i, rule in enumerate(rules, 1):
        name = rule.get('name', 'unnamed')
        keywords = rule.get('keywords', [])
        target_ids = rule.get('target_chat_ids', [])
        case_sensitive = rule.get('case_sensitive', False)
        
        keywords_str = ', '.join(keywords)
        targets_str = ', '.join(str(id) for id in target_ids)
        case_str = "⚠️ ВАЖЕН" if case_sensitive else "не важен"
        
        text += f"{i}️⃣ **{name}**\n"
        text += f"   📝 Ключевые слова: {keywords_str} ({len(keywords)})\n"
        text += f"   📤 Целевые чаты: {targets_str} ({len(target_ids)})\n"
        text += f"   🔤 Регистр: {case_str}\n\n"
    
    await event.reply(text)


async def cmd_monitored_chats(event, config_mgr) -> None:
    """Показывает список мониторимых чатов"""
    monitored = config_mgr.config.get('monitored_chats', [])
    
    if not monitored:
        await event.reply("👁 Нет мониторимых чатов\n\nДобавьте бота в группу для автоматического добавления")
        return
    
    text = f"👁 Мониторимые чаты ({len(monitored)}):\n\n"
    
    for i, chat in enumerate(monitored, 1):
        chat_id = chat.get('id', 'Unknown')
        chat_name = chat.get('name', 'Unknown')
        text += f"{i}. `{chat_id}` - \"{chat_name}\"\n"
    
    text += "\n💡 Для использования в правилах копируйте chat_id"
    
    await event.reply(text)


async def cmd_add_chat(event, config_mgr) -> None:
    """
    Добавляет чат в monitored_chats через пересылку сообщения.
    Работает для групп И каналов!
    """
    # Проверяем что есть пересланное сообщение
    if not event.message.is_reply:
        await event.reply(
            "❌ **Использование:**\n\n"
            "1️⃣ Перешлите любое сообщение из канала/группы в Saved Messages\n"
            "2️⃣ Ответьте на это сообщение командой `/add_chat`\n\n"
            "💡 Это работает даже для каналов!"
        )
        return
    
    try:
        # Получаем пересланное сообщение
        reply_msg = await event.get_reply_message()
        
        # Проверяем откуда переслано
        if not reply_msg.fwd_from:
            await event.reply("❌ Это сообщение не является пересланным (или скрыт автор).")
            return

        # Пытаемся получить сущность оригинального чата
        # fwd_from.from_id может быть PeerChannel, PeerUser или PeerChat
        if reply_msg.fwd_from.from_id:
            chat = await event.client.get_entity(reply_msg.fwd_from.from_id)
        elif reply_msg.fwd_from.from_name:
            await event.reply(f"❌ Не могу получить ID чата: автор скрыл свой профиль (имя: {reply_msg.fwd_from.from_name})")
            return
        else:
            # Fallback (иногда бывает forward_to)
            chat = await reply_msg.get_chat()
            
        chat_id = chat.id
        
        # Получаем название
        if hasattr(chat, 'title'):
            chat_name = chat.title
        elif hasattr(chat, 'first_name'):
            # Если переслано от пользователя - берем имя
            last = getattr(chat, 'last_name', '') or ''
            chat_name = f"{chat.first_name} {last}".strip()
        else:
            chat_name = 'Unknown'
        
        # Добавляем в monitored_chats
        added = config_mgr.add_monitored_chat(chat_id, chat_name)
        
        if added:
            await event.reply(
                f"✅ **Чат добавлен в мониторинг!**\n\n"
                f"📝 Название: {chat_name}\n"
                f"🆔 Chat ID: `{chat_id}`\n\n"
                f"💡 Теперь скопируйте этот ID в `rules.txt`"
            )
        else:
            await event.reply(
                f"ℹ️ **Чат уже в мониторинге**\n\n"
                f"📝 Название: {chat_name}\n"
                f"🆔 Chat ID: `{chat_id}`"
            )
    
    except Exception as e:
        logger.error(f"Ошибка в cmd_add_chat: {e}", exc_info=True)
        await event.reply(f"❌ Ошибка: {e}")


async def cmd_test_message(event, config_mgr, test_text: str) -> None:
    """Проверяет какие правила сработают для заданного текста"""
    if not test_text:
        await event.reply("❌ Использование: /test <текст сообщения>")
        return
    
    from handlers import check_message_against_rules, get_unique_target_chats
    
    rules = config_mgr.get_rules()
    matched_rules = check_message_against_rules(test_text, rules)
    
    if not matched_rules:
        await event.reply(f"🧪 Тест: \"{test_text}\"\n\n❌ Ни одно правило не сработало")
        return
    
    unique_chats = get_unique_target_chats(matched_rules)
    
    text = f"🧪 Тест: \"{test_text}\"\n\n✅ Сработали правила:\n\n"
    
    for i, rule in enumerate(matched_rules, 1):
        rule_name = rule['rule_name']
        keyword = rule['matched_keyword']
        targets = rule['target_chat_ids']
        
        text += f"{i}️⃣ **{rule_name}**\n"
        text += f"   🎯 Совпало: \"{keyword}\"\n"
        text += f"   📤 Отправится в: {', '.join(str(id) for id in targets)}\n\n"
    
    text += f"📊 Итого: {len(matched_rules)} правил, {len(unique_chats)} уникальных чатов"
    
    await event.reply(text)


async def cmd_reload(event, config_mgr) -> None:
    """Перечитывает конфигурацию с диска"""
    try:
        config_mgr.load()
        rules_count = len(config_mgr.get_rules())
        monitored_count = len(config_mgr.config.get('monitored_chats', []))
        
        await event.reply(
            f"✅ Конфигурация перезагружена\n\n"
            f"📊 Правил: {rules_count}\n"
            f"👁 Мониторимых чатов: {monitored_count}"
        )
    except Exception as e:
        await event.reply(f"❌ Ошибка перезагрузки: {e}")


async def cmd_help(event) -> None:
    """Показывает справку по командам"""
    help_text = """📖 **Справка по командам**

**Просмотр:**
`/rules` - список всех правил
`/monitored_chats` - список мониторимых чатов  
`/test <текст>` - проверить какие правила сработают

**Добавление чатов:**
`/add_chat` - добавить канал/группу через пересылку

**Как использовать /add_chat:**
1️⃣ Перешлите сообщение из канала в Saved Messages
2️⃣ Ответьте на него: `/add_chat`
3️⃣ Скопируйте полученный chat_id в rules.txt

**Системные:**
`/reload` - перечитать rules.txt
`/help` - эта справка

**Настройка:**
Редактируйте `app_data/rules.txt` на сервере:
```
# Формат:
название: ключевые_слова -> chat_id "Название"

# Примеры:
urgent: срочно, важно -> -1001234 "Важные новости"
trading: deal, price -> -1005678 "Трейдинг"
```

После редактирования используйте `/reload`

📚 Подробности в файле `USER_GUIDE.md`
"""
    
    await event.reply(help_text)
