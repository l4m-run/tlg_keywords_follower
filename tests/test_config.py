
import pytest
import json
import os

def test_load_config_defaults(config_mgr, temp_env):
    """Тест создания дефолтного конфига"""
    config_mgr.load()
    assert config_mgr.config['forward_mode'] == 'copy'
    assert config_mgr.config['auto_add_chats'] is True
    assert os.path.exists(temp_env['config'])

def test_load_existing_config(config_mgr, temp_env):
    """Тест загрузки существующего конфига"""
    data = {
        'forward_mode': 'forward',
        'auto_add_chats': False,
        'monitored_chats': [{'id': 123, 'name': 'Test'}]
    }
    with open(temp_env['config'], 'w') as f:
        json.dump(data, f)
    
    config_mgr.load()
    assert config_mgr.config['forward_mode'] == 'forward'
    assert config_mgr.config['auto_add_chats'] is False
    assert len(config_mgr.get_monitored_chat_ids()) == 1

def test_parse_rules(config_mgr, temp_env):
    """Тест парсинга правил из файла"""
    rules_content = '''
    # Comment
    rule1: keyword1, keyword2 -> -100 "Group1"
    rule2: key3 -> -200 "Group2", -300 "Group3" [case:on]
    '''
    with open(temp_env['rules'], 'w') as f:
        f.write(rules_content)
    
    config_mgr.load()
    rules = config_mgr.get_rules()
    
    assert len(rules) == 2
    
    # Проверка rule1
    r1 = rules[0]
    assert r1['name'] == 'rule1'
    assert 'keyword1' in r1['keywords']
    assert len(r1['target_chat_ids']) == 1
    assert r1['target_chat_ids'][0] == -100
    assert r1['case_sensitive'] is False
    
    # Проверка rule2
    r2 = rules[1]
    assert r2['name'] == 'rule2'
    assert r2['case_sensitive'] is True
    assert len(r2['target_chat_ids']) == 2

def test_add_monitored_chat(config_mgr):
    """Тест добавления чата в мониторинг"""
    config_mgr.load()
    
    # Добавление нового
    added = config_mgr.add_monitored_chat(123, "New Chat")
    assert added is True
    assert 123 in config_mgr.get_monitored_chat_ids()
    
    # Добавление дубликата
    added = config_mgr.add_monitored_chat(123, "New Chat")
    assert added is False
