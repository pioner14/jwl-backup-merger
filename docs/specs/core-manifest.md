# spec://core/manifest

## Создание манифеста бэкапа

**Версия**: 1.0  
**Статус**: stable  
**Модуль**: `jwl_backup_merger.py::create_manifest_from_archives()`

---

## Назначение

Компонент создаёт `manifest.json` для объединённого бэкапа на основе первого исходного архива.

---

## Структура manifest.json

```json
{
  "name": "CombinedUserDataBackup_2026-02-26_12-30-45",
  "creationDate": "2026-02-26",
  "userDataBackup": {
    "hash": "sha256_of_userData.db",
    "lastModifiedDate": "2026-02-26T12:30:45+00:00",
    "userMarkCount": 150
  }
}
```

---

## Контракт

```python
def create_manifest_from_archives(
    archive_paths: List[Path],
    output_db_path: Path
) -> Dict:
    """
    Создаёт манифест на основе первого архива и объединённой БД.
    
    Args:
        archive_paths: Список путей к исходным архивам
        output_db_path: Путь к объединённой базе данных
    
    Returns:
        Словарь с данными манифеста
    """
```

---

## Алгоритм

```
1. Извлечь manifest.json из первого архива
2. Вычислить SHA-256 хэш объединённой userData.db
3. Подсчитать количество записей в UserMark
4. Обновить поля манифеста:
   - name: "CombinedUserDataBackup_{timestamp}"
   - creationDate: текущая дата
   - userDataBackup.hash: хэш БД
   - userDataBackup.lastModifiedDate: текущая дата+время
   - userDataBackup.userMarkCount: количество выделений
5. Вернуть обновлённый манифест
```

---

## Формат даты

```python
datetime.now().isoformat().split('.')[0] + "+00:00"
# Пример: "2026-02-26T12:30:45+00:00"
```

**Обоснование**: Формат ISO 8601 с timezone offset требуется JW Library.

---

## Поля манифеста

| Поле | Источник | Формат |
|------|----------|--------|
| name | Генерируется | `CombinedUserDataBackup_{YYYY-MM-DD_HH-MM-SS}` |
| creationDate | Генерируется | `YYYY-MM-DD` |
| userDataBackup.hash | Вычисляется | `sha256` (hex) |
| userDataBackup.lastModifiedDate | Генерируется | ISO 8601 |
| userDataBackup.userMarkCount | Подсчитывается | integer |

---

## Тесты

Прямо не тестируется (интеграция с `create_backup_archive`).

**TODO**: Добавить тесты для `create_manifest_from_archives()`.

---

## История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-02-26 | Initial spec |
