
import pytest
from app.handlers import check_message_against_rules, get_unique_target_chats

def test_check_message_simple_match():
    """Тест простого совпадения"""
    rules = [
        {
            'name': 'r1',
            'keywords': ['test', 'hello'],
            'target_chat_ids': [-100],
            'case_sensitive': False
        }
    ]
    
    # Совпадение
    matched = check_message_against_rules("This is a test message", rules)
    assert len(matched) == 1
    assert matched[0]['rule_name'] == 'r1'
    assert matched[0]['matched_keyword'] == 'test'
    
    # Нет совпадения
    matched = check_message_against_rules("Another message", rules)
    assert len(matched) == 0

def test_check_message_case_sensitive():
    """Тест чувствительности к регистру"""
    rules = [
        {
            'name': 'r1',
            'keywords': ['Test'],
            'target_chat_ids': [-100],
            'case_sensitive': True
        }
    ]
    
    # Не совпадает (регистр)
    matched = check_message_against_rules("this is a test", rules)
    assert len(matched) == 0
    
    # Совпадает
    matched = check_message_against_rules("this is a Test", rules)
    assert len(matched) == 1

def test_get_unique_target_chats():
    """Тест дедупликации чатов"""
    matched_rules = [
        {
            'target_chat_ids': [-100, -200]
        },
        {
            'target_chat_ids': [-200, -300]
        }
    ]
    
    unique = get_unique_target_chats(matched_rules)
    assert len(unique) == 3
    assert sorted(unique) == [-300, -200, -100]
