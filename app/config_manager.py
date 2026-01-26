"""
Менеджер конфигурации для Telegram UserBot.
Управление config.json и rules.txt.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Менеджер конфигурации бота"""
    
    def __init__( self,
                 config_file: str = 'app_data/config.json',
                 rules_file: str = 'app_data/rules.txt'):
        """
        Инициализация менеджера конфигурации.
        
        Args:
            config_file: Путь к файлу config.json
            rules_file: Путь к файлу rules.txt
        """
        # Создаем директорию app_data, если не существует
        Path('app_data').mkdir(exist_ok=True)
        
        self.config_file = config_file
        self.rules_file = rules_file
        self.config: Dict[str, Any] = {}
    
    def load(self) -> None:
        """Загружает конфигурацию из файлов"""
        self._load_config_json()
        
        # Миграция из rules.txt если он есть
        self._migrate_rules_if_needed()
        
        self._validate_and_clean()
        self.save()
        logger.info("Конфигурация загружена успешно")
    
    def _load_config_json(self) -> None:
        """Загрузка config.json"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.warning(f"{self.config_file} не найден, создаём default")
            self._create_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга {self.config_file}: {e}")
            raise
    
    def _create_default_config(self) -> None:
        """Создание конфигурации по умолчанию"""
        self.config = {
            'monitored_chats': [],
            'rules': [],
            'forward_mode': 'copy',
            'auto_add_chats': True
        }
        self.save()
    
    def _migrate_rules_if_needed(self) -> None:
        """
        Миграция правил из rules.txt в config.json.
        Выполняется один раз, после чего rules.txt переименовывается в rules.txt.bak.
        """
        rules_path = Path(self.rules_file)
        if not rules_path.exists():
            return

        logger.info(f"Обнаружен {self.rules_file}, начинаем миграцию правил...")
        
        rules = []
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    try:
                        rule = self._parse_rule_line(line)
                        if rule:
                            rules.append(rule)
                    except Exception as e:
                        logger.error(f"Ошибка миграции строки {line_num}: {e}")
            
            if rules:
                current_rules = self.config.get('rules', [])
                current_names = {r.get('name') for r in current_rules}
                
                added_count = 0
                for rule in rules:
                    if rule.get('name') not in current_names:
                        current_rules.append(rule)
                        added_count += 1
                
                self.config['rules'] = current_rules
                logger.info(f"Миграция завершена: добавлено {added_count} правил")
            
            # Переименовываем файл
            bak_path = rules_path.with_suffix('.txt.bak')
            # Если бак уже есть, добавим индекс
            if bak_path.exists():
                from datetime import datetime
                bak_path = rules_path.with_suffix(f'.txt.{datetime.now().strftime("%Y%m%d%H%M%S")}.bak')
                
            rules_path.rename(bak_path)
            logger.info(f"Файл {self.rules_file} переименован в {bak_path.name}")
            
        except Exception as e:
            logger.error(f"Критическая ошибка при миграции правил: {e}")
    
    def _load_rules_txt(self) -> None:
        """Загрузка и парсинг rules.txt"""
        rules_path = Path(self.rules_file)
        
        if not rules_path.exists():
            logger.warning(f"{self.rules_file} не найден")
            self.config['rules'] = []
            return
        
        rules = []
        with open(self.rules_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Пропуск комментариев и пустых строк
                if not line or line.startswith('#'):
                    continue
                
                try:
                    rule = self._parse_rule_line(line)
                    if rule:
                        rules.append(rule)
                except Exception as e:
                    logger.error(f"Ошибка парсинга строки {line_num}: {e}")
        
        self.config['rules'] = rules
        logger.info(f"Загружено {len(rules)} правил из {self.rules_file}")
    
    def _parse_rule_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг строки правила.
        Формат: name: keywords -> chat_id "Name", chat_id2 "Name2" [case:on]
        
        Args:
            line: Строка для парсинга
            
        Returns:
            Словарь с правилом или None при ошибке
        """
        # Проверка базового формата
        if ':' not in line or '->' not in line:
            logger.warning(f"Неверный формат строки: {line}")
            return None
        
        # Разделяем на части
        name_part, rest = line.split(':', 1)
        keywords_part, targets_part = rest.split('->', 1)
        
        # Извлекаем опции
        case_sensitive = False
        if '[case:on]' in targets_part:
            case_sensitive = True
            targets_part = targets_part.replace('[case:on]', '')
        
        # Парсим название
        name = name_part.strip()
        if not name:
            logger.warning("Пустое название правила")
            return None
        
        # Парсим ключевые слова
        keywords = [k.strip() for k in keywords_part.split(',') if k.strip()]
        if not keywords:
            logger.warning(f"Правило '{name}': нет ключевых слов")
            return None
        
        # Парсим целевые чаты с названиями
        target_chat_ids = []
        chat_entries = re.split(r',\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', targets_part)
        
        for entry in chat_entries:
            entry = entry.strip()
            if not entry:
                continue
            
            match = re.match(r'(-?\d+)(?:\s+"([^"]+)")?', entry)
            if match:
                chat_id_raw = match.group(1)
                chat_id = self._correct_chat_id(int(chat_id_raw))
                target_chat_ids.append(chat_id)
            else:
                logger.warning(f"Не удалось распарсить целевой чат: {entry}")
        
        if not target_chat_ids:
            logger.warning(f"Правило '{name}': нет целевых чатов")
            return None
        
        return {
            'name': name,
            'keywords': keywords,
            'target_chat_ids': target_chat_ids,
            'case_sensitive': case_sensitive
        }

    def _correct_chat_id(self, chat_id: int) -> int:
        """
        Корректирует ID чата, добавляя префикс -100 для каналов и супергрупп,
        если он отсутствует. Telethon использует маркированные ID.
        """
        chat_str = str(chat_id)
        
        # Если ID уже правильный (начинается на -100) - не трогаем
        if chat_str.startswith('-100'):
            return chat_id
            
        # Если чат отрицательный, но без -100 и длинный (обычно > 8 цифр)
        if chat_id < 0 and len(chat_str) >= 10:
            return int(f"-100{abs(chat_id)}")
            
        # Если чат положительный и длинный (вероятно ID канала от бота)
        if chat_id > 0 and len(chat_str) >= 9:
            return int(f"-100{chat_id}")
            
        return chat_id
    
    def _validate_and_clean(self) -> None:
        """
        Валидация, коррекция ID и очистка от зацикливаний.
        """
        # 1. Корректируем ID в правилах
        for rule in self.config.get('rules', []):
            rule['target_chat_ids'] = [self._correct_chat_id(id) for id in rule.get('target_chat_ids', [])]
            
        # 2. Корректируем ID в monitored_chats
        monitored = self.config.get('monitored_chats', [])
        for chat in monitored:
            if isinstance(chat, dict) and 'id' in chat:
                chat['id'] = self._correct_chat_id(chat['id'])
            elif isinstance(chat, int):
                # Старый формат (просто список ID)
                pass # Это будет обработано ниже при перепаковке в словари
                
        # 3. Собираем все target чаты для защиты от зацикливания
        all_target_ids = set()
        for rule in self.config.get('rules', []):
            all_target_ids.update(rule.get('target_chat_ids', []))
        
        # 4. Фильтруем monitored_chats
        cleaned = []
        removed_ids = []
        
        for chat in monitored:
            if isinstance(chat, dict):
                chat_id = chat.get('id')
                if chat_id not in all_target_ids:
                    cleaned.append(chat)
                else:
                    removed_ids.append(chat_id)
            elif isinstance(chat, int):
                corrected_id = self._correct_chat_id(chat)
                if corrected_id not in all_target_ids:
                    cleaned.append({'id': corrected_id, 'name': 'Unknown'})
                else:
                    removed_ids.append(corrected_id)
        
        if removed_ids:
            logger.warning(f"Удалены target чаты из monitored_chats: {removed_ids}")
        
        self.config['monitored_chats'] = cleaned

    def save(self) -> None:
        """Сохраняет конфигурацию в config.json"""
        self._save_config_json()
        logger.info("Конфигурация сохранена")

    def _save_config_json(self) -> None:
        """Сохранение config.json"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def save_rules_to_file(self) -> None:
        """Заглушка (теперь всё хранится в config.json)"""
        pass
    
    def add_monitored_chat(self, chat_id: int, chat_name: str) -> bool:
        """
        Добавляет чат в monitored_chats.
        
        Args:
            chat_id: ID чата
            chat_name: Название чата
            
        Returns:
            True если добавлен, False если уже существует или это target_chat
        """
        # Проверка что это не target чат
        all_target_ids = set()
        for rule in self.config.get('rules', []):
            all_target_ids.update(rule.get('target_chat_ids', []))
        
        if chat_id in all_target_ids:
            logger.warning(f"Чат {chat_id} является target_chat, не добавляем в monitored")
            return False
        
        # Проверка дубликатов
        monitored = self.config.get('monitored_chats', [])
        for chat in monitored:
            if chat.get('id') == chat_id:
                logger.info(f"Чат {chat_id} уже в monitored_chats")
                return False
        
        # Добавляем
        monitored.append({'id': chat_id, 'name': chat_name})
        self.config['monitored_chats'] = monitored
        self.save()
        logger.info(f"Добавлен чат в monitored_chats: {chat_name} ({chat_id})")
        return True
    
    def get_monitored_chat_ids(self) -> List[int]:
        """Возвращает список ID мониторимых чатов"""
        return [chat['id'] for chat in self.config.get('monitored_chats', [])]
    
    def get_rules(self) -> List[Dict]:
        """Возвращает список правил"""
        return self.config.get('rules', [])
    
    def get_forward_mode(self) -> str:
        """Возвращает режим пересылки"""
        return self.config.get('forward_mode', 'copy')
    
    def get_auto_add_chats(self) -> bool:
        """Возвращает настройку автоматического добавления чатов"""
        return self.config.get('auto_add_chats', True)

    def add_rule(self, name: str, keywords: List[str], target_chat_ids: List[int], case_sensitive: bool = False) -> None:
        """
        Добавляет или обновляет правило.
        
        Args:
            name: Название правила
            keywords: Список ключевых слов
            target_chat_ids: Список ID целевых чатов
            case_sensitive: Учитывать ли регистр
        """
        rules = self.config.get('rules', [])
        
        # Ищем существующее правило
        existing_rule = next((r for r in rules if r.get('name') == name), None)
        
        new_rule = {
            'name': name,
            'keywords': keywords,
            'target_chat_ids': target_chat_ids,
            'case_sensitive': case_sensitive
        }
        
        if existing_rule:
            rules[rules.index(existing_rule)] = new_rule
            logger.info(f"Обновлено правило: {name}")
        else:
            rules.append(new_rule)
            logger.info(f"Добавлено новое правило: {name}")
            
        self.config['rules'] = rules
        self._validate_and_clean()  # Очистка и коррекция ID
        self.save()                 # Сохраняем в config.json

    def remove_rule(self, name: str) -> bool:
        """
        Удаляет правило по имени.
        
        Args:
            name: Название правила
            
        Returns:
            True если удалено, False если не найдено
        """
        rules = self.config.get('rules', [])
        original_len = len(rules)
        
        rules = [r for r in rules if r.get('name') != name]
        
        if len(rules) < original_len:
            self.config['rules'] = rules
            self.save()
            logger.info(f"Удалено правило: {name}")
            return True
        
        logger.warning(f"Правило не найдено для удаления: {name}")
        return False
