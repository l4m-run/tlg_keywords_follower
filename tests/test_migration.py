
import os
import json
from pathlib import Path
from app.config_manager import ConfigManager

def test_migration_and_id_correction(tmp_path):
    # Подготовка временных файлов
    config_file = tmp_path / "config.json"
    rules_file = tmp_path / "rules.txt"
    
    # 1. Создаем rules.txt с различными форматами ID
    rules_content = (
        "rule1: key1 -> 1234567890 \"Test\"\n"  # Нужна коррекция до -1001234567890
        "rule2: key2 -> -100987654321 \"Already OK\"\n"
        "rule3: key3 -> -3667194817 \"Needs -100\"\n" # Превратится в -1003667194817
    )
    rules_file.write_text(rules_content, encoding='utf-8')
    
    # 2. Создаем начальный config.json с мониторимыми чатами, требующими коррекции
    initial_config = {
        "monitored_chats": [
            {"id": 1685349748, "name": "Lpr 1"}, # Нужна коррекция
            {"id": -1002319552152, "name": "Already OK"}
        ],
        "rules": [],
        "forward_mode": "forward",
        "auto_add_chats": True
    }
    config_file.write_text(json.dumps(initial_config), encoding='utf-8')
    
    # Инициализируем менеджер
    # ВАЖНО: Нам нужно мокнуть Path('app_data').mkdir, так как ConfigManager ее делает
    # Но для теста мы просто укажем прямые пути
    mgr = ConfigManager(config_file=str(config_file), rules_file=str(rules_file))
    
    # Здесь мы будем внедрять логику миграции в mgr.load()
    # Пока просто проверяем, что мы можем вызвать загрузку и она сработает (после наших правок в коде)
    
    print(f"Testing with files: {config_file} and {rules_file}")
    
if __name__ == "__main__":
    # Для ручного запуска
    import sys
    from unittest.mock import MagicMock
    
    # Создаем фейковый tmp_path если запускаем не через pytest
    class TmpPath:
        def __div__(self, other): return Path(f"/tmp/{other}")
        def __truediv__(self, other):
            p = Path("/tmp/test_tlg") / other
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
            
    test_migration_and_id_correction(TmpPath())
    print("Test setup complete (not actual test yet)")
