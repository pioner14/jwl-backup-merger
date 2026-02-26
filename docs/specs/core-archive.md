# spec://core/archive

## Работа с архивами .jwlibrary

**Версия**: 1.0  
**Статус**: stable  
**Модуль**: `jwl_backup_merger.py::extract_from_archive()`, `create_backup_archive()`

---

## Назначение

Компонент отвечает за:
- Извлечение `userData.db` и `manifest.json` из архивов `.jwlibrary`
- Создание финального архива для импорта в JW Library

---

## Формат архива .jwlibrary

Архив `.jwlibrary` — это ZIP-архив со следующей структурой:

```
backup.jwlibrary
├── userData.db      # SQLite база данных с заметками, выделениями и т.д.
└── manifest.json    # Метаданные бэкапа
```

### Альтернативные имена БД

Некоторые версии JW Library могут использовать:
- `userData.db` (стандарт)
- `user_data.db` (альернатива)

**Решение**: Проверять оба имени при извлечении.

---

## Контракт: extract_from_archive

```python
def extract_from_archive(
    archive_path: Path,
    extract_dir: str
) -> Tuple[Path, Path]:
    """
    Извлекает архив JW Library во временную директорию.
    
    Args:
        archive_path: Путь к архиву .jwlibrary
        extract_dir: Директория для извлечения
    
    Returns:
        Кортеж (db_path, manifest_path)
    
    Raises:
        zipfile.BadZipFile: Если архив повреждён
        FileNotFoundError: Если userData.db не найден
    """
```

---

## Контракт: create_backup_archive

```python
def create_backup_archive(
    db_path: Path,
    manifest_data: Dict,
    output_archive_path: Path
) -> None:
    """
    Создаёт архив бэкапа с базой данных и манифестом.
    
    Args:
        db_path: Путь к объединённой базе данных
        manifest_data: Словарь с данными манифеста
        output_archive_path: Путь для выходного архива
    
    Returns:
        None (архив записывается на диск)
    """
```

---

## Сжатие

**Решение**: Использовать `ZIP_DEFLATED` для сжатия.

**Обоснование**:
- Уменьшает размер бэкапа на 60-80%
- Поддерживается стандартной библиотекой Python
- Совместимо с JW Library

---

## Временные файлы

### manifest.json

При создании архива манифест записывается во временный файл, который удаляется после создания архива:

```python
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(manifest_data, f)
    manifest_path = f.name

try:
    # создание архива
finally:
    os.unlink(manifest_path)
```

**Обоснование**: zipfile требует путь к файлу, а не file-like объект.

---

## Валидация

### При извлечении

1. Проверка существования `userData.db` (или `user_data.db`)
2. Проверка существования `manifest.json`
3. Валидация схемы БД (см. `spec://core/schema`)

### При создании

1. Проверка существования `db_path`
2. Валидация структуры `manifest_data`

---

## Ошибки

| Ошибка | Обработка |
|--------|-----------|
| BadZipFile | Логировать, пропустить архив |
| FileNotFoundError | Логировать, пропустить архив |
| SQLite error | Логировать, откат транзакции |

---

## Тесты

См. `spec://test/integration#archive`

---

## История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-02-26 | Initial spec |
