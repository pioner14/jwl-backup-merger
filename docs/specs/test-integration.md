# spec://test/integration

## Интеграционные тесты

**Версия**: 1.0  
**Статус**: stable  
**Модуль**: `tests/test_integration.py`

---

## Назначение

Проверка корректности слияния баз данных, включая:
- Whitelist таблиц
- Порядок обработки таблиц
- Маппинг первичных ключей
- Копирование уникальных записей
- Валидацию схемы

---

## Тесты ALLOWED_TABLES

### `test_allowed_tables_contains_all_tables`

**Проверка**: Whitelist содержит все поддерживаемые таблицы.

```python
required_tables = {'Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange'}
assert required_tables.issubset(ALLOWED_TABLES)
```

---

### `test_allowed_tables_is_frozenset`

**Проверка**: ALLOWED_TABLES — неизменяемый frozenset.

```python
assert isinstance(ALLOWED_TABLES, frozenset)
```

**Обоснование**: Защита от случайного изменения в runtime.

---

## Тесты TABLE_ORDER

### `test_table_order_is_list`

**Проверка**: TABLE_ORDER — список.

---

### `test_tag_before_tagmap`

**Проверка**: Tag обрабатывается перед TagMap.

```python
assert TABLE_ORDER.index('Tag') < TABLE_ORDER.index('TagMap')
```

**Обоснование**: TagMap ссылается на Tag, поэтому Tag должен быть создан первым.

---

### `test_usermark_before_blockrange`

**Проверка**: UserMark обрабатывается перед BlockRange.

---

### `test_location_before_note_bookmark`

**Проверка**: Location обрабатывается перед Note и Bookmark.

---

## Тесты PRIMARY_KEYS

### `test_primary_keys_is_dict`

**Проверка**: PRIMARY_KEYS — словарь.

---

### `test_all_tables_have_primary_keys`

**Проверка**: Все таблицы имеют первичные ключи.

```python
for table in ALLOWED_TABLES:
    assert table in PRIMARY_KEYS
```

---

## Тесты copy_unique_records

### Фикстура `temp_dbs`

Создаёт временные БД для тестов:
- Исходная БД с 2 тегами
- Целевая БД с 1 существующим тегом

---

### `test_copy_tags`

**Проверка**: Теги копируются из исходной БД в целевую.

**Ожидаемый результат**: 3 тега (1 существующий + 2 новых).

---

### `test_id_mapping_created`

**Проверка**: Маппинг ID создаётся для новых записей.

**Ожидаемый результат**: `id_mapping['Tag']` содержит 2 записи.

---

### `test_invalid_table_name_raises_error`

**Проверка**: Недопустимое имя таблицы вызывает `ValueError`.

---

## Тесты TagMap Integration

### Фикстура `temp_dbs_with_tagmap`

Создаёт БД с Tag и TagMap.

---

### `test_tagmap_references_correct_tag_id`

**Проверка**: TagMap ссылается на правильный TagId после копирования.

**Алгоритм**:
1. Копировать Tag
2. Копировать TagMap с маппингом ID
3. Проверить, что TagMap.TagId = новый Tag.TagId

---

## Тесты validate_database_schema

### Фикстура `valid_db`

Создаёт БД со всеми таблицами из ALLOWED_TABLES.

---

### `test_valid_schema`

**Проверка**: Валидная схема проходит проверку.

```python
is_valid, missing, message = validate_database_schema(valid_db)
assert is_valid is True
assert len(missing) == 0
```

---

### `test_empty_schema`

**Проверка**: Пустая схема возвращает список недостающих таблиц.

```python
is_valid, missing, message = validate_database_schema(empty_db)
assert is_valid is False
assert all(table in ALLOWED_TABLES for table in missing)
```

---

## Недостатки (TODO)

### 1. Нет тестов для Note с маппингом LocationId/UserMarkId

**Решение (планируется)**: Добавить тест аналогично `test_tagmap_references_correct_tag_id`.

### 2. Нет тестов для BlockRange с маппингом UserMarkId

**Решение (планируется)**: Добавить тест.

### 3. Нет тестов для Bookmark с маппингом LocationId

**Решение (планируется)**: Добавить тест.

### 4. Нет тестов для create_merged_db

**Решение (планируется)**: Добавить интеграционный тест с реальными .jwlibrary файлами.

---

## Запуск тестов

```bash
pytest tests/test_integration.py -v
```

---

## История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-02-26 | Initial spec |
