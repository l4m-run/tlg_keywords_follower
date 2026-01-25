
import pytest
import json
import asyncio
from pathlib import Path

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

def test_get_queue_items_sorting(queue_mgr, sample_message):
    """Тест сортировки очереди"""
    # Добавляем два сообщения с паузой
    data = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [],
        'forward_mode': 'copy'
    }
    
    queue_mgr.add_to_queue(data)
    # Имитация задержки через названия (таймстемп в имени)
    # На самом деле add_to_queue использует time.time(), 
    # в тесте они могут быть созданы очень быстро, но порядок должен сохраняться
    queue_mgr.add_to_queue(data)
    
    items = queue_mgr.get_queue_items()
    assert len(items) == 2
    # Проверяем что имена файлов разные и верного формата
    assert items[0].name < items[1].name

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
async def test_process_queue_success(queue_mgr, mock_client, sample_message):
    """Тест успешной обработки очереди"""
    # Подготовка данных
    data = {
        'message': sample_message,
        'target_chats': [-1001],
        'matched_rules': [{'rule_name': 'r1'}],
        'forward_mode': 'copy'
    }
    queue_mgr.add_to_queue(data)
    
    # Запускаем process_queue в фоне, но прерываем его, 
    # чтобы не зависнуть в бесконечном цикле.
    # Но лучше тестировать логику внутри цикла или отдельные методы.
    # Здесь протестируем send_message_safe напрямую
    
    items = queue_mgr.get_queue_items()
    with open(items[0], 'r') as f:
        msg_data = json.load(f)
        
    # Настройка мока успешной отправки
    mock_client.send_message.return_value = None
    
    result = await queue_mgr.send_message_safe(
        mock_client,
        -1001,
        msg_data,
        'copy',
        ['r1']
    )
    
    assert result is True
    # Проверка вызова client.send_message дважды (текст + инфо о правиле)
    assert mock_client.send_message.call_count == 2
