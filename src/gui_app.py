"""
GUI приложение для управления ботом на CustomTkinter
"""
import customtkinter as ctk
import threading
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any

from src.main_no_gui import async_main, save_data_on_exit
from scripts.initialize_database import initialize_data
from src.repository import Repository
from src.logger import Logger, LogCategory
from src.SQLSyntaxHelper import ETablesBM_DB as tables

from os import getenv
from dotenv import load_dotenv

# Импортируем функции для работы с бэкапами
from scripts.backup_database import (
    check_env_variables,
    create_backup,
    list_backups,
    restore_backup,
    recreate_backup,
    get_backups_dir
)

# Настройка темы CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ADMIN_ID = getenv('ADMIN_ID', '517965582')


class BotGUIApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("BattleMetrics Bot Control Panel")
        self.geometry("1200x800")
        
        # Состояние бота
        self.bot_running = False
        self.bot_thread: Optional[threading.Thread] = None
        self.asyncio_loop: Optional[asyncio.AbstractEventLoop] = None
        self.stop_event = threading.Event()
        self.asyncio_stop_event: Optional[asyncio.Event] = None
        
        # Состояние инициализации
        self.init_running = False
        self.init_thread: Optional[threading.Thread] = None
        self.init_loop: Optional[asyncio.AbstractEventLoop] = None
        self.init_stop_event = threading.Event()
        
        # Repository для статистики (инициализируем лениво, чтобы не блокировать GUI)
        self.repo: Optional[Repository] = None
        self._repo_init_error: Optional[str] = None
        
        # Инициализируем Repository в отдельном потоке, чтобы не блокировать GUI
        def init_repo():
            try:
                self.repo = Repository()
                # Не вызываем _ensure_db_connection сразу - подключение произойдет при первом использовании
            except Exception as e:
                self._repo_init_error = str(e)
                print(f"[WARNING] Не удалось инициализировать Repository: {e}")
                print("   Приложение будет работать в ограниченном режиме")
        
        # Запускаем инициализацию в отдельном потоке
        repo_thread = threading.Thread(target=init_repo, daemon=True)
        repo_thread.start()
        
        # Logger (инициализируем с обработкой ошибок)
        self.logger: Optional[Logger] = None
        try:
            self.logger = Logger("GUI")
        except Exception as e:
            print(f"[WARNING] Не удалось инициализировать Logger: {e}")
        
        # Последняя позиция в логах для чтения
        self.last_log_position = {}
        self.logs_dir = Path.cwd() / "logs"
        # Кэш для модификаций файлов
        self.log_file_mtimes = {}
        
        # Создаем интерфейс (с обработкой ошибок)
        try:
            self.create_widgets()
        except Exception as e:
            print(f"[ERROR] Ошибка при создании интерфейса: {e}")
            import traceback
            traceback.print_exc()
            # Создаем минимальный интерфейс с сообщением об ошибке
            self._create_error_interface(str(e))
            return
        
        # Запускаем обновление логов (с обработкой ошибок)
        try:
            self.update_logs()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка при запуске обновления логов: {e}")
            else:
                print(f"[ERROR] Ошибка при запуске обновления логов: {e}")
        
        # Откладываем обновление статистики на 2 секунды после запуска, чтобы не блокировать GUI
        # Статистика будет собираться в фоне
        self.after(2000, self._update_stats_async)
        
        # Обработчик закрытия окна
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Показываем окно
        self.deiconify()
        self.lift()
        self.focus_force()
    
    def _safe_log(self, level: str, message: str):
        """Безопасное логирование с проверкой на None"""
        if self.logger:
            if level == 'info':
                self.logger.info(message)
            elif level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def _create_error_interface(self, error_msg: str):
        """Создает минимальный интерфейс с сообщением об ошибке"""
        error_label = ctk.CTkLabel(
            self,
            text=f"Ошибка при инициализации приложения:\n{error_msg}\n\nПроверьте логи и настройки подключения к БД.",
            font=ctk.CTkFont(size=14),
            text_color="red",
            justify="left"
        )
        error_label.pack(pady=50, padx=50)
    
    def create_widgets(self):
        """Создает все виджеты интерфейса"""
        # Панель управления вверху
        self.create_control_panel()
        
        # Вкладки
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Вкладка "Логи"
        self.create_logs_tab()
        
        # Вкладка "Статистика"
        self.create_stats_tab()
        
        # Вкладка "Конфигурация"
        self.create_config_tab()
        
        # Вкладка "Инициализация"
        self.create_init_tab()
        
        # Вкладка "Бэкап БД"
        self.create_backup_tab()
        
        # Вкладка "Отчеты"
        self.create_reports_tab()
    
    def create_control_panel(self):
        """Создает панель управления"""
        control_frame = ctk.CTkFrame(self)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        # Кнопка запуска/остановки
        self.start_stop_btn = ctk.CTkButton(
            control_frame,
            text="Запустить бота",
            command=self.toggle_bot,
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.start_stop_btn.pack(side="left", padx=10, pady=10)
        
        # Индикатор статуса
        self.status_indicator = ctk.CTkLabel(
            control_frame,
            text="●",
            font=ctk.CTkFont(size=24),
            text_color="gray"
        )
        self.status_indicator.pack(side="left", padx=10, pady=10)
        
        # Текст статуса
        self.status_label = ctk.CTkLabel(
            control_frame,
            text="Статус: Остановлен",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(side="left", padx=10, pady=10)
    
    def create_logs_tab(self):
        """Создает вкладку логов"""
        logs_tab = self.tabview.add("Логи")
        
        # Панель управления логами
        logs_control = ctk.CTkFrame(logs_tab)
        logs_control.pack(fill="x", padx=10, pady=10)
        
        # Фильтр уровня
        ctk.CTkLabel(logs_control, text="Фильтр уровня:").pack(side="left", padx=5)
        self.log_level_filter = ctk.CTkComboBox(
            logs_control,
            values=["Все", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            width=150,
            command=self.on_log_filter_changed
        )
        self.log_level_filter.set("Все")
        self.log_level_filter.pack(side="left", padx=5)
        
        # Кнопка очистки
        clear_btn = ctk.CTkButton(
            logs_control,
            text="Очистить",
            command=self.clear_logs,
            width=100
        )
        clear_btn.pack(side="left", padx=5)
        
        # Текстовое поле для логов
        self.logs_text = ctk.CTkTextbox(
            logs_tab,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="none"
        )
        self.logs_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def create_stats_tab(self):
        """Создает вкладку статистики"""
        stats_tab = self.tabview.add("Статистика")
        
        # Кнопка обновления
        refresh_btn = ctk.CTkButton(
            stats_tab,
            text="Обновить",
            command=self.update_stats,
            width=100
        )
        refresh_btn.pack(pady=10)
        
        # Текстовое поле для статистики
        self.stats_text = ctk.CTkTextbox(
            stats_tab,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word"
        )
        self.stats_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def create_config_tab(self):
        """Создает вкладку конфигурации"""
        config_tab = self.tabview.add("Конфигурация")
        
        # Панель управления
        config_control = ctk.CTkFrame(config_tab)
        config_control.pack(fill="x", padx=10, pady=10)
        
        load_btn = ctk.CTkButton(
            config_control,
            text="Загрузить",
            command=self.load_config,
            width=100
        )
        load_btn.pack(side="left", padx=5)
        
        save_btn = ctk.CTkButton(
            config_control,
            text="Сохранить",
            command=self.save_config,
            width=100
        )
        save_btn.pack(side="left", padx=5)
        
        check_btn = ctk.CTkButton(
            config_control,
            text="Проверить",
            command=self.check_config,
            width=100
        )
        check_btn.pack(side="left", padx=5)
        
        # Текстовое поле для .env
        self.config_text = ctk.CTkTextbox(
            config_tab,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="none"
        )
        self.config_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Загружаем конфигурацию при создании
        self.load_config()
    
    def create_init_tab(self):
        """Создает вкладку инициализации"""
        init_tab = self.tabview.add("Инициализация")
        
        # Информация
        info_label = ctk.CTkLabel(
            init_tab,
            text="Инициализация данных загружает все серверы и игроков Rust из BattleMetrics API.\nЭто может занять очень много времени.",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        info_label.pack(pady=10)
        
        # Кнопки
        buttons_frame = ctk.CTkFrame(init_tab)
        buttons_frame.pack(pady=10)
        
        self.init_btn = ctk.CTkButton(
            buttons_frame,
            text="Запустить инициализацию",
            command=self.toggle_initialization,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.init_btn.pack(side="left", padx=10)
        
        clear_state_btn = ctk.CTkButton(
            buttons_frame,
            text="Очистить состояние инициализации",
            command=self.clear_init_state,
            width=250,
            height=40
        )
        clear_state_btn.pack(side="left", padx=10)
        
        clear_db_btn = ctk.CTkButton(
            buttons_frame,
            text="Очистить базу данных",
            command=self.confirm_clear_database,
            width=200,
            height=40,
            fg_color="red",
            hover_color="darkred"
        )
        clear_db_btn.pack(side="left", padx=10)
        
        # Текстовое поле для статуса
        self.init_status_text = ctk.CTkTextbox(
            init_tab,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=300
        )
        self.init_status_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def create_backup_tab(self):
        """Создает вкладку для работы с бэкапами БД"""
        backup_tab = self.tabview.add("Бэкап БД")
        
        # Информация
        info_label = ctk.CTkLabel(
            backup_tab,
            text="Управление бэкапами базы данных. Создавайте бэкапы перед важными операциями.",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        info_label.pack(pady=10)
        
        # Панель управления
        control_frame = ctk.CTkFrame(backup_tab)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        # Кнопка создания бэкапа
        create_backup_btn = ctk.CTkButton(
            control_frame,
            text="Создать бэкап",
            command=self.create_backup_gui,
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="green",
            hover_color="darkgreen"
        )
        create_backup_btn.pack(side="left", padx=10)
        
        # Кнопка обновления списка
        refresh_backups_btn = ctk.CTkButton(
            control_frame,
            text="Обновить список",
            command=self.refresh_backups_list,
            width=150,
            height=40
        )
        refresh_backups_btn.pack(side="left", padx=10)
        
        # Поле для имени бэкапа
        name_frame = ctk.CTkFrame(backup_tab)
        name_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            name_frame,
            text="Имя бэкапа (необязательно):",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=10)
        
        self.backup_name_entry = ctk.CTkEntry(
            name_frame,
            width=300,
            placeholder_text="Введите имя бэкапа..."
        )
        self.backup_name_entry.pack(side="left", padx=10)
        
        # Список бэкапов
        list_frame = ctk.CTkFrame(backup_tab)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            list_frame,
            text="Доступные бэкапы:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Скроллируемый фрейм для списка бэкапов
        self.backups_scroll_frame = ctk.CTkScrollableFrame(list_frame)
        self.backups_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Текстовое поле для статуса операций
        self.backup_status_text = ctk.CTkTextbox(
            backup_tab,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=150
        )
        self.backup_status_text.pack(fill="x", padx=10, pady=(0, 10))
        
        # Загружаем список бэкапов при создании
        self.refresh_backups_list()
    
    def create_reports_tab(self):
        """Создает вкладку для работы с отчетами (репортами)"""
        reports_tab = self.tabview.add("Отчеты")
        
        # Информация
        info_label = ctk.CTkLabel(
            reports_tab,
            text="Отчеты от пользователей бота. Вы можете отвечать на них напрямую из интерфейса.",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        info_label.pack(pady=10)
        
        # Панель управления
        control_frame = ctk.CTkFrame(reports_tab)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        # Кнопка обновления списка отчетов
        refresh_reports_btn = ctk.CTkButton(
            control_frame,
            text="Обновить отчеты",
            command=self.refresh_reports_list,
            width=150,
            height=40
        )
        refresh_reports_btn.pack(side="left", padx=10)
        
        # Кнопка пометки как прочитанного
        mark_read_btn = ctk.CTkButton(
            control_frame,
            text="Пометить как прочитанное",
            command=self.mark_report_as_read,
            width=200,
            height=40,
            fg_color="blue",
            hover_color="darkblue"
        )
        mark_read_btn.pack(side="left", padx=10)
        
        # Кнопка удаления отчета
        delete_report_btn = ctk.CTkButton(
            control_frame,
            text="Удалить отчет",
            command=self.delete_selected_report,
            width=150,
            height=40,
            fg_color="red",
            hover_color="darkred"
        )
        delete_report_btn.pack(side="left", padx=10)
        
        # Основной контейнер с двумя колонками
        main_container = ctk.CTkFrame(reports_tab)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Левая колонка - список отчетов
        left_column = ctk.CTkFrame(main_container, width=400)
        left_column.pack(side="left", fill="both", expand=False, padx=(0, 5), pady=5)
        left_column.pack_propagate(False)  # Фиксируем ширину
        
        ctk.CTkLabel(
            left_column,
            text="Список отчетов:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Скроллируемый фрейм для списка отчетов
        self.reports_scroll_frame = ctk.CTkScrollableFrame(left_column)
        self.reports_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Правая колонка - просмотр и ответ на отчет
        right_column = ctk.CTkFrame(main_container)
        right_column.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=5)
        
        ctk.CTkLabel(
            right_column,
            text="Просмотр отчета:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # Текстовое поле для просмотра отчета
        self.report_view_text = ctk.CTkTextbox(
            right_column,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=200
        )
        self.report_view_text.pack(fill="x", padx=10, pady=(0, 10))
        
        # Поле для ввода ответа
        ctk.CTkLabel(
            right_column,
            text="Ответ пользователю:",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(10, 5))
        
        self.report_answer_text = ctk.CTkTextbox(
            right_column,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=100
        )
        self.report_answer_text.pack(fill="x", padx=10, pady=(0, 10))
        
        # Кнопка отправки ответа
        send_answer_btn = ctk.CTkButton(
            right_column,
            text="Отправить ответ",
            command=self.send_answer_to_report,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="green",
            hover_color="darkgreen"
        )
        send_answer_btn.pack(pady=10)
        
        # Текущий выбранный отчет
        self.selected_report_id = None
        self.selected_report_user_id = None
        
        # Загружаем отчеты при создании
        # В конце метода вместо self.refresh_reports_list() пишем:
        self.after(100, self._async_refresh_reports)   # запускаем обновление в фоне
    
    def _async_refresh_reports(self):
        """Запускает обновление списка отчетов в фоновом потоке"""
        if not self.repo:
            self.after(2000, self._async_refresh_reports)
            return
        thread = threading.Thread(target=self._refresh_reports_worker, daemon=True)
        thread.start()

    def _refresh_reports_worker(self):
        """Работа с БД выполняется в отдельном потоке"""
        try:
            reports_data = self._fetch_reports_data()
            self.after(0, lambda: self._update_reports_ui(reports_data))
        except Exception as e:
            self._safe_log('error', f'Ошибка загрузки отчетов: {e}')
            self.after(0, lambda: self._show_reports_error(str(e)))

    def _fetch_reports_data(self):
        """Извлекает список отчетов из БД (без GUI)"""
        if not self.repo:
            return None
        return self.repo.fetch_suggestions_list()

    def _update_reports_ui(self, reports):
        """Обновляет список отчетов в интерфейсе (вызывается из главного потока)"""
        # Очищаем скроллируемый фрейм
        for widget in self.reports_scroll_frame.winfo_children():
            widget.destroy()
        
        if reports is None:
            # Репозиторий ещё не готов
            label = ctk.CTkLabel(
                self.reports_scroll_frame,
                text="Инициализация подключения к БД...",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            label.pack(pady=20)
            self.after(2000, self._async_refresh_reports)
            return
        
        if not reports:
            label = ctk.CTkLabel(
                self.reports_scroll_frame,
                text="Нет отчетов от пользователей",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            label.pack(pady=20)
            return
        
        # Отображаем каждый отчет (код скопирован из оригинального refresh_reports_list)
        for report in reports:
            report_frame = ctk.CTkFrame(self.reports_scroll_frame)
            report_frame.pack(fill="x", padx=5, pady=5)
            
            report_id = report['id_suggestions']
            user_id = report['fk_id_profile']
            user_info = f"{report['profile_nickname'] or report['profile_name'] or user_id}"
            created_at = report['created_at'].strftime('%Y-%m-%d %H:%M') if report['created_at'] else "N/A"
            preview_text = report['msg_txt'][:50] + "..." if len(report['msg_txt']) > 50 else report['msg_txt']
            
            info_text = f"#{report_id} | {user_info} | {created_at}\n{preview_text}"
            
            def create_report_callback(rid, uid):
                return lambda: self.select_report(rid, uid)
            
            report_btn = ctk.CTkButton(
                report_frame,
                text=info_text,
                command=create_report_callback(report_id, user_id),
                anchor="w",
                justify="left",
                height=60,
                fg_color=("gray85", "gray25"),
                hover_color=("gray75", "gray35")
            )
            report_btn.pack(fill="x", padx=5, pady=2)

    def _show_reports_error(self, error_msg):
        """Показывает сообщение об ошибке в списке отчетов"""
        for widget in self.reports_scroll_frame.winfo_children():
            widget.destroy()
        label = ctk.CTkLabel(
            self.reports_scroll_frame,
            text=f"Ошибка загрузки отчетов:\n{error_msg}",
            font=ctk.CTkFont(size=12),
            text_color="red",
            justify="left"
        )
        label.pack(pady=20)

    def refresh_reports_list(self):
        """Обновляет список отчетов (асинхронно)"""
        self._async_refresh_reports()
    
    def select_report(self, report_id: int, user_id):
        """Выбирает отчет для просмотра и ответа"""
        try:
            self.selected_report_id = report_id
            self.selected_report_user_id = user_id
            
            report = self.repo.get_suggestion_by_id(report_id)
            if not report:
                self.report_view_text.delete("1.0", "end")
                self.report_view_text.insert("1.0", "Отчет не найден")
                return
            
            # Форматируем информацию об отчете
            report_text = f"Отчет #{report_id}\n"
            report_text += f"От пользователя: {report['user_nickname'] or report['user_name'] or user_id} (ID: {user_id})\n"
            report_text += f"Дата: {report['created_at'].strftime('%Y-%m-%d %H:%M:%S') if report['created_at'] else 'N/A'}\n"
            report_text += f"\nСообщение:\n{report['msg_txt']}\n"
            
            # Показываем информацию об отчете
            self.report_view_text.delete("1.0", "end")
            self.report_view_text.insert("1.0", report_text)
            
            # Очищаем поле ответа
            self.report_answer_text.delete("1.0", "end")
            
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при выборе отчета: {e}\n"
            self.logger.error(error_msg)
    
    def send_answer_to_report(self):
        """Отправляет ответ на выбранный отчет"""
        if not self.selected_report_id or not self.selected_report_user_id:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("400x150")
            ctk.CTkLabel(
                dialog,
                text="Выберите отчет для ответа",
                font=ctk.CTkFont(size=12)
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
            return
        
        answer_text = self.report_answer_text.get("1.0", "end-1c").strip()
        if not answer_text:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("400x150")
            ctk.CTkLabel(
                dialog,
                text="Введите текст ответа",
                font=ctk.CTkFont(size=12)
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
            return
        
        try:
            # Отправляем ответ через Telegram API
            import requests
            from os import getenv
            
            bot_token = getenv('T_API_KEY')
            if not bot_token:
                raise ValueError("Токен бота не найден")
            
            # Формируем сообщение
            message = f"📨 Ответ на ваш отчет:\n\n{answer_text}"
            
            # Отправляем сообщение пользователю
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            params = {
                'chat_id': self.selected_report_user_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=params)
            
            if response.status_code == 200:
                self.repo.mark_suggestion_answered(self.selected_report_id)
                # Показываем успешное сообщение
                dialog = ctk.CTkToplevel(self)
                dialog.title("Успех")
                dialog.geometry("400x150")
                ctk.CTkLabel(
                    dialog,
                    text="Ответ успешно отправлен пользователю",
                    font=ctk.CTkFont(size=12)
                ).pack(pady=20)
                ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
                
                # Обновляем список отчетов
                self.refresh_reports_list()
                # Очищаем поля
                self.report_view_text.delete("1.0", "end")
                self.report_answer_text.delete("1.0", "end")
                self.selected_report_id = None
                self.selected_report_user_id = None
                
            else:
                error_data = response.json()
                error_msg = error_data.get('description', 'Неизвестная ошибка')
                raise Exception(f"Ошибка Telegram API: {error_msg}")
                
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при отправке ответа: {e}\n"
            self.logger.error(error_msg)
            
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("500x200")
            ctk.CTkLabel(
                dialog,
                text=f"Ошибка при отправке ответа:\n{e}",
                font=ctk.CTkFont(size=12)
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
    
    def mark_report_as_read(self):
        """Помечает выбранный отчет как прочитанный"""
        if not self.selected_report_id:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("400x150")
            ctk.CTkLabel(
                dialog,
                text="Выберите отчет для отметки",
                font=ctk.CTkFont(size=12)
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
            return
        
        try:
            self.repo.mark_suggestion_answered(self.selected_report_id)
            self.refresh_reports_list()
            dialog = ctk.CTkToplevel(self)
            dialog.title("Успех")
            dialog.geometry("400x150")
            ctk.CTkLabel(
                dialog,
                text="Отчет помечен как прочитанный",
                font=ctk.CTkFont(size=12)
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
            
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при отметке отчета: {e}\n"
            self.logger.error(error_msg)
    
    def delete_selected_report(self):
        """Удаляет выбранный отчет"""
        if not self.selected_report_id:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("400x150")
            ctk.CTkLabel(
                dialog,
                text="Выберите отчет для удаления",
                font=ctk.CTkFont(size=12)
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
            return
        
        # Диалог подтверждения
        dialog = ctk.CTkToplevel(self)
        dialog.title("Подтверждение удаления")
        dialog.geometry("500x200")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog,
            text="Вы уверены, что хотите удалить этот отчет?",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=20)
        
        ctk.CTkLabel(
            dialog,
            text="Это действие нельзя отменить.",
            font=ctk.CTkFont(size=12)
        ).pack(pady=10)
        
        buttons_frame = ctk.CTkFrame(dialog)
        buttons_frame.pack(pady=20)
        
        def confirm_delete():
            try:
                self.repo.delete_suggestion(self.selected_report_id)
                # Обновляем список отчетов
                self.refresh_reports_list()
                # Очищаем поля
                self.report_view_text.delete("1.0", "end")
                self.report_answer_text.delete("1.0", "end")
                self.selected_report_id = None
                self.selected_report_user_id = None
                
                dialog.destroy()
                
                success_dialog = ctk.CTkToplevel(self)
                success_dialog.title("Успех")
                success_dialog.geometry("400x150")
                ctk.CTkLabel(
                    success_dialog,
                    text="Отчет успешно удален",
                    font=ctk.CTkFont(size=12)
                ).pack(pady=20)
                ctk.CTkButton(success_dialog, text="OK", command=success_dialog.destroy).pack()
                
            except Exception as e:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при удалении отчета: {e}\n"
                self.logger.error(error_msg)
                dialog.destroy()
        
        ctk.CTkButton(
            buttons_frame,
            text="Да, удалить",
            command=confirm_delete,
            width=150,
            fg_color="red",
            hover_color="darkred"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            command=dialog.destroy,
            width=150
        ).pack(side="left", padx=10)
    
    def toggle_bot(self):
        """Переключает состояние бота"""
        if not self.bot_running:
            self.start_bot()
        else:
            self.stop_bot()
    
    def start_bot(self):
        """Запускает бота в отдельном потоке"""
        if self.bot_running:
            return
        
        self.bot_running = True
        self.stop_event.clear()
        self.start_stop_btn.configure(text="Остановить бота", fg_color="red")
        self.status_indicator.configure(text_color="green")
        self.status_label.configure(text="Статус: Запущен")
        
        # Запускаем в отдельном потоке
        self.bot_thread = threading.Thread(target=self.run_bot_async, daemon=True)
        self.bot_thread.start()
        
        self.logger.info("Бот запущен через GUI")
    
    def stop_bot(self):
        """Останавливает бота"""
        if not self.bot_running:
            return
        
        self.bot_running = False
        self.stop_event.set()
        self.start_stop_btn.configure(text="▶ Запустить бота", fg_color=("green", "darkgreen"))
        self.status_indicator.configure(text_color="red")
        self.status_label.configure(text="Статус: ⏸ Остановка...")
        
        # Устанавливаем asyncio.Event для остановки асинхронных задач
        if self.asyncio_loop and self.asyncio_stop_event:
            try:
                # Устанавливаем событие в event loop
                self.asyncio_loop.call_soon_threadsafe(self.asyncio_stop_event.set)
            except Exception as e:
                self.logger.error(f"Ошибка при установке stop_event: {e}")
        
        # Отменяем все задачи в event loop
        if self.asyncio_loop:
            try:
                tasks = [task for task in asyncio.all_tasks(self.asyncio_loop) if not task.done()]
                for task in tasks:
                    self.asyncio_loop.call_soon_threadsafe(task.cancel)
            except Exception as e:
                self.logger.error(f"Ошибка при отмене задач: {e}")
        
        # Сохраняем данные
        try:
            save_data_on_exit(self.repo)
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении данных: {e}")
        
        self.status_indicator.configure(text_color="gray")
        self.status_label.configure(text="Статус: ⏹ Остановлен")
        self.logger.info("Бот остановлен через GUI")
    
    def run_bot_async(self):
        """Запускает async_main в новом event loop"""
        try:
            # Создаем новый event loop для потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.asyncio_loop = loop
            
            # Создаем asyncio.Event для сигнала остановки
            self.asyncio_stop_event = asyncio.Event()
            
            # Запускаем async_main с stop_event
            loop.run_until_complete(async_main(stop_event=self.asyncio_stop_event))
        except Exception as e:
            self.logger.error(f"Ошибка при запуске бота: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            if self.asyncio_loop:
                try:
                    # Отменяем все задачи
                    tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    for task in tasks:
                        task.cancel()
                    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                    loop.close()
                except:
                    pass
            self.bot_running = False
            self.after(0, lambda: self.status_label.configure(text="Статус: Остановлен"))
            self.after(0, lambda: self.status_indicator.configure(text_color="gray"))
    
    def extract_log_level(self, line: str) -> Optional[str]:
        """Извлекает уровень логирования из строки лога"""
        # Формат: [Category] [timestamp] [LEVEL] [Module] message
        # Ищем паттерн [LEVEL] в строке
        import re
        match = re.search(r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]', line)
        if match:
            return match.group(1)
        return None
    
    def should_show_log_line(self, line: str, filter_level: str) -> bool:
        """Проверяет, должна ли строка лога отображаться согласно фильтру"""
        if filter_level == "Все":
            return True
        
        # Если строка пустая, не показываем
        if not line.strip():
            return False
        
        log_level = self.extract_log_level(line)
        if not log_level:
            # Если не удалось определить уровень, не показываем
            return False
        
        # Показываем только логи точно выбранного уровня
        return log_level == filter_level
    
    def on_log_filter_changed(self, value):
        """Обработчик изменения фильтра логов"""
        # Сбрасываем позиции, чтобы перечитать все логи с новым фильтром
        self.last_log_position.clear()
        self.log_file_mtimes.clear()
        # Очищаем текущие логи
        self.logs_text.delete("1.0", "end")
    
    def update_logs(self):
        """Обновляет логи из файлов"""
        try:
            log_level = self.log_level_filter.get()
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Читаем логи из всех категорий
            categories = ['general', 'initialization', 'dbwrite']
            new_lines = []
            
            for category in categories:
                log_file = self.logs_dir / f"{category}_{today}.log"
                if log_file.exists():
                    try:
                        # Проверяем изменение файла по времени модификации
                        current_mtime = log_file.stat().st_mtime
                        last_mtime = self.log_file_mtimes.get(category, 0)
                        
                        # Пропускаем если файл не изменился
                        if current_mtime == last_mtime:
                            continue
                        
                        self.log_file_mtimes[category] = current_mtime
                        
                        # Читаем файл полностью и берем только новые строки
                        with open(log_file, 'r', encoding='utf-8') as f:
                            f.seek(self.last_log_position.get(category, 0))
                            new_content = f.read()
                            
                            if new_content:
                                # Обновляем позицию
                                current_size = f.tell()
                                self.last_log_position[category] = current_size
                                
                                lines = new_content.splitlines(keepends=True)
                                
                                # Фильтруем по уровню
                                for line in lines:
                                    if self.should_show_log_line(line, log_level):
                                        new_lines.append(line)
                    except Exception as e:
                        pass
            
            # Добавляем новые строки батчами
            if new_lines:
                # Объединяем все строки и вставляем одним вызовом для производительности
                combined_text = ''.join(new_lines)
                self.logs_text.insert("end", combined_text)
                
                # Автоскрролл
                self.logs_text.see("end")
                
                # Ограничиваем размер (оставляем последние 50000 символов)
                content = self.logs_text.get("1.0", "end")
                if len(content) > 50000:
                    # Удаляем первые строки
                    lines = content.split('\n')
                    if len(lines) > 100:
                        # Удаляем первые 50 строк
                        self.logs_text.delete("1.0", f"{51}.0")
        except Exception as e:
            pass
        
        # Планируем следующее обновление (увеличиваем интервал если нет изменений)
        self.after(500, self.update_logs)
    
    def clear_logs(self):
        """Очищает логи"""
        self.logs_text.delete("1.0", "end")
    
    def analyze_logs(self) -> Dict[str, Any]:
        """Анализирует логи и возвращает статистику ошибок"""
        import re
        from collections import Counter
        
        log_stats = {
            'total_lines': 0,
            'by_level': {'DEBUG': 0, 'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'CRITICAL': 0},
            'errors_last_24h': 0,
            'warnings_last_24h': 0,
            'critical_last_24h': 0,
            'top_errors': [],
            'log_files_analyzed': 0
        }
        
        try:
            today = datetime.now()
            categories = ['general', 'initialization', 'dbwrite']
            
            for category in categories:
                # Анализируем сегодняшний лог
                log_file = self.logs_dir / f"{category}_{today.strftime('%Y-%m-%d')}.log"
                if not log_file.exists():
                    continue
                
                log_stats['log_files_analyzed'] += 1
                
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    log_stats['total_lines'] += len(lines)
                    
                    # Паттерн для извлечения уровня и времени
                    level_pattern = re.compile(r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]')
                    time_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
                    
                    error_messages = []
                    cutoff_time = today - timedelta(hours=24)
                    
                    for line in lines:
                        # Извлекаем уровень
                        level_match = level_pattern.search(line)
                        if level_match:
                            level = level_match.group(1)
                            if level in log_stats['by_level']:
                                log_stats['by_level'][level] += 1
                        
                        # Проверяем время для последних 24 часов
                        time_match = time_pattern.search(line)
                        if time_match:
                            try:
                                log_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
                                if log_time >= cutoff_time:
                                    if level_match:
                                        level = level_match.group(1)
                                        if level == 'ERROR':
                                            log_stats['errors_last_24h'] += 1
                                            # Извлекаем сообщение об ошибке
                                            error_msg = line.strip()
                                            if len(error_msg) > 100:
                                                error_msg = error_msg[:100] + "..."
                                            error_messages.append(error_msg)
                                        elif level == 'WARNING':
                                            log_stats['warnings_last_24h'] += 1
                                        elif level == 'CRITICAL':
                                            log_stats['critical_last_24h'] += 1
                                            error_messages.append(line.strip()[:100])
                            except ValueError:
                                pass
                    
                    # Находим самые частые ошибки
                    if error_messages:
                        error_counter = Counter(error_messages)
                        log_stats['top_errors'] = error_counter.most_common(5)
                
                except Exception as e:
                    # Пропускаем файлы, которые не удалось прочитать
                    continue
            
        except Exception as e:
            pass
        
        return log_stats
    
    def _update_stats_async(self):
        """Обновляет статистику асинхронно в отдельном потоке с таймаутом"""
        def update_in_thread():
            try:
                if not self.repo:
                    self.after(0, lambda: self.stats_text.delete("1.0", "end"))
                    self.after(0, lambda: self.stats_text.insert("1.0", "[INFO] Инициализация подключения к БД...\nСтатистика будет обновлена после подключения."))
                    self.after(5000, self._update_stats_async)
                    return
                
                # Используем ThreadPoolExecutor с таймаутом
                from concurrent.futures import ThreadPoolExecutor, TimeoutError
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.repo.get_service_stats)
                    try:
                        stats = future.result(timeout=60)  # максимум 60 секунд на всю статистику
                    except TimeoutError:
                        self._safe_log('error', 'Таймаут при получении статистики (более 60 сек)')
                        stats = {}
                
                # Анализ логов (быстро)
                try:
                    log_stats = self.analyze_logs()
                except Exception as e:
                    log_stats = {}
                    if self.logger:
                        self.logger.warning(f"Ошибка при анализе логов: {e}")
                
                stats_text = self._format_stats(stats, log_stats)
                self.after(0, lambda: self._update_stats_ui(stats_text))
                
            except Exception as e:
                error_msg = f"[ERROR] Ошибка при обновлении статистики: {e}"
                self.after(0, lambda: self.stats_text.delete("1.0", "end"))
                self.after(0, lambda: self.stats_text.insert("1.0", error_msg))
                self.after(30000, self._update_stats_async)
        
        # Запускаем в отдельном потоке
        threading.Thread(target=update_in_thread, daemon=True).start()
    
    def _update_stats_ui(self, stats_text: str):
        """Обновляет UI статистики в главном потоке"""
        try:
            self.stats_text.delete("1.0", "end")
            self.stats_text.insert("1.0", stats_text)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка при обновлении UI статистики: {e}")
        
        # Планируем следующее обновление (каждые 30 секунд)
        self.after(30000, self._update_stats_async)
    
    def update_stats(self):
        """Обновляет расширенную статистику (синхронная версия для ручного обновления)"""
        self._update_stats_async()
    
    def _format_stats(self, stats: Dict[str, Any], log_stats: Dict[str, Any]) -> str:
        """Форматирует статистику в текст"""
        try:
            stats_text = "╔" + "═" * 78 + "╗\n"
            stats_text += "║" + " " * 25 + "СТАТИСТИКА СЕРВИСА" + " " * 35 + "║\n"
            stats_text += "╚" + "═" * 78 + "╝\n\n"
            
            # === 1. ИНФОРМАЦИЯ О БАЗЕ ДАННЫХ ===
            stats_text += "┌─ БАЗА ДАННЫХ ────────────────────────────────────────────────────────────┐\n"
            stats_text += f"│ Наименование: {stats.get('db_name', ''):<64} │\n"
            stats_text += f"│ Адрес: {stats.get('db_address', ''):<69} │\n"
            stats_text += f"│ Пользователь: {stats.get('db_user', ''):<64} │\n"
            db_status = stats.get('db_status', 'unknown')
            db_reason = stats.get('db_status_reason', '')
            status_str = db_status
            if db_reason:
                status_str = f"{db_status} — {db_reason[:50]}..." if len(db_reason) > 50 else f"{db_status} — {db_reason}"
            stats_text += f"│ Статус: {status_str:<68} │\n"
            stats_text += "└──────────────────────────────────────────────────────────────────────────┘\n\n"
            
            # === 2. ТАБЛИЦЫ С КОЛИЧЕСТВОМ ЗАПИСЕЙ ===
            database_tables = stats.get('database_tables', {})
            if database_tables:
                stats_text += "┌─ ТАБЛИЦЫ БАЗЫ ДАННЫХ ───────────────────────────────────────────────────┐\n"
                sorted_tables = sorted(
                    database_tables.items(),
                    key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0,
                    reverse=True
                )
                total_records = 0
                for table, count in sorted_tables:
                    count_val = count if isinstance(count, (int, float)) else 0
                    if count_val >= 0:
                        total_records += count_val
                        formatted_count = f"{int(count_val):,}".replace(",", " ")
                        table_display = table[:35] if len(table) > 35 else table
                        stats_text += f"│ {table_display:<35} │ {formatted_count:>18} записей │\n"
                stats_text += "├" + "─" * 78 + "┤\n"
                stats_text += f"│ {'ИТОГО':<35} │ {f'{int(total_records):,}'.replace(',', ' '):>18} записей │\n"
                stats_text += "└──────────────────────────────────────────────────────────────────────────┘\n\n"
            
            # === 3. ОЧЕРЕДЬ КОМАНД ===
            queue_size = stats.get('queue_size', 0)
            stats_text += "┌─ ОЧЕРЕДЬ ────────────────────────────────────────────────────────────────┐\n"
            stats_text += f"│ Количество команд в очереди записи: {queue_size:>41,} │\n".replace(",", " ")
            stats_text += "└──────────────────────────────────────────────────────────────────────────┘\n\n"
            
            # === 4. ОТЧЁТЫ ===
            answered = stats.get('answered_suggestions', 0)
            total_suggestions = stats.get('total_suggestions', 0)
            stats_text += "┌─ ОТЧЁТЫ ─────────────────────────────────────────────────────────────────┐\n"
            stats_text += f"│ Отвеченных / всего: {answered}/{total_suggestions:<54} │\n"
            stats_text += "└──────────────────────────────────────────────────────────────────────────┘\n\n"
            
            # === 5. ПОЛЬЗОВАТЕЛИ (без заблокировавших бота) ===
            active_users = stats.get('active_users', 0)
            total_users = stats.get('total_users', 0)
            stats_text += "┌─ ПОЛЬЗОВАТЕЛИ ───────────────────────────────────────────────────────────┐\n"
            stats_text += f"│ Активных / всего (без заблокировавших бота): {active_users}/{total_users:<27} │\n"
            stats_text += "└──────────────────────────────────────────────────────────────────────────┘\n\n"
            
            # === СТАТИСТИКА ПО ЛОГАМ ===
            if log_stats['total_lines'] > 0:
                stats_text += "┌─ СТАТИСТИКА ЛОГОВ ──────────────────────────────────────────────────────┐\n"
                stats_text += f"│ Проанализировано файлов: {log_stats['log_files_analyzed']:>54} │\n"
                stats_text += f"│ Всего строк в логах: {log_stats['total_lines']:>60,} │\n".replace(",", " ")
                stats_text += "│\n"
                stats_text += "│ По уровням:\n"
                for level, count in log_stats['by_level'].items():
                    if count > 0:
                        stats_text += f"│   └─ {level:<10}: {count:>62,} │\n".replace(",", " ")
                
                stats_text += "│\n"
                stats_text += "│ За последние 24 часа:\n"
                stats_text += f"│   └─ Ошибок (ERROR): {log_stats['errors_last_24h']:>58,} │\n".replace(",", " ")
                stats_text += f"│   └─ Предупреждений (WARNING): {log_stats['warnings_last_24h']:>48,} │\n".replace(",", " ")
                stats_text += f"│   └─ Критических (CRITICAL): {log_stats['critical_last_24h']:>52,} │\n".replace(",", " ")
                
                if log_stats['top_errors']:
                    stats_text += "│\n"
                    stats_text += "│ Топ-5 частых ошибок:\n"
                    for i, (error_msg, count) in enumerate(log_stats['top_errors'], 1):
                        # Обрезаем длинные сообщения
                        display_msg = error_msg[:60] + "..." if len(error_msg) > 60 else error_msg
                        stats_text += f"│   {i}. ({count}x) {display_msg:<60} │\n"
                
                stats_text += "└──────────────────────────────────────────────────────────────────────────┘\n\n"
            
            # === ВРЕМЯ ОБНОВЛЕНИЯ ===
            stats_text += f"Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return stats_text
        except Exception as e:
            error_msg = f"Ошибка при форматировании статистики: {e}\n"
            import traceback
            error_msg += traceback.format_exc()
            return error_msg
    
    def load_config(self):
        """Загружает конфигурацию из .env"""
        try:
            env_path = Path.cwd() / '.env'
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.config_text.delete("1.0", "end")
                self.config_text.insert("1.0", content)
            else:
                self.config_text.delete("1.0", "end")
                self.config_text.insert("1.0", "# Файл .env не найден")
        except Exception as e:
            self.config_text.delete("1.0", "end")
            self.config_text.insert("1.0", f"Ошибка при загрузке конфигурации: {e}")
    
    def save_config(self):
        """Сохраняет конфигурацию в .env"""
        try:
            content = self.config_text.get("1.0", "end-1c")
            env_path = Path.cwd() / '.env'
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Перезагружаем переменные окружения
            load_dotenv(str(env_path), override=True)
            
            self.logger.info("Конфигурация сохранена")
            
            # Показываем сообщение
            dialog = ctk.CTkToplevel(self)
            dialog.title("Успех")
            dialog.geometry("300x100")
            ctk.CTkLabel(dialog, text="Конфигурация успешно сохранена!").pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении конфигурации: {e}")
            
            # Показываем ошибку
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("400x150")
            ctk.CTkLabel(dialog, text=f"Ошибка при сохранении:\n{e}").pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
    
    def check_config(self):
        """Проверяет конфигурацию"""
        try:
            required_vars = ['DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME', 'T_API_KEY', 'BM_API_KEY']
            missing = []
            
            for var in required_vars:
                if not getenv(var):
                    missing.append(var)
            
            dialog = ctk.CTkToplevel(self)
            dialog.title("Проверка конфигурации")
            dialog.geometry("400x200")
            
            if missing:
                text = f"Отсутствуют переменные:\n\n" + "\n".join(missing)
                color = "red"
            else:
                text = "Все необходимые переменные установлены!"
                color = "green"
            
            label = ctk.CTkLabel(dialog, text=text, text_color=color)
            label.pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
        except Exception as e:
            self.logger.error(f"Ошибка при проверке конфигурации: {e}")
    
    def toggle_initialization(self):
        """Переключает состояние инициализации"""
        if not self.init_running:
            self.start_initialization()
        else:
            self.stop_initialization()
    
    def start_initialization(self):
        """Запускает инициализацию данных"""
        if self.bot_running:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("400x150")
            ctk.CTkLabel(
                dialog,
                text="Нельзя запускать инициализацию\nпока бот работает.\nОстановите бота сначала."
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
            return
        
        if self.init_running:
            return
        
        self.init_running = True
        self.init_stop_event.clear()
        self.init_btn.configure(
            text="Остановить инициализацию", 
            fg_color="red",
            state="normal"
        )
        
        # Запускаем в отдельном потоке
        self.init_thread = threading.Thread(target=self.run_initialization, daemon=True)
        self.init_thread.start()
    
    def stop_initialization(self):
        """Останавливает инициализацию"""
        if not self.init_running:
            return
        
        self.init_stop_event.set()
        self.init_btn.configure(text="Остановка...", state="disabled")
        
        self.after(0, lambda: self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Запрос на остановку инициализации...\n"))
        self.after(0, lambda: self.init_status_text.see("end"))
    
    def run_initialization(self):
        """Запускает initialize_data в отдельном потоке"""
        loop = None
        try:
            self.after(0, lambda: self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Запуск инициализации...\n"))
            self.after(0, lambda: self.init_status_text.see("end"))
            
            # Создаем новый event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.init_loop = loop
            
            # Создаем обертку для проверки флага остановки
            async def initialize_with_stop_check():
                """Обертка для initialize_data с проверкой флага остановки"""
                init_task = asyncio.create_task(initialize_data())
                
                # Периодически проверяем флаг остановки
                while not init_task.done():
                    if self.init_stop_event.is_set():
                        init_task.cancel()
                        break
                    await asyncio.sleep(0.5)  # Проверяем каждые 0.5 секунды
                
                # Ждем завершения или отмены задачи
                try:
                    return await init_task
                except asyncio.CancelledError:
                    raise
            
            # Запускаем инициализацию
            try:
                loop.run_until_complete(initialize_with_stop_check())
                if not self.init_stop_event.is_set():
                    self.after(0, lambda: self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Инициализация завершена успешно!\n"))
                    self.after(0, lambda: self.init_status_text.see("end"))
            except asyncio.CancelledError:
                self.after(0, lambda: self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Инициализация остановлена пользователем\n"))
                self.after(0, lambda: self.init_status_text.see("end"))
            except Exception as e:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: {e}\n"
                self.after(0, lambda msg=error_msg: self.init_status_text.insert("end", msg))
                self.after(0, lambda: self.init_status_text.see("end"))
                import traceback
                traceback.print_exc()
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: {e}\n"
            self.after(0, lambda msg=error_msg: self.init_status_text.insert("end", msg))
            self.after(0, lambda: self.init_status_text.see("end"))
            import traceback
            traceback.print_exc()
        finally:
            if loop and not loop.is_closed():
                try:
                    # Отменяем все оставшиеся задачи
                    tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    for task in tasks:
                        task.cancel()
                    if tasks:
                        try:
                            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                        except:
                            pass
                    loop.close()
                except:
                    pass
            self.init_running = False
            self.init_loop = None
            self.after(0, lambda: self.init_btn.configure(
                text="Запустить инициализацию", 
                fg_color=("gray70", "gray30"),
                state="normal"
            ))
    
    def clear_init_state(self):
        """Очищает состояние инициализации"""
        try:
            if not self.repo:
                self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: Repository не инициализирован\n")
                self.init_status_text.see("end")
                return
            self.repo.clear_initialization_state(admin_id=ADMIN_ID)
            self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Состояние инициализации очищено\n")
            self.init_status_text.see("end")
        except Exception as e:
            self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: {e}\n")
            self.init_status_text.see("end")
    
    def confirm_clear_database(self):
        """Показывает диалог подтверждения очистки БД"""
        if self.bot_running:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Ошибка")
            dialog.geometry("400x150")
            ctk.CTkLabel(
                dialog,
                text="Нельзя очищать базу данных\nпока бот работает.\nОстановите бота сначала."
            ).pack(pady=20)
            ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()
            return
        
        # Создаем диалог подтверждения
        dialog = ctk.CTkToplevel(self)
        dialog.title("Подтверждение очистки БД")
        dialog.geometry("500x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Предупреждение
        warning_label = ctk.CTkLabel(
            dialog,
            text="ВНИМАНИЕ: БУДУТ УДАЛЕНЫ ВСЕ ДАННЫЕ ИЗ БАЗЫ ДАННЫХ!",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="red"
        )
        warning_label.pack(pady=10)
        
        info_label = ctk.CTkLabel(
            dialog,
            text="Это действие удалит все данные из таблиц:\n"
                 "- servers, players, rust_servers\n"
                 "- profiles, subscriptions\n"
                 "- filters и все связанные данные\n\n"
                 "После очистки можно будет запустить инициализацию заново.",
            justify="left"
        )
        info_label.pack(pady=10, padx=20)
        
        # Кнопки
        buttons_frame = ctk.CTkFrame(dialog)
        buttons_frame.pack(pady=20)
        
        def clear_with_preserve_games():
            dialog.destroy()
            self.clear_database(preserve_games=True)
        
        def clear_full():
            # Дополнительное подтверждение для полной очистки
            confirm_dialog = ctk.CTkToplevel(self)
            confirm_dialog.title("Финальное подтверждение")
            confirm_dialog.geometry("400x200")
            confirm_dialog.transient(self)
            confirm_dialog.grab_set()
            
            ctk.CTkLabel(
                confirm_dialog,
                text="Вы уверены, что хотите выполнить\nПОЛНУЮ очистку (включая games)?",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="red"
            ).pack(pady=20)
            
            def do_clear():
                confirm_dialog.destroy()
                dialog.destroy()
                self.clear_database(preserve_games=False)
            
            ctk.CTkButton(
                confirm_dialog,
                text="ДА, очистить всё",
                command=do_clear,
                fg_color="red",
                hover_color="darkred"
            ).pack(side="left", padx=10, pady=20)
            
            ctk.CTkButton(
                confirm_dialog,
                text="Отмена",
                command=confirm_dialog.destroy
            ).pack(side="left", padx=10, pady=20)
        
        ctk.CTkButton(
            buttons_frame,
            text="Очистить (сохранить games)",
            command=clear_with_preserve_games,
            width=200,
            fg_color="orange",
            hover_color="darkorange"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="Полная очистка",
            command=clear_full,
            width=150,
            fg_color="red",
            hover_color="darkred"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            command=dialog.destroy,
            width=100
        ).pack(side="left", padx=5)
    
    def clear_database(self, preserve_games: bool = True):
        """Очищает базу данных (запускает очистку в фоновом потоке)"""
        if not self.repo:
            self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: Repository не инициализирован\n")
            self.init_status_text.see("end")
            return
        self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Начало очистки базы данных...\n")
        self.init_status_text.see("end")
        tables_to_clear = [
            tables.LOGS,
            tables.SUGGESTIONS,
            tables.SUBSCRIPTIONS,
            tables.PLAYER_FILTERS,
            tables.SERVER_FILTERS,
            tables.RUST_SERVERS_FILTERS,
            tables.PLAYERS_SERVERS,
            tables.SERVERS_HISTORY,
            tables.PLAYERS_HISTORY,
            tables.RUST_SERVERS,
            tables.PROFILES,
            tables.SERVERS,
            tables.PLAYERS,
        ]
        if not preserve_games:
            tables_to_clear.append(tables.GAMES)
        total_tables = len(tables_to_clear)

        def _do_clear():
            try:
                cleared_count = self.repo.clear_tables_for_init(tables_to_clear, preserve_games)
                success_msg = f"[{datetime.now().strftime('%H:%M:%S')}] База данных успешно очищена! Очищено таблиц: {cleared_count}/{total_tables}\n"
                if preserve_games:
                    success_msg += f"[{datetime.now().strftime('%H:%M:%S')}] Восстановлены начальные данные в таблице {tables.GAMES}\n"
                self.after(0, lambda msg=success_msg: self.init_status_text.insert("end", msg))
                self.after(0, lambda: self.init_status_text.see("end"))
                try:
                    self.repo.clear_initialization_state(admin_id=ADMIN_ID)
                    self.after(0, lambda: self.init_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Состояние инициализации очищено\n"))
                    self.after(0, lambda: self.init_status_text.see("end"))
                except Exception:
                    pass
                self.after(0, self.update_stats)
            except Exception as e:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при очистке БД: {e}\n"
                self.after(0, lambda msg=error_msg: self.init_status_text.insert("end", msg))
                self.after(0, lambda: self.init_status_text.see("end"))
                import traceback
                traceback.print_exc()

        thread = threading.Thread(target=_do_clear, daemon=True)
        thread.start()
    
    def create_backup_gui(self):
        """Создает бэкап БД через GUI"""
        backup_name = self.backup_name_entry.get().strip()
        backup_name = backup_name if backup_name else None
        
        # Отключаем кнопку на время создания
        self.backup_status_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Начало создания бэкапа...\n")
        self.backup_status_text.see("end")
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(
            target=self._create_backup_thread,
            args=(backup_name,),
            daemon=True
        )
        thread.start()
    
    def _create_backup_thread(self, backup_name: Optional[str]):
        """Создает бэкап в отдельном потоке"""
        try:
            # Получаем переменные окружения
            env_vars = check_env_variables()
            if not env_vars:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: не удалось загрузить переменные окружения\n"
                self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
                return
            
            # Создаем бэкап
            backup_id = create_backup(env_vars, backup_name)
            
            if backup_id:
                success_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Бэкап успешно создан! ID: {backup_id}\n"
                self.after(0, lambda msg=success_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
                # Обновляем список бэкапов
                self.after(0, self.refresh_backups_list)
            else:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: не удалось создать бэкап\n"
                self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при создании бэкапа: {e}\n"
            self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
            self.after(0, lambda: self.backup_status_text.see("end"))
            import traceback
            traceback.print_exc()
    
    def refresh_backups_list(self):
        """Обновляет список бэкапов в GUI"""
        try:
            backups = list_backups()
            
            # Очищаем текущий список (оптимизированно - уничтожаем только виджеты)
            for widget in self.backups_scroll_frame.winfo_children():
                widget.destroy()
            
            if not backups:
                no_backups_label = ctk.CTkLabel(
                    self.backups_scroll_frame,
                    text="Бэкапы не найдены",
                    font=ctk.CTkFont(size=12),
                    text_color="gray"
                )
                no_backups_label.pack(pady=10)
                return
            
            # Создаем элементы списка (батчинг для производительности)
            # Форматируем даты заранее
            formatted_backups = []
            for backup in backups:
                created_at = datetime.fromisoformat(backup['created_at']).strftime('%Y-%m-%d %H:%M:%S')
                formatted_backups.append((backup, created_at))
            
            for backup, created_at in formatted_backups:
                backup_frame = ctk.CTkFrame(self.backups_scroll_frame)
                backup_frame.pack(fill="x", padx=5, pady=5)
                
                # Информация о бэкапе
                info_text = f"{backup['name']} | {created_at} | {backup['size_mb']} MB"
                
                info_label = ctk.CTkLabel(
                    backup_frame,
                    text=info_text,
                    font=ctk.CTkFont(size=11),
                    anchor="w"
                )
                info_label.pack(side="left", padx=10, pady=5)
                
                # Кнопка восстановления (с правильным замыканием)
                restore_btn = ctk.CTkButton(
                    backup_frame,
                    text="Восстановить",
                    command=self._make_restore_callback(backup['id']),
                    width=120,
                    height=30,
                    fg_color="orange",
                    hover_color="darkorange"
                )
                restore_btn.pack(side="right", padx=5, pady=5)
                
                # Кнопка пересоздания (с правильным замыканием)
                recreate_btn = ctk.CTkButton(
                    backup_frame,
                    text="Пересоздать",
                    command=self._make_recreate_callback(backup['id']),
                    width=120,
                    height=30,
                    fg_color="blue",
                    hover_color="darkblue"
                )
                recreate_btn.pack(side="right", padx=5, pady=5)
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при обновлении списка бэкапов: {e}\n"
            self.backup_status_text.insert("end", error_msg)
            self.backup_status_text.see("end")
    
    def restore_backup_gui(self, backup_id: str):
        """Восстанавливает БД из бэкапа через GUI"""
        # Показываем диалог подтверждения
        dialog = ctk.CTkToplevel(self)
        dialog.title("Подтверждение восстановления")
        dialog.geometry("500x200")
        dialog.transient(self)
        dialog.grab_set()
        
        # Центрируем окно
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (200 // 2)
        dialog.geometry(f"500x200+{x}+{y}")
        
        ctk.CTkLabel(
            dialog,
            text="ВНИМАНИЕ!",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="red"
        ).pack(pady=10)
        
        ctk.CTkLabel(
            dialog,
            text="Восстановление из бэкапа перезапишет текущую базу данных!\nВсе текущие данные будут потеряны!",
            font=ctk.CTkFont(size=12),
            justify="center"
        ).pack(pady=10)
        
        buttons_frame = ctk.CTkFrame(dialog)
        buttons_frame.pack(pady=20)
        
        def confirm_restore():
            dialog.destroy()
            self._restore_backup_thread(backup_id)
        
        ctk.CTkButton(
            buttons_frame,
            text="Да, восстановить",
            command=confirm_restore,
            width=150,
            fg_color="red",
            hover_color="darkred"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            command=dialog.destroy,
            width=150
        ).pack(side="left", padx=10)
    
    def _restore_backup_thread(self, backup_id: str):
        """Восстанавливает бэкап в отдельном потоке"""
        try:
            # Получаем переменные окружения
            env_vars = check_env_variables()
            if not env_vars:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: не удалось загрузить переменные окружения\n"
                self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
                return
            
            status_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Начало восстановления из бэкапа...\n"
            self.after(0, lambda msg=status_msg: self.backup_status_text.insert("end", msg))
            self.after(0, lambda: self.backup_status_text.see("end"))
            
            # Восстанавливаем бэкап (пропускаем подтверждение, т.к. оно уже было в GUI)
            success = restore_backup(env_vars, backup_id, skip_confirmation=True)
            
            if success:
                success_msg = f"[{datetime.now().strftime('%H:%M:%S')}] База данных успешно восстановлена из бэкапа!\n"
                self.after(0, lambda msg=success_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
            else:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: не удалось восстановить базу данных\n"
                self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при восстановлении: {e}\n"
            self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
            self.after(0, lambda: self.backup_status_text.see("end"))
            import traceback
            traceback.print_exc()
    
    def recreate_backup_gui(self, backup_id: str):
        """Пересоздает бэкап через GUI (восстанавливает и создает новый)"""
        # Показываем диалог подтверждения
        dialog = ctk.CTkToplevel(self)
        dialog.title("Подтверждение пересоздания бэкапа")
        dialog.geometry("600x250")
        dialog.transient(self)
        dialog.grab_set()
        
        # Центрируем окно
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (250 // 2)
        dialog.geometry(f"600x250+{x}+{y}")
        
        ctk.CTkLabel(
            dialog,
            text="Пересоздание бэкапа",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="blue"
        ).pack(pady=10)
        
        ctk.CTkLabel(
            dialog,
            text="Это действие выполнит следующие шаги:\n"
                 "1. Восстановит данные из выбранного бэкапа в БД\n"
                 "2. Создаст новый оптимизированный бэкап\n\n"
                 "ВНИМАНИЕ: Текущие данные в БД будут перезаписаны!",
            font=ctk.CTkFont(size=12),
            justify="left"
        ).pack(pady=10, padx=20)
        
        buttons_frame = ctk.CTkFrame(dialog)
        buttons_frame.pack(pady=20)
        
        def confirm_recreate():
            dialog.destroy()
            self._recreate_backup_thread(backup_id)
        
        ctk.CTkButton(
            buttons_frame,
            text="Да, пересоздать",
            command=confirm_recreate,
            width=150,
            fg_color="blue",
            hover_color="darkblue"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="Отмена",
            command=dialog.destroy,
            width=150
        ).pack(side="left", padx=10)
    
    def _recreate_backup_thread(self, backup_id: str):
        """Пересоздает бэкап в отдельном потоке"""
        try:
            # Получаем переменные окружения
            env_vars = check_env_variables()
            if not env_vars:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: не удалось загрузить переменные окружения\n"
                self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
                return
            
            status_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Начало пересоздания бэкапа...\n"
            self.after(0, lambda msg=status_msg: self.backup_status_text.insert("end", msg))
            self.after(0, lambda: self.backup_status_text.see("end"))
            
            # Пересоздаем бэкап
            new_backup_id = recreate_backup(env_vars, backup_id)
            
            if new_backup_id:
                success_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Бэкап успешно пересоздан! Новый ID: {new_backup_id}\n"
                self.after(0, lambda msg=success_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
                # Обновляем список бэкапов
                self.after(0, self.refresh_backups_list)
            else:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: не удалось пересоздать бэкап\n"
                self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
                self.after(0, lambda: self.backup_status_text.see("end"))
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при пересоздании: {e}\n"
            self.after(0, lambda msg=error_msg: self.backup_status_text.insert("end", msg))
            self.after(0, lambda: self.backup_status_text.see("end"))
            import traceback
            traceback.print_exc()
    
    def _make_restore_callback(self, backup_id: str):
        """Создает callback для восстановления бэкапа с правильным замыканием"""
        return lambda: self.restore_backup_gui(backup_id)
    
    def _make_recreate_callback(self, backup_id: str):
        """Создает callback для пересоздания бэкапа с правильным замыканием"""
        return lambda: self.recreate_backup_gui(backup_id)
    
    def on_closing(self):
        """Обработчик закрытия окна"""
        if self.bot_running:
            self.stop_bot()
            # Ждем немного для корректного завершения
            self.after(1000, self.destroy)
        else:
            self.destroy()
    
    def destroy(self):
        """Закрывает приложение"""
        # Сохраняем данные, если репозиторий инициализирован
        if self.repo is not None:
            try:
                save_data_on_exit(self.repo)
            except Exception as e:
                self._safe_log('error', f'Ошибка при сохранении данных: {e}')
        
        # Закрываем logger
        if hasattr(self, 'logger') and self.logger:
            try:
                self.logger.close()
            except:
                pass
        
        super().destroy()


if __name__ == "__main__":
    app = BotGUIApp()
    app.mainloop()