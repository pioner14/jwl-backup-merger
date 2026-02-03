# JW Library Backup Merger
# Установочный скрипт для Linux/macOS

set -e

echo "Установка JW Library Backup Merger"
echo "=================================="

# Проверяем, установлен ли Python
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: python3 не найден. Пожалуйста, установите Python 3."
    exit 1
fi

# Проверяем версию Python
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$PYTHON_VERSION" < "3.6" ]]; then
    echo "Ошибка: требуется Python 3.6 или выше. Установлена версия: $PYTHON_VERSION"
    exit 1
fi

echo "Python $PYTHON_VERSION найден"

# Создаем директорию для установки (если не указана, используем ~/jwl-backup-merger)
INSTALL_DIR="${1:-$HOME/jwl-backup-merger}"

echo "Установка в директорию: $INSTALL_DIR"

# Создаем директорию
mkdir -p "$INSTALL_DIR"

# Копируем файлы
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/jwl_backup_merger.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || echo "# JW Library Backup Merger" > "$INSTALL_DIR/README.md"

# Создаем исполняемый скрипт-обертку
cat > "$INSTALL_DIR/jwl-merge" << 'EOF'
#!/bin/bash
python3 "$(dirname "$0")/jwl_backup_merger.py" "$@"
EOF

chmod +x "$INSTALL_DIR/jwl-merge"

# Устанавливаем зависимости
echo "Проверка зависимостей..."
if ! python3 -c "import sqlite3, hashlib, json, zipfile"; then
    echo "Ошибка: отсутствуют необходимые зависимости Python"
    exit 1
fi

echo ""
echo "Установка завершена!"
echo ""
echo "Использование:"
echo "  $INSTALL_DIR/jwl-merge <путь_к_директории_с_архивами>"
echo ""
echo "Пример:"
echo "  $INSTALL_DIR/jwl-merge ./backups"
echo ""
echo "Для добавления в PATH добавьте в ~/.bashrc или ~/.zshrc:"
echo "  export PATH=\$PATH:$INSTALL_DIR"
echo ""

# Предлагаем добавить в PATH
read -p "Добавить в PATH автоматически? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SHELL_PROFILE="$HOME/.bashrc"
    if [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_PROFILE="$HOME/.zshrc"
    fi
    
    if [[ -f "$SHELL_PROFILE" ]]; then
        echo "export PATH=\$PATH:$INSTALL_DIR" >> "$SHELL_PROFILE"
        echo "Добавлено в $SHELL_PROFILE"
        echo "Для применения изменений выполните: source $SHELL_PROFILE"
    else
        echo "Файл $SHELL_PROFILE не найден, добавьте вручную:"
        echo "  export PATH=\$PATH:$INSTALL_DIR"
    fi
fi