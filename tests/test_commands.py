
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.commands import cmd_test_message

@pytest.mark.asyncio
async def test_cmd_test_message_imports(config_mgr):
    """
    Тест проверяет, что команда /test не вызывает ModuleNotFoundError при запуске.
    Это защищает от регрессии ошибки импорта 'from handlers import ...'
    """
    # Создаем мок события
    event = MagicMock()
    event.reply = AsyncMock()
    
    # Вызываем команду (текст не важен, главное - дойти до импорта внутри функции)
    # cmd_test_message содержит 'from .handlers import ...'
    await cmd_test_message(event, config_mgr, "test text")
    
    # Проверяем, что ответ был отправлен (значит функция отработала без ModuleNotFoundError)
    assert event.reply.called
