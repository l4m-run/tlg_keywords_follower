
import pytest
import os
import json
from unittest.mock import AsyncMock, MagicMock
from app.config_manager import ConfigManager
from app.queue_manager import QueueManager

@pytest.fixture
def temp_env(tmp_path):
    """Создает временное окружение для тестов"""
    config_file = tmp_path / "config.json"
    rules_file = tmp_path / "rules.txt"
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()
    
    return {
        'config': config_file,
        'rules': rules_file,
        'queue': queue_dir
    }

@pytest.fixture
def mock_client():
    """Mock Telethon клиента"""
    client = AsyncMock()
    client.send_message = AsyncMock()
    client.forward_messages = AsyncMock()
    return client

@pytest.fixture
def config_mgr(temp_env):
    """Фикстура ConfigManager с временными файлами"""
    return ConfigManager(str(temp_env['config']), str(temp_env['rules']))

@pytest.fixture
def queue_mgr(config_mgr, temp_env):
    """Фикстура QueueManager с временной директорией"""
    return QueueManager(config_mgr, str(temp_env['queue']))

@pytest.fixture
def sample_message():
    """Mock сообщения Telethon"""
    message = MagicMock()
    message.id = 123
    message.chat_id = -100111
    message.text = "Test message text"
    return message
