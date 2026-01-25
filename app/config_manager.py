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
                 config_file: str = 'config.json',
                 rules_file: str = 'rules.txt'):
        """
        Инициализация менеджера конфигурации.
        
        Args:
            config_file: Путь к файлу config.json
            rules_file: Путь к файлу rules.txt
        """
        self.config_file = config_file
        self.rules_file = rules_file
        self.config: Dict[str, Any] = {}
    
    def load(self) -> None:
        """Загружает конфигурацию из файлов"""
        self._load_config_json()
        self._load_rules_txt()
        self._validate_and_clean()
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
        # Формат: chat_id "Name", chat_id2 "Name2"
        target_chat_ids = []
        
        # Разделяем по запятым, игнорируя запятые внутри кавычек
        # Используем lookahead для проверки четного количества кавычек впереди
        chat_entries = re.split(r',\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', targets_part)
        
        for entry in chat_entries:
            entry = entry.strip()
            if not entry:
                continue
            
            # Пытаемся извлечь ID и название
            # Формат: -1001234 "Название" или просто -1001234
            match = re.match(r'(-?\d+)(?:\s+"([^"]+)")?', entry)
            if match:
                chat_id = int(match.group(1))
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
    
    def _validate_and_clean(self) -> None:
        """
        Валидация и очистка monitored_chats.
        Убирает все target_chat_ids из monitored_chats для защиты от зацикливания.
        """
        # Собираем все target чаты из всех правил
        all_target_ids = set()
        for rule in self.config.get('rules', []):
            all_target_ids.update(rule.get('target_chat_ids', []))
        
        monitored = self.config.get('monitored_chats', [])
        
        # Фильтруем - monitored это список объектов {"id": ..., "name": ...}
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
                # Обратная совместимость со старым форматом
                if chat not in all_target_ids:
                    cleaned.append({'id': chat, 'name': 'Unknown'})
                else:
                    removed_ids.append(chat)
        
        if removed_ids:
            logger.warning(f"Удалены target чаты из monitored_chats: {removed_ids}")
        
        self.config['monitored_chats'] = cleaned
    
    def save(self) -> None:
        """Сохраняет конфигурацию в файлы"""
        self._save_config_json()
        logger.info("Конфигурация сохранена")
    
    def _save_config_json(self) -> None:
        """Сохранение config.json"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def save_rules_to_file(self) -> None:
        """Сохранение правил в rules.txt"""
        with open(self.rules_file, 'w', encoding='utf-8') as f:
            f.write("# Правила пересылки сообщений\n")
            f.write("# Формат: name: keywords -> chat_id \"Name\" [case:on]\n\n")
            
            for rule in self.config.get('rules', []):
                name = rule.get('name', 'unnamed')
                keywords = ', '.join(rule.get('keywords', []))
                target_ids = ', '.join(str(id) for id in rule.get('target_chat_ids', []))
                case_flag = ' [case:on]' if rule.get('case_sensitive', False) else ''
                
                f.write(f"{name}: {keywords} -> {target_ids}{case_flag}\n")
        
        logger.info(f"Правила сохранены в {self.rules_file}")
    
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
