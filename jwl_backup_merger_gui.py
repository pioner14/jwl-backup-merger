#!/usr/bin/env python3
"""
JW Library Backup Merger - GUI
==============================
Графический интерфейс для объединения бэкапов JW Library.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import logging
from datetime import datetime

# Импортируем функции из основного модуля
from jwl_backup_merger import (
    create_merged_db,
    create_manifest_from_archives,
    create_backup_archive,
    validate_database_schema
)


class BackupMergerGUI:
    """Графический интерфейс для слияния бэкапов JW Library"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("JW Library Backup Merger")
        self.root.resizable(True, True)
        
        # Переменные
        self.input_dir = tk.StringVar()
        self.output_file = tk.StringVar(value="combined_backup.jwlibrary")
        self.archive_files = []
        self.is_processing = False
        
        # Настройка логирования
        self.setup_logging()
        
        # Создание интерфейса
        self.setup_ui()
        
    def setup_logging(self):
        """Настройка логирования в GUI"""
        self.log_messages = []
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_ui(self):
        """Создание элементов интерфейса"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Настройка растягивания
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Заголовок
        title_label = ttk.Label(
            main_frame,
            text="JW Library Backup Merger",
            font=('Helvetica', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # 1. Выбор входной папки
        input_frame = ttk.LabelFrame(main_frame, text="1. Выберите папку с бэкапами:", padding="5")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        input_frame.columnconfigure(0, weight=1)
        
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_dir, width=60)
        self.input_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.browse_input_btn = ttk.Button(
            input_frame,
            text="Обзор...",
            command=self.browse_input_folder
        )
        self.browse_input_btn.grid(row=0, column=1)
        
        # 2. Список архивов
        list_frame = ttk.LabelFrame(main_frame, text="2. Найдено архивов:", padding="5")
        list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Список с прокруткой
        list_container = ttk.Frame(list_frame)
        list_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)
        
        self.archive_listbox = tk.Listbox(
            list_container,
            height=6,
            width=60,
            font=('Courier', 9)
        )
        self.archive_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.archive_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.archive_listbox.configure(yscrollcommand=scrollbar.set)
        
        # 3. Выходной файл
        output_frame = ttk.LabelFrame(main_frame, text="3. Выходной файл:", padding="5")
        output_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        output_frame.columnconfigure(0, weight=1)
        
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_file, width=60)
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.browse_output_btn = ttk.Button(
            output_frame,
            text="Обзор...",
            command=self.browse_output_file
        )
        self.browse_output_btn.grid(row=0, column=1)
        
        # Опция открытия папки
        self.open_folder_var = tk.BooleanVar(value=True)
        open_folder_check = ttk.Checkbutton(
            main_frame,
            text="Открыть папку после завершения",
            variable=self.open_folder_var
        )
        open_folder_check.grid(row=4, column=0, sticky=tk.W, pady=5)
        
        # Кнопка "Объединить"
        self.merge_btn = ttk.Button(
            main_frame,
            text="⚡ Объединить",
            command=self.start_merge,
            style='Accent.TButton'
        )
        self.merge_btn.grid(row=5, column=0, pady=20)
        
        # Прогресс-бар
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Строка состояния
        self.status_var = tk.StringVar(value="Готово к работе")
        self.status_label = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            font=('Helvetica', 10),
            foreground='gray'
        )
        self.status_label.grid(row=7, column=0, sticky=tk.W)
        
        # Лог (скрытый, для отладки)
        log_frame = ttk.LabelFrame(main_frame, text="Лог:", padding="5")
        log_frame.grid(row=8, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=8, width=60, font=('Courier', 8))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
    def browse_input_folder(self):
        """Выбор папки с бэкапами"""
        folder = filedialog.askdirectory(title="Выберите папку с бэкапами")
        if folder:
            self.input_dir.set(folder)
            self.update_archive_list()
    
    def browse_output_file(self):
        """Выбор выходного файла"""
        file = filedialog.asksaveasfilename(
            title="Сохранить как",
            defaultextension=".jwlibrary",
            filetypes=[("JW Library Backup", "*.jwlibrary"), ("All Files", "*.*")],
            initialfile="combined_backup.jwlibrary"
        )
        if file:
            self.output_file.set(file)
    
    def update_archive_list(self):
        """Обновление списка найденных архивов"""
        self.archive_listbox.delete(0, tk.END)
        self.archive_files = []
        
        input_path = Path(self.input_dir.get())
        if not input_path.exists():
            self.status_var.set("❌ Папка не существует")
            return
        
        # Поиск архивов
        archive_files = list(input_path.glob('*.jwlibrary'))
        
        if not archive_files:
            self.archive_listbox.insert(tk.END, "❌ Не найдено файлов .jwlibrary")
            self.status_var.set("❌ Не найдено файлов .jwlibrary")
            self.merge_btn.configure(state='disabled')
            return
        
        self.archive_files = archive_files
        
        # Отображение
        for archive in archive_files:
            size_kb = archive.stat().st_size // 1024
            self.archive_listbox.insert(
                tk.END,
                f"📄 {archive.name[:50]} ({size_kb} KB)"
            )
        
        count = len(archive_files)
        self.status_var.set(f"✅ Найдено архивов: {count}")
        self.merge_btn.configure(state='normal')
        self.log(f"Найдено {count} архивов для объединения")
    
    def log(self, message):
        """Запись в лог GUI"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_messages.append(log_entry)
        self.log_text.insert(tk.END, log_entry + "\n")
        self.log_text.see(tk.END)
    
    def start_merge(self):
        """Запуск процесса слияния"""
        if self.is_processing:
            return
        
        if not self.archive_files:
            messagebox.showerror("Ошибка", "Выберите папку с бэкапами")
            return
        
        self.is_processing = True
        self.merge_btn.configure(state='disabled', text="⏳ Обработка...")
        self.progress_var.set(0)
        self.log("=" * 60)
        self.log("Начало слияния...")
        
        # Запуск в отдельном потоке
        thread = threading.Thread(target=self.merge_worker, daemon=True)
        thread.start()
    
    def merge_worker(self):
        """Рабочий поток для слияния (выполняется в фоне)"""
        try:
            output_path = Path(self.output_file.get())
            output_dir = output_path.parent
            
            self.log(f"Выходной файл: {output_path}")
            self.root.after(0, lambda: self.status_var.set("⏳ Создание объединённой базы данных..."))
            self.root.after(0, lambda: self.progress_var.set(10))
            
            # Шаг 1: Создание объединённой БД
            temp_db = output_dir / 'merged_userData.db'
            create_merged_db(
                self.archive_files,
                temp_db,
                verbose=False
            )
            self.root.after(0, lambda: self.progress_var.set(40))
            self.log("✓ База данных создана")
            
            # Шаг 2: Подсчёт результатов
            self.root.after(0, lambda: self.status_var.set("⏳ Подсчёт результатов..."))
            import sqlite3
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            
            tables = ['Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange']
            results = {}
            total = 0
            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    count = cursor.fetchone()[0]
                    results[table] = count
                    total += count
                    self.log(f"  {table}: {count} записей")
                except sqlite3.OperationalError:
                    results[table] = 0
            
            conn.close()
            self.root.after(0, lambda: self.progress_var.set(60))
            self.log(f"✓ Всего записей: {total:,}")
            
            # Шаг 3: Создание манифеста
            self.root.after(0, lambda: self.status_var.set("⏳ Создание манифеста..."))
            manifest_data = create_manifest_from_archives(self.archive_files, temp_db)
            self.root.after(0, lambda: self.progress_var.set(80))
            self.log("✓ Манифест создан")
            
            # Шаг 4: Создание финального архива
            self.root.after(0, lambda: self.status_var.set("⏳ Создание финального архива..."))
            create_backup_archive(temp_db, manifest_data, output_path)
            self.root.after(0, lambda: self.progress_var.set(100))
            self.log("✓ Архив создан")
            
            # Очистка временного файла
            temp_db.unlink()
            
            # Успех
            self.root.after(0, lambda: self.status_var.set(f"✅ Готово! {total:,} записей"))
            self.root.after(0, lambda: self.log(f"Слияние завершено успешно!"))
            
            messagebox.showinfo(
                "Готово!",
                f"Объединённый бэкап создан:\n{output_path}\n\n"
                f"Всего записей: {total:,}"
            )
            
            # Открытие папки
            if self.open_folder_var.get():
                self.open_folder(output_dir)
            
        except Exception as e:
            error_msg = f"❌ Ошибка: {str(e)}"
            self.log(error_msg)
            self.root.after(0, lambda: self.status_var.set(error_msg))
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.merge_btn.configure(state='normal', text="⚡ Объединить"))
    
    def open_folder(self, path):
        """Открытие папки в файловом менеджере"""
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as e:
            self.log(f"Не удалось открыть папку: {e}")


def main():
    """Точка входа GUI"""
    root = tk.Tk()
    
    # Настройка стиля
    style = ttk.Style()
    style.theme_use('clam')  # Более современный вид
    
    # Настройка размеров окна
    root.geometry("700x650")
    root.minsize(600, 500)
    
    # Запуск приложения
    app = BackupMergerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
