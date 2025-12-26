"""
Модуль для логирования с поддержкой различных уровней и форматирования
"""
import sys
from datetime import datetime
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Logger:
    """Класс для логирования с поддержкой различных уровней"""
    
    def __init__(self, name: str = "App"):
        self.name = name
        self._enabled_levels = {
            LogLevel.DEBUG: True,
            LogLevel.INFO: True,
            LogLevel.WARNING: True,
            LogLevel.ERROR: True,
            LogLevel.CRITICAL: True
        }
    
    def _format_message(self, level: LogLevel, message: str, metadata: Optional[dict] = None) -> str:
        """Форматирует сообщение лога"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{level.value}] [{self.name}] {message}"
        
        if metadata:
            metadata_str = ", ".join([f"{k}={v}" for k, v in metadata.items()])
            log_line += f" | {metadata_str}"
        
        return log_line
    
    def _log(self, level: LogLevel, message: str, metadata: Optional[dict] = None):
        """Внутренний метод логирования"""
        if self._enabled_levels.get(level, False):
            formatted = self._format_message(level, message, metadata)
            print(formatted, file=sys.stdout if level != LogLevel.ERROR else sys.stderr)
            sys.stdout.flush()
            if level == LogLevel.ERROR:
                sys.stderr.flush()
    
    def debug(self, message: str, metadata: Optional[dict] = None):
        """Логирование уровня DEBUG"""
        self._log(LogLevel.DEBUG, message, metadata)
    
    def info(self, message: str, metadata: Optional[dict] = None):
        """Логирование уровня INFO"""
        self._log(LogLevel.INFO, message, metadata)
    
    def warning(self, message: str, metadata: Optional[dict] = None):
        """Логирование уровня WARNING"""
        self._log(LogLevel.WARNING, message, metadata)
    
    def error(self, message: str, metadata: Optional[dict] = None):
        """Логирование уровня ERROR"""
        self._log(LogLevel.ERROR, message, metadata)
    
    def critical(self, message: str, metadata: Optional[dict] = None):
        """Логирование уровня CRITICAL"""
        self._log(LogLevel.CRITICAL, message, metadata)
    
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

