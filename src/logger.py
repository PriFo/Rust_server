"""
Модуль для логирования с поддержкой различных уровней и форматирования
Обновлен для лучшей интеграции с новой схемой БД v5.1
"""
import sys
import os
import json
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from enum import Enum
from pathlib import Path
import traceback
import inspect


class LogLevel(Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Категории логирования для маркировки"""
    INITIALIZATION = "Initialization"
    DBWRITE = "DBWrite"
    DBREAD = "DBRead"
    DBERROR = "DBError"
    PROFILE = "Profile"
    SERVER = "Server"
    PLAYER = "Player"
    FILTER = "Filter"
    CACHE = "Cache"
    QUEUE = "Queue"
    NOTIFICATION = "Notification"
    API = "API"
    GENERAL = "General"
    SYSTEM = "System"


class LogFormat(Enum):
    """Форматы вывода логов"""
    CONSOLE = "console"
    JSON = "json"
    SIMPLE = "simple"


class Logger:
    """Класс для логирования с поддержкой различных уровней и файлового логирования"""
    
    # Конфигурация по умолчанию
    DEFAULT_CONFIG = {
        'enable_file_logging': True,
        'enable_console_logging': True,
        'log_level': LogLevel.INFO,
        'log_format': LogFormat.CONSOLE,
        'max_file_size_mb': 10,
        'backup_count': 5,
        'json_compact': False,
        'include_timestamp': True,
        'include_module': True,
        'include_function': True,
        'include_line': True
    }
    
    def __init__(self, name: str = "App", config: Optional[Dict] = None, logs_dir: Optional[str] = None):
        """
        Инициализация логгера
        
        Args:
            name: Имя логгера (обычно имя модуля или класса)
            config: Конфигурация логгера
            logs_dir: Директория для логов
        """
        self.name = name
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        
        # Устанавливаем уровень логирования
        self._set_log_level(self.config['log_level'])
        
        # Настройка директории логов
        self.logs_dir = Path(logs_dir) if logs_dir else Path.cwd() / "logs"
        
        # Кэш открытых файлов и ротация
        self._file_handles = {}
        self._current_file_sizes = {}
        
        # Создаем директорию для логов
        if self.config['enable_file_logging']:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    def _set_log_level(self, level: LogLevel):
        """Устанавливает активные уровни логирования"""
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4
        }
        
        current_level = level_order[level]
        self._enabled_levels = {
            level: (level_order[level] >= current_level)
            for level in LogLevel
        }
    
    def _get_caller_info(self) -> Dict[str, str]:
        """Получает информацию о вызывающем коде"""
        frame = inspect.currentframe()
        # Поднимаемся на 3 фрейма: _format_message -> _log -> вызывающий метод
        for _ in range(3):
            if frame:
                frame = frame.f_back
        
        if frame:
            module = inspect.getmodule(frame)
            return {
                'module': module.__name__ if module else 'unknown',
                'function': frame.f_code.co_name,
                'line': str(frame.f_lineno)
            }
        return {}
    
    def _format_message(self, level: LogLevel, message: str, 
                       metadata: Optional[dict] = None,
                       category: LogCategory = LogCategory.GENERAL,
                       exception: Optional[Exception] = None) -> str:
        """Форматирует сообщение лога в зависимости от выбранного формата"""
        timestamp = datetime.now(timezone.utc).isoformat()
        caller_info = self._get_caller_info() if self.config['include_module'] else {}
        
        # Базовые поля
        log_data = {
            'timestamp': timestamp,
            'level': level.value,
            'logger': self.name,
            'message': str(message),
            'category': category.value
        }
        
        # Добавляем информацию о вызывающем коде
        if caller_info:
            log_data.update(caller_info)
        
        # Добавляем метаданные
        if metadata:
            log_data['metadata'] = metadata
        
        # Добавляем информацию об исключении
        if exception:
            log_data['exception'] = {
                'type': exception.__class__.__name__,
                'message': str(exception),
                'traceback': traceback.format_exc() if self.config['log_level'] == LogLevel.DEBUG else None
            }
        
        # Форматируем в зависимости от выбранного формата
        if self.config['log_format'] == LogFormat.JSON:
            return self._format_json(log_data)
        elif self.config['log_format'] == LogFormat.SIMPLE:
            return self._format_simple(log_data, level)
        else:  # CONSOLE
            return self._format_console(log_data, level)
    
    def _format_json(self, log_data: Dict[str, Any]) -> str:
        """Форматирует лог в JSON"""
        if self.config['json_compact']:
            return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
        return json.dumps(log_data, ensure_ascii=False, indent=2)
    
    def _format_simple(self, log_data: Dict[str, Any], level: LogLevel) -> str:
        """Простое форматирование"""
        timestamp = log_data['timestamp'][:19].replace('T', ' ')
        level_color = self._get_level_color(level)
        reset = '\033[0m' if sys.stdout.isatty() else ''
        
        # Собираем дополнительные поля
        extra = []
        if 'module' in log_data and self.config['include_module']:
            extra.append(f"module={log_data['module']}")
        if 'function' in log_data and self.config['include_function']:
            extra.append(f"func={log_data['function']}")
        if 'line' in log_data and self.config['include_line']:
            extra.append(f"line={log_data['line']}")
        
        extra_str = f" [{', '.join(extra)}]" if extra else ""
        
        return f"{timestamp} [{level_color}{level.value}{reset}] {log_data['message']}{extra_str}"
    
    def _format_console(self, log_data: Dict[str, Any], level: LogLevel) -> str:
        """Форматирование для консоли с цветами"""
        timestamp = log_data['timestamp'][:19].replace('T', ' ')
        level_color = self._get_level_color(level)
        category_color = self._get_category_color(LogCategory(log_data['category']))
        reset = '\033[0m' if sys.stdout.isatty() else ''
        
        # Базовая строка
        parts = [
            f"{timestamp}",
            f"[{level_color}{level.value}{reset}]",
            f"[{category_color}{log_data['category']}{reset}]",
            f"[{self.name}]",
            log_data['message']
        ]
        
        # Добавляем информацию о вызывающем коде
        if self.config['include_module'] and 'module' in log_data:
            parts.append(f"[{log_data['module']}")
            if self.config['include_function'] and 'function' in log_data:
                parts[-1] += f".{log_data['function']}"
                if self.config['include_line'] and 'line' in log_data:
                    parts[-1] += f":{log_data['line']}"
            parts[-1] += "]"
        
        # Добавляем метаданные
        if 'metadata' in log_data and log_data['metadata']:
            metadata_str = ", ".join([f"{k}={v}" for k, v in log_data['metadata'].items()])
            parts.append(f"| {metadata_str}")
        
        return " ".join(parts)
    
    def _get_level_color(self, level: LogLevel) -> str:
        """Возвращает цвет для уровня логирования"""
        if not sys.stdout.isatty():
            return ""
        
        colors = {
            LogLevel.DEBUG: '\033[36m',    # Cyan
            LogLevel.INFO: '\033[32m',     # Green
            LogLevel.WARNING: '\033[33m',  # Yellow
            LogLevel.ERROR: '\033[31m',    # Red
            LogLevel.CRITICAL: '\033[41m\033[37m'  # Red background, white text
        }
        return colors.get(level, '')
    
    def _get_category_color(self, category: LogCategory) -> str:
        """Возвращает цвет для категории"""
        if not sys.stdout.isatty():
            return ""
        
        colors = {
            LogCategory.DBWRITE: '\033[35m',  # Magenta
            LogCategory.DBREAD: '\033[34m',   # Blue
            LogCategory.DBERROR: '\033[41m\033[37m',  # Red background
            LogCategory.PROFILE: '\033[36m',  # Cyan
            LogCategory.SERVER: '\033[32m',   # Green
            LogCategory.PLAYER: '\033[33m',   # Yellow
            LogCategory.INITIALIZATION: '\033[1m',  # Bold
        }
        return colors.get(category, '\033[90m')  # Gray by default
    
    def _get_log_file_path(self, category: LogCategory = LogCategory.GENERAL) -> Path:
        """Возвращает путь к файлу лога для категории"""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{category.value.lower()}_{today}.log"
        return self.logs_dir / filename
    
    def _check_file_rotation(self, file_path: Path, category: LogCategory):
        """Проверяет необходимость ротации файла"""
        if not file_path.exists():
            return
        
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb >= self.config['max_file_size_mb']:
            self._rotate_log_file(file_path, category)
    
    def _rotate_log_file(self, file_path: Path, category: LogCategory):
        """Ротирует файл лога"""
        try:
            # Закрываем текущий файл
            file_key = str(file_path)
            if file_key in self._file_handles:
                self._file_handles[file_key].close()
                del self._file_handles[file_key]
            
            # Создаем backup файлы
            for i in range(self.config['backup_count'] - 1, 0, -1):
                old_file = file_path.with_suffix(f".{i}.log")
                new_file = file_path.with_suffix(f".{i + 1}.log")
                if old_file.exists():
                    if new_file.exists():
                        new_file.unlink()
                    old_file.rename(new_file)
            
            # Переименовываем текущий файл в .1.log
            backup_file = file_path.with_suffix(".1.log")
            if file_path.exists():
                file_path.rename(backup_file)
                
        except Exception as e:
            self._write_to_stderr(f"Ошибка при ротации файла {file_path}: {e}")
    
    def _write_to_file(self, log_line: str, category: LogCategory = LogCategory.GENERAL):
        """Записывает лог в файл"""
        if not self.config['enable_file_logging']:
            return
        
        try:
            file_path = self._get_log_file_path(category)
            file_key = str(file_path)
            
            # Проверяем ротацию
            self._check_file_rotation(file_path, category)
            
            # Открываем файл в режиме append
            if file_key not in self._file_handles:
                self._file_handles[file_key] = open(file_path, 'a', encoding='utf-8')
            
            # Для JSON формата уже есть перенос строки
            if self.config['log_format'] != LogFormat.JSON:
                log_line += '\n'
            
            self._file_handles[file_key].write(log_line)
            self._file_handles[file_key].flush()
            
        except Exception as e:
            self._write_to_stderr(f"Не удалось записать в файл лога: {e}")
    
    def _write_to_stderr(self, message: str):
        """Записывает сообщение в stderr"""
        print(f"[LOGGER ERROR] {message}", file=sys.stderr)
        sys.stderr.flush()
    
    def _should_log(self, level: LogLevel) -> bool:
        """Проверяет, нужно ли логировать сообщение данного уровня"""
        return self._enabled_levels.get(level, False)
    
    def _log(self, level: LogLevel, message: str, 
             metadata: Optional[dict] = None, 
             category: LogCategory = LogCategory.GENERAL,
             exception: Optional[Exception] = None):
        """Внутренний метод логирования"""
        if not self._should_log(level):
            return
        
        formatted = self._format_message(level, message, metadata, category, exception)
        
        # Вывод в консоль
        if self.config['enable_console_logging']:
            output_stream = sys.stdout if level in [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING] else sys.stderr
            print(formatted, file=output_stream)
            output_stream.flush()
        
        # Запись в файл
        if self.config['enable_file_logging']:
            # Для ошибок и критических сообщений всегда пишем в файл
            if level in [LogLevel.ERROR, LogLevel.CRITICAL] or category != LogCategory.GENERAL:
                self._write_to_file(formatted, category)
            
            # Для режима DEBUG пишем все в файл
            if self.config['log_level'] == LogLevel.DEBUG:
                self._write_to_file(formatted, category)
    
    def close(self):
        """Закрывает все открытые файлы логов"""
        for handle in self._file_handles.values():
            try:
                handle.close()
            except:
                pass
        self._file_handles.clear()
    
    def set_level(self, level: LogLevel):
        """Устанавливает уровень логирования"""
        self.config['log_level'] = level
        self._set_log_level(level)
        self.info(f"Уровень логирования изменен на {level.value}")
    
    def set_format(self, log_format: LogFormat):
        """Устанавливает формат логирования"""
        self.config['log_format'] = log_format
        self.info(f"Формат логирования изменен на {log_format.value}")
    
    # Основные методы логирования
    
    def debug(self, message: str, metadata: Optional[dict] = None, 
              category: LogCategory = LogCategory.GENERAL):
        """Логирование уровня DEBUG"""
        self._log(LogLevel.DEBUG, message, metadata, category)
    
    def info(self, message: str, metadata: Optional[dict] = None, 
             category: LogCategory = LogCategory.GENERAL):
        """Логирование уровня INFO"""
        self._log(LogLevel.INFO, message, metadata, category)
    
    def warning(self, message: str, metadata: Optional[dict] = None, 
                category: LogCategory = LogCategory.GENERAL):
        """Логирование уровня WARNING"""
        self._log(LogLevel.WARNING, message, metadata, category)
    
    def error(self, message: str, metadata: Optional[dict] = None, 
              category: LogCategory = LogCategory.GENERAL,
              exception: Optional[Exception] = None):
        """Логирование уровня ERROR"""
        self._log(LogLevel.ERROR, message, metadata, category, exception)
    
    def critical(self, message: str, metadata: Optional[dict] = None, 
                 category: LogCategory = LogCategory.GENERAL,
                 exception: Optional[Exception] = None):
        """Логирование уровня CRITICAL"""
        self._log(LogLevel.CRITICAL, message, metadata, category, exception)
    
    # Специализированные методы для новой схемы БД
    
    def db_write(self, message: str, metadata: Optional[dict] = None):
        """Логирование операций записи в БД"""
        self.info(message, metadata, LogCategory.DBWRITE)
    
    def db_read(self, message: str, metadata: Optional[dict] = None):
        """Логирование операций чтения из БД"""
        self.debug(message, metadata, LogCategory.DBREAD)
    
    def db_error(self, message: str, metadata: Optional[dict] = None, 
                 exception: Optional[Exception] = None):
        """Логирование ошибок БД"""
        self.error(message, metadata, LogCategory.DBERROR, exception)
    
    def profile(self, message: str, metadata: Optional[dict] = None, level: LogLevel = LogLevel.INFO):
        """Логирование операций с профилями"""
        self._log(level, message, metadata, LogCategory.PROFILE)
    
    def server(self, message: str, metadata: Optional[dict] = None, level: LogLevel = LogLevel.INFO):
        """Логирование операций с серверами"""
        self._log(level, message, metadata, LogCategory.SERVER)
    
    def player(self, message: str, metadata: Optional[dict] = None, level: LogLevel = LogLevel.INFO):
        """Логирование операций с игроками"""
        self._log(level, message, metadata, LogCategory.PLAYER)
    
    def filter(self, message: str, metadata: Optional[dict] = None, level: LogLevel = LogLevel.INFO):
        """Логирование операций с фильтрами"""
        self._log(level, message, metadata, LogCategory.FILTER)
    
    def queue(self, message: str, metadata: Optional[dict] = None, level: LogLevel = LogLevel.INFO):
        """Логирование операций с очередями"""
        self._log(level, message, metadata, LogCategory.QUEUE)
    
    # Вспомогательные методы
    
    def section(self, title: str, char: str = "=", width: int = 80):
        """Выводит разделитель секции"""
        self.info(char * width)
        self.info(f"{title:^{width}}")
        self.info(char * width)
    
    def subsection(self, title: str, char: str = "-", width: int = 80):
        """Выводит разделитель подсекции"""
        self.info(f"{char * width}")
        self.info(f"{title}")
        self.info(f"{char * width}")
    
    def performance(self, operation: str, start_time: datetime, 
                   metadata: Optional[dict] = None):
        """Логирование производительности операции"""
        duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        perf_metadata = {'operation': operation, 'duration_ms': round(duration, 2)}
        if metadata:
            perf_metadata.update(metadata)
        
        if duration > 1000:  # Больше 1 секунды
            self.warning(f"Медленная операция: {operation}", perf_metadata)
        else:
            self.debug(f"Операция завершена: {operation}", perf_metadata)
    
    def sql_query(self, query: str, params: Optional[list] = None, 
                  duration: Optional[float] = None):
        """Логирование SQL запросов (для отладки)"""
        if self.config['log_level'] == LogLevel.DEBUG:
            metadata = {'query': query[:200] + '...' if len(query) > 200 else query}
            if params:
                metadata['params'] = str(params)[:100]
            if duration is not None:
                metadata['duration_ms'] = round(duration, 2)
            
            self.debug("SQL запрос выполнен", metadata, LogCategory.DBREAD)


# Глобальные настройки логгера по умолчанию
def configure_global_logging(config: Optional[Dict] = None):
    """
    Конфигурирует глобальное логирование
    
    Args:
        config: Конфигурация логгера
    """
    global _global_config
    _global_config = config or {}


def get_logger(name: str = "App", config: Optional[Dict] = None) -> Logger:
    """
    Фабрика для создания логгеров с возможностью глобальной конфигурации
    
    Args:
        name: Имя логгера
        config: Локальная конфигурация (имеет приоритет над глобальной)
    
    Returns:
        Настроенный экземпляр Logger
    """
    global _global_config
    try:
        _global_config
    except NameError:
        _global_config = {}
    
    # Объединяем глобальную и локальную конфигурацию
    final_config = {**Logger.DEFAULT_CONFIG, **_global_config, **(config or {})}
    
    return Logger(name, final_config)


# Глобальная конфигурация по умолчанию
_global_config = {}