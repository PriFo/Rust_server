# Загружаем переменные окружения ПЕРЕД всеми импортами
from src.config import load_env

load_env()

from src.gui_app import BotGUIApp

if __name__ == '__main__':
    app = BotGUIApp()
    app.mainloop()
