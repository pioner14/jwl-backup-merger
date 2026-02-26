# spec://core/hash

## Генерация хэшей для дедупликации записей

**Версия**: 1.0  
**Статус**: stable  
**Модуль**: `jwl_backup_merger.py::generate_record_hash()`

---

## Назначение

Функция `generate_record_hash()` создаёт уникальный SHA-256 хэш для каждой записи БД JW Library с целью обнаружения дубликатов при слиянии бэкапов.

---

## Контракт

```python
def generate_record_hash(table_name: str, record_data: Dict[str, Any]) -> str:
    """
    Создаёт уникальную хэш-сумму для записи базы данных JW Library.
    
    Args:
        table_name: Имя таблицы (Note, UserMark, Location, Tag, Bookmark, BlockRange, TagMap)
        record_data: Словарь с данными записи (ключ = имя колонки, значение = значение)
    
    Returns:
        HEX-строка SHA-256 хэша (64 символа)
    """
```

---

## Спецификация по таблицам

### Tag

**Поля для хэша**: `Name`, `Type`

```
hash = SHA256("{Name}|{Type}")
```

**Обоснование**: Тег уникально определяется именем и типом.

---

### UserMark

**Поля для хэша**:
- Если `UserMarkGuid` существует: `UserMarkGuid`
- Иначе: `LocationId`, `ColorIndex`, `StyleIndex`, `Version`

```
if UserMarkGuid:
    hash = SHA256("{UserMarkGuid}")
else:
    hash = SHA256("{LocationId}|{ColorIndex}|{StyleIndex}|{Version}")
```

**Обоснование**: GUID — уникальный идентификатор выделения. Если GUID отсутствует (старые версии), используется комбинация полей.

---

### Location

**Поля для хэша**: `BookNumber`, `ChapterNumber`, `DocumentId`, `KeySymbol`, `IssueTagNumber`, `MepsLanguage`, `Title`

```
hash = SHA256("{BookNumber}|{ChapterNumber}|{DocumentId}|{KeySymbol}|{IssueTagNumber}|{MepsLanguage}|{Title}")
```

**Обоснование**: Местоположение уникально определяется комбинацией книги, главы, публикации и языка.

---

### Note

**Поля для хэша**: `Content`, `Title`, `LocationId`, `UserMarkId`, `BlockType`, `BlockIdentifier`, `Guid`

```
hash = SHA256("{Content}|{Title}|{LocationId}|{UserMarkId}|{BlockType}|{BlockIdentifier}|{Guid}")
```

**Обоснование**: Заметка уникальна по содержимому + метаданным. `UserMarkId` может быть None.

---

### Bookmark

**Поля для хэша**: `LocationId`, `Slot`, `Title`, `Snippet`

```
hash = SHA256("{LocationId}|{Slot}|{Title}|{Snippet}")
```

**Обоснование**: Закладка уникальна по местоположению + слоту + названию.

---

### BlockRange

**Поля для хэша**: `BlockType`, `Identifier`, `StartToken`, `EndToken`, `UserMarkId`

```
hash = SHA256("{BlockType}|{Identifier}|{StartToken}|{EndToken}|{UserMarkId}")
```

**Обоснование**: Диапазон блоков уникален по токенам и типу блока.

---

### TagMap

**Поля для хэша**: `Type`, `TypeId`, `TagId`, `Position`

```
hash = SHA256("{Type}|{TypeId}|{TagId}|{Position}")
```

**Обоснование**: Связь тега с объектом уникальна по комбинации ID и позиции.

---

## Обработка None-значений

```python
value = record_data.get(field) or ''  # Для строк
value = record_data.get(field) or 0   # Для чисел
```

**Обоснование**: `None` должен быть эквивалентен пустому значению для целей дедупликации.

---

## Гарантии

1. **Детерминизм**: Одинаковые входные данные → одинаковый хэш
2. **Уникальность**: Разные входные данные → разные хэши (с вероятностью 1 - 2^-256)
3. **Стабильность**: Формат хэша не меняется между версиями

---

## Тесты

См. `spec://test/hash-generation`

---

## История изменений

| Версия | Дата | Изменение |
|--------|------|-----------|
| 1.0 | 2026-02-26 | Initial spec |
