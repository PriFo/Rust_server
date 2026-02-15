"""
Модуль для проверки ошибок при инициализации базы данных
Проверяет ошибки в БД и файлах логов, определяет место для продолжения инициализации
"""
import re
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from datetime import datetime
from src.logger import Logger, LogCategory
from src.repository import Repository
from os import getenv


class InitializationChecker:
    """Класс для проверки ошибок при инициализации"""
    
    def __init__(self, logs_dir: Optional[str] = None):
        self.logger = Logger("InitializationChecker")
        self.repo = Repository()
        self.logs_dir = Path(logs_dir) if logs_dir else Path.cwd() / "logs"
        self.admin_id = getenv('ADMIN_ID', '517965582')
    
    def check_db_errors(self) -> Optional[Dict]:
        """
        Проверяет наличие ошибок инициализации в базе данных
        
        Returns:
            Dict с информацией об ошибке или None, если ошибок нет
            Формат: {
                'error_type': str,  # 'servers_loading' или 'players_loading'
                'error_url': str,     # URL страницы, на которой произошла ошибка
                'error_message': str, # Сообщение об ошибке
                'source': 'db'        # Источник ошибки
            }
        """
        try:
            init_state = self.repo.get_initialization_state(self.admin_id)
            if init_state:
                init_state['source'] = 'db'
                self.logger.info("Обнаружена ошибка инициализации в БД", {
                    'error_type': init_state.get('error_type'),
                    'error_url': init_state.get('error_url')
                }, category=LogCategory.INITIALIZATION)
                return init_state
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при проверке БД: {e}", category=LogCategory.INITIALIZATION)
            return None
    
    def check_file_logs(self) -> Optional[Dict]:
        """
        Проверяет наличие ошибок инициализации в файлах логов
        
        Returns:
            Dict с информацией об ошибке или None, если ошибок нет
            Формат: {
                'error_type': str,      # 'servers_loading' или 'players_loading'
                'error_url': str,        # URL страницы, на которой произошла ошибка
                'error_message': str,    # Сообщение об ошибке
                'source': 'file',        # Источник ошибки
                'log_file': str,         # Путь к файлу лога
                'line_number': int       # Номер строки в файле
            }
        """
        try:
            # Ищем файлы логов с категорией Initialization
            log_files = sorted(self.logs_dir.glob("initialization_*.log"), reverse=True)
            
            if not log_files:
                self.logger.debug("Файлы логов инициализации не найдены", category=LogCategory.INITIALIZATION)
                return None
            
            # Проверяем последний файл лога
            latest_log = log_files[0]
            self.logger.debug(f"Проверка файла лога: {latest_log}", category=LogCategory.INITIALIZATION)
            
            error_info = self._parse_log_file(latest_log)
            if error_info:
                error_info['source'] = 'file'
                error_info['log_file'] = str(latest_log)
                self.logger.info("Обнаружена ошибка инициализации в файле лога", {
                    'error_type': error_info.get('error_type'),
                    'log_file': str(latest_log)
                }, category=LogCategory.INITIALIZATION)
                return error_info
            
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при проверке файлов логов: {e}", category=LogCategory.INITIALIZATION)
            return None
    
    def _parse_log_file(self, log_file: Path) -> Optional[Dict]:
        """
        Парсит файл лога и ищет ошибки инициализации
        
        Returns:
            Dict с информацией об ошибке или None
        """
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Ищем последнюю критическую ошибку инициализации
            error_patterns = [
                (r'Критическая ошибка при загрузке серверов', 'servers_loading'),
                (r'Критическая ошибка при загрузке игроков', 'players_loading'),
                (r'Ошибка при получении серверов', 'servers_loading'),
                (r'Ошибка при получении игроков', 'players_loading'),
            ]
            
            url_pattern = r'URL страницы[:\s]+(https?://[^\s]+)'
            error_message_pattern = r'Ошибка[:\s]+(.+?)(?:\n|$)'
            
            last_error = None
            last_error_type = None
            last_url = None
            last_line_num = 0
            
            for line_num, line in enumerate(lines, 1):
                # Проверяем паттерны ошибок
                for pattern, error_type in error_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        last_error = line.strip()
                        last_error_type = error_type
                        last_line_num = line_num
                
                # Ищем URL
                url_match = re.search(url_pattern, line, re.IGNORECASE)
                if url_match:
                    last_url = url_match.group(1)
            
            if last_error and last_error_type:
                return {
                    'error_type': last_error_type,
                    'error_url': last_url or '',
                    'error_message': last_error,
                    'line_number': last_line_num
                }
            
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при парсинге файла лога {log_file}: {e}", category=LogCategory.INITIALIZATION)
            return None
    
    def check_db_write_errors(self) -> List[Dict]:
        """
        Проверяет наличие ошибок записи в БД в файлах логов
        
        Returns:
            List[Dict] со списком ошибок записи в БД
            Формат каждого элемента: {
                'error_message': str,
                'log_file': str,
                'line_number': int,
                'timestamp': str
            }
        """
        errors = []
        try:
            # Ищем файлы логов с категорией DBWrite
            log_files = sorted(self.logs_dir.glob("dbwrite_*.log"), reverse=True)
            
            if not log_files:
                return errors
            
            # Проверяем последние файлы логов (за последние 7 дней)
            for log_file in log_files[:7]:
                file_errors = self._parse_db_write_errors(log_file)
                errors.extend(file_errors)
            
            if errors:
                self.logger.warning(f"Обнаружено {len(errors)} ошибок записи в БД", {
                    'errors_count': len(errors)
                }, category=LogCategory.DBWRITE)
            
            return errors
        except Exception as e:
            self.logger.error(f"Ошибка при проверке ошибок записи в БД: {e}", category=LogCategory.DBWRITE)
            return []
    
    def _parse_db_write_errors(self, log_file: Path) -> List[Dict]:
        """
        Парсит файл лога и ищет ошибки записи в БД
        
        Returns:
            List[Dict] со списком ошибок
        """
        errors = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            error_patterns = [
                r'Не удалось записать',
                r'Ошибка при записи в БД',
                r'Ошибка при вставке',
                r'Ошибка при обновлении',
                r'Foreign key constraint',
                r'Cannot add or update',
                r'Database error',
            ]
            
            for line_num, line in enumerate(lines, 1):
                for pattern in error_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Извлекаем timestamp, если есть
                        timestamp_match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        timestamp = timestamp_match.group(1) if timestamp_match else ''
                        
                        errors.append({
                            'error_message': line.strip(),
                            'log_file': str(log_file),
                            'line_number': line_num,
                            'timestamp': timestamp
                        })
                        break  # Не добавляем одну строку несколько раз
            
            return errors
        except Exception as e:
            self.logger.error(f"Ошибка при парсинге файла лога {log_file}: {e}", category=LogCategory.DBWRITE)
            return []
    
    def get_resume_info(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Определяет информацию для возобновления инициализации
        
        Returns:
            Tuple[resume_servers_url, resume_players_url, error_source]
            - resume_servers_url: URL для возобновления загрузки серверов или None
            - resume_players_url: URL для возобновления загрузки игроков или None
            - error_source: 'db', 'file' или None
        """
        # Сначала проверяем БД
        db_error = self.check_db_errors()
        if db_error:
            error_type = db_error.get('error_type')
            error_url = db_error.get('error_url', '')
            
            if error_type == 'servers_loading':
                return error_url, None, 'db'
            elif error_type == 'players_loading':
                return None, error_url, 'db'
        
        # Если в БД нет ошибки, проверяем файлы логов
        file_error = self.check_file_logs()
        if file_error:
            error_type = file_error.get('error_type')
            error_url = file_error.get('error_url', '')
            
            if error_type == 'servers_loading':
                return error_url, None, 'file'
            elif error_type == 'players_loading':
                return None, error_url, 'file'
        
        return None, None, None
    
    def check_all_errors(self) -> Dict:
        """
        Выполняет полную проверку всех ошибок
        
        Returns:
            Dict с полной информацией об ошибках:
            {
                'initialization_error': Dict или None,
                'db_write_errors': List[Dict],
                'resume_info': {
                    'servers_url': str или None,
                    'players_url': str или None,
                    'source': str или None
                }
            }
        """
        self.logger.info("Начало проверки ошибок инициализации", category=LogCategory.INITIALIZATION)
        
        # Проверяем ошибки инициализации
        db_error = self.check_db_errors()
        file_error = self.check_file_logs()
        
        # Приоритет у ошибки из БД
        init_error = db_error or file_error
        
        # Проверяем ошибки записи в БД
        db_write_errors = self.check_db_write_errors()
        
        # Получаем информацию для возобновления
        resume_servers_url, resume_players_url, error_source = self.get_resume_info()
        
        result = {
            'initialization_error': init_error,
            'db_write_errors': db_write_errors,
            'resume_info': {
                'servers_url': resume_servers_url,
                'players_url': resume_players_url,
                'source': error_source
            }
        }
        
        self.logger.info("Проверка ошибок завершена", {
            'has_init_error': init_error is not None,
            'db_write_errors_count': len(db_write_errors),
            'resume_source': error_source
        }, category=LogCategory.INITIALIZATION)
        
        return result

