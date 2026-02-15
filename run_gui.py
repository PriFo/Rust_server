#!/usr/bin/env python
"""
Точка входа для запуска GUI приложения
"""
import sys
import os
from pathlib import Path

# Проверяем наличие виртуального окружения
venv_path = Path(__file__).parent / '.venv'
if venv_path.exists():
    # Проверяем, активировано ли виртуальное окружение
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("[WARNING] Виртуальное окружение найдено, но не активировано!")
        print("   Рекомендуется активировать его перед запуском:")
        print("   Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1")
        print("   Windows CMD: .venv\\Scripts\\activate.bat")
        print("   Linux/macOS: source .venv/bin/activate")
        print()
        print("   Продолжаем запуск...")
        print()

# Добавляем корень проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Загружаем переменные окружения ПЕРЕД всеми импортами
from src.config import load_env

load_env()
# GUI может стартовать без бота — validate_required() не вызываем здесь

# Импортируем и запускаем приложение
try:
    from src.gui_app import BotGUIApp
    
    if __name__ == '__main__':
        app = BotGUIApp()
        app.mainloop()
except ModuleNotFoundError as e:
    print("[ERROR] Не найден необходимый модуль!")
    print(f"   {e}")
    print()
    print("   Решение:")
    print("   1. Убедитесь, что виртуальное окружение активировано")
    print("   2. Установите зависимости: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Ошибка при запуске приложения: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

