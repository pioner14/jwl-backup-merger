#!/bin/bash

echo "Сборка кроссплатформенного бинарника для JW Library Backup Merger"
echo "================================================================="

# Проверяем, установлен ли PyInstaller
if ! python3 -m PyInstaller --version &>/dev/null; then
    echo "PyInstaller не установлен. Установите его командой:"
    echo "pip install pyinstaller"
    echo ""
    echo "Или используйте скрипт напрямую: python3 jwl_backup_merger.py"
    exit 1
fi

echo "PyInstaller найден. Начинаем сборку..."

# Запускаем PyInstaller
python3 -m PyInstaller jwl_backup_merger.spec

if [ $? -eq 0 ]; then
    echo ""
    echo "Сборка завершена успешно!"
    echo ""
    echo "Бинарник находится в директории ./dist/:"
    ls -la dist/
    echo ""
    echo "Вы можете скопировать бинарник на другую систему и запустить без установки Python:"
    echo "./jwl-backup-merger <путь_к_директории_с_архивами>"
else
    echo "Ошибка при сборке бинарника"
    exit 1
fi