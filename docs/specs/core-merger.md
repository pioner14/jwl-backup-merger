# spec://core/merger

## Слияние записей с дедупликацией

**Версия**: 1.0  
**Статус**: stable  
**Модуль**: `jwl_backup_merger.py::copy_unique_records()`, `create_merged_db()`

---

## Назначение

Компонент отвечает за:
- Копирование уникальных записей из исходных архивов в объединённую БД
- Исключение дубликатов на основе хэшей
- Маппинг ID для связанных таблиц

---

## Контракт: copy_unique_records

```python
def copy_unique_records(
    src_conn: sqlite3.Connection,
    dst_conn: sqlite3.Connection,
    table_name: str,
    seen_hashes: Set[str],
    id_mapping: Optional[Dict[str, Dict[int, int]]] = None
) -> Set[str]:
    """
    Копирует уникальные записи из исходной БД в целевую.
    
    Args:
        src_conn: Подключение к исходной БД
        dst_conn: Подключение к целевой БД
        table_name: Имя таблицы для копирования
        seen_hashes: Множество хэшей уже обработанных записей
        id_mapping: Словарь для маппинга ID {table_name: {old_id: new_id}}
    
    Returns:
        Обновлённое множество seen_hashes
    
    Raises:
        ValueError: Если имя таблицы недопустимо
    """
```

---

## Алгоритм

```
1. Проверить table_name в ALLOWED_TABLES
2. Получить все записи из src_conn.table_name
3. Для каждой записи:
   a. Вычислить хэш (spec://core/hash)
   b. Если хэш в seen_hashes:
      - Пропустить запись (дубликат)
   c. Иначе:
      - Обновить foreign key согласно id_mapping
      - Вставить запись в dst_conn
      - Сохранить маппинг old_id → new_id
      - Добавить хэш в seen_hashes
```

---

## Порядок обработки таблиц

```python
TABLE_ORDER = ['Location', 'UserMark', 'Tag', 'Note', 'TagMap', 'Bookmark', 'BlockRange']
```

**Обоснование**:

| Таблица | Зависимости |
|---------|-------------|
| Location | Нет |
| UserMark | Нет |
| Tag | Нет |
| Note | Location, UserMark |
| TagMap | Tag |
| Bookmark | Location |
| BlockRange | UserMark |

Сначала обрабатываются родительские таблицы, затем дочерние.

---

## Маппинг ID

### Проблема

При вставке записи с `AUTOINCREMENT` первичный ключ может измениться:
- Исходная БД: `Tag(TagId=1, Name='Test')`
- Целевая БД: `Tag(TagId=1, Name='Existing')` уже существует
- Новая запись: `Tag(TagId=2, Name='Test')`

### Решение

Сохранять маппинг `{old_id: new_id}` для каждой таблицы:

```python
id_mapping = {
    'Tag': {1: 2, 3: 4},      # old TagId → new TagId
    'UserMark': {5: 10},       # old UserMarkId → new UserMarkId
    'Location': {7: 12}        # old LocationId → new LocationId
}
```

### Обновление foreign keys

При копировании дочерних таблиц обновлять foreign keys:

**TagMap**:
```python
if table_name == 'TagMap' and 'Tag' in id_mapping:
    old_tag_id = record['TagId']
    record['TagId'] = id_mapping['Tag'].get(old_tag_id, old_tag_id)
```

**Note**:
```python
if table_name == 'Note':
    if 'Location' in id_mapping:
        record['LocationId'] = id_mapping['Location'].get(record['LocationId'], record['LocationId'])
    if 'UserMark' in id_mapping and record['UserMarkId']:
        record['UserMarkId'] = id_mapping['UserMark'].get(record['UserMarkId'], record['UserMarkId'])
```

**BlockRange**:
```python
if table_name == 'BlockRange' and 'UserMark' in id_mapping:
    record['UserMarkId'] = id_mapping['UserMark'].get(record['UserMarkId'], record['UserMarkId'])
```

**Bookmark**:
```python
if table_name == 'Bookmark' and 'Location' in id_mapping:
    record['LocationId'] = id_mapping['Location'].get(record['LocationId'], record['LocationId'])
```

---

## Транзакции

### commit/rollback

```python
try:
    # обработка всех архивов
    merged_conn.commit()
except Exception as e:
    merged_conn.rollback()
    raise
```

**Обоснование**: Атомарность — либо все архивы объединены, либо ни одного.

### Foreign keys

```python
# На время импорта
merged_conn.execute("PRAGMA foreign_keys = OFF")

# После импорта
merged_conn.execute("PRAGMA foreign_keys = ON")
merged_conn.commit()
```

**Обоснование**: Отключение foreign keys на время импорта позволяет вставлять записи в любом порядке.

---

## Обработка ошибок

| Ошибка | Обработка |
|--------|-----------|
| ValueError (недопустимая таблица) | Выбросить исключение |
| sqlite3.OperationalError (нет колонки) | Пропустить запись, логировать |
| sqlite3.IntegrityError (дубликат) | Пропустить (INSERT OR IGNORE) |

---

## Тесты

См. `spec://test/integration#TestCopyUniqueRecords`

---

## История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-02-26 | Initial spec |
