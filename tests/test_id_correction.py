import pytest
from app.config_manager import ConfigManager
import os
import json

def test_id_auto_correction(tmp_path):
    """Тест автоматической коррекции ID чатов (добавление -100)"""
    config_file = tmp_path / "config.json"
    rules_file = tmp_path / "rules.txt"
    
    # Создаем rules.txt с "кривым" ID
    rules_content = "test_rule: keyword -> -3667194817\n"
    rules_file.write_text(rules_content)
    
    # Инициализируем конфиг менеджер
    cm = ConfigManager(config_file=str(config_file), rules_file=str(rules_file))
    cm.load()
    
    rules = cm.get_rules()
    assert len(rules) == 1
    # Должен добавиться префикс -100
    assert rules[0]['target_chat_ids'][0] == -1003667194817

def test_id_no_correction_for_proper_ids(tmp_path):
    """Тест того, что правильные ID не трогаются"""
    config_file = tmp_path / "config.json"
    rules_file = tmp_path / "rules.txt"
    
    # -100... и короткие ID (например, личные чаты) не должны меняться
    rules_content = (
        "rule1: k -> -1001234567890\n"
        "rule2: k -> 123456789\n"
        "rule3: k -> -123456789\n"
    )
    rules_file.write_text(rules_content)
    
    cm = ConfigManager(config_file=str(config_file), rules_file=str(rules_file))
    cm.load()
    
    rules = cm.get_rules()
    ids = {r['name']: r['target_chat_ids'][0] for r in rules}
    
    assert ids['rule1'] == -1001234567890
    assert ids['rule2'] == 123456789
    assert ids['rule3'] == -123456789
