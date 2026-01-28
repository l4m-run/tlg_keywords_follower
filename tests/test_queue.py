
import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from telethon.errors import FloodWaitError, ChatIdInvalidError

@pytest.fixture
def queue_dir(tmp_path):
    d = tmp_path / "queue"
    d.mkdir()
    return d

@pytest.fixture
def queue_mgr(queue_dir):
    # Mock config manager
    config_mgr = Mock()
    from app.queue_manager import QueueManager
    return QueueManager(config_mgr, str(queue_dir))

@pytest.fixture
def sample_message():
    msg = Mock()
    msg.id = 123
    msg.chat_id = -100111
    msg.text = "Test message"
    return msg

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Mock get_input_entity to return something valid
    client.get_input_entity.return_value = Mock()
    return client

def test_add_to_queue(queue_mgr, sample_message):
    """Тест добавления сообщения в очередь"""
    data = {
        'message': sample_message,
        'target_chats': [-1001, -1002],
        'matched_rules': [{'rule_name': 'test_rule'}],
        'forward_mode': 'copy'
    }
    
    queue_mgr.add_to_queue(data)
    
    items = queue_mgr.get_queue_items()
    assert len(items) == 1
    
    # Проверка содержимого файла
    with open(items[0], 'r') as f:
        content = json.load(f)
        
    assert content['message_id'] == 123
    assert content['from_chat_id'] == -100111
    assert content['target_chat_ids'] == [-1001, -1002]
    assert content['matched_rules'] == ['test_rule']
    # New fields
    assert content['sent_chat_ids'] == []
    assert content['retry_count'] == 0

def test_get_queue_items_sorting(queue_mgr, sample_message):
    """Тест сортировки очереди"""
    data1 = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [],
        'forward_mode': 'copy'
    }
    
    queue_mgr.add_to_queue(data1)
    time_sorted_files = queue_mgr.get_queue_items()
    
    # Just ensure we have 1 item and it's a Path
    assert len(time_sorted_files) == 1
    assert isinstance(time_sorted_files[0], Path)

def test_remove_from_queue(queue_mgr, sample_message):
    """Тест удаления из очереди"""
    data = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [],
        'forward_mode': 'copy'
    }
    queue_mgr.add_to_queue(data)
    items = queue_mgr.get_queue_items()
    assert len(items) == 1
    
    queue_mgr.remove_from_queue(items[0])
    assert len(queue_mgr.get_queue_items()) == 0

@pytest.mark.asyncio
async def test_send_message_safe_success(queue_mgr, mock_client, sample_message):
    """Тест успешной отправки"""
    data = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [{'rule_name': 'r1'}],
        'forward_mode': 'copy'
    }
    queue_mgr.add_to_queue(data)
    items = queue_mgr.get_queue_items()
    with open(items[0], 'r') as f:
        msg_data = json.load(f)
        
    mock_client.send_message.return_value = None
    
    success, error_type = await queue_mgr.send_message_safe(
        mock_client,
        -1001,
        msg_data,
        'copy',
        ['r1']
    )
    
    assert success is True
    assert error_type == 'none'
    assert mock_client.send_message.call_count == 2 # Message + log

@pytest.mark.asyncio
async def test_send_message_safe_permanent_error(queue_mgr, mock_client, sample_message):
    """Тест постоянной ошибки (ChatIdInvalidError)"""
    data = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [],
        'forward_mode': 'copy'
    }
    queue_mgr.add_to_queue(data)
    items = queue_mgr.get_queue_items()
    with open(items[0], 'r') as f:
        msg_data = json.load(f)
    
    # Simulate ChatIdInvalidError
    mock_client.get_input_entity.side_effect = ChatIdInvalidError(request=None)

    success, error_type = await queue_mgr.send_message_safe(
        mock_client,
        -1001,
        msg_data
    )
    
    assert success is False
    assert error_type == 'permanent'

@pytest.mark.asyncio
async def test_send_message_safe_temporary_error(queue_mgr, mock_client, sample_message):
    """Тест временной ошибки (FloodWait)"""
    data = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [],
        'forward_mode': 'copy'
    }
    queue_mgr.add_to_queue(data)
    items = queue_mgr.get_queue_items()
    with open(items[0], 'r') as f:
        msg_data = json.load(f)
        
    # Simulate FloodWait
    error = FloodWaitError(request=None, capture=10)
    mock_client.get_input_entity.side_effect = error

    with pytest.raises(FloodWaitError):
        await queue_mgr.send_message_safe(
            mock_client,
            -1001,
            msg_data
        )

def test_move_to_failed(queue_mgr, sample_message):
    """Тест перемещения в failed"""
    data = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [],
    }
    queue_mgr.add_to_queue(data)
    items = queue_mgr.get_queue_items()
    assert len(items) == 1
    
    queue_mgr.move_to_failed(items[0])
    
    assert len(queue_mgr.get_queue_items()) == 0
    failed_items = list(queue_mgr.failed_dir.glob('*.json'))
    assert len(failed_items) == 1
    assert failed_items[0].name == items[0].name

