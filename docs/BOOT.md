# BOOT.md — Инструкции системы

## Назначение
Этот файл содержит инструкции по загрузке контекста для AI-сопроцессора (GPU) в архитектуре Человек-AI.

## Протокол загрузки

При начале каждой сессии AI обязан выполнить следующую последовательность:

### 1. Прочитать этот файл (docs/BOOT.md)
Загрузка инструкций системы и протоколов.

### 2. Прочитать docs/WAL.md
Журнал состояния и принятых решений (Write-Ahead Log).
Определить текущий контекст задачи из WAL.

### 3. Актуализировать контекст проекта
- Проверить наличие спецификаций `spec://`
- Свериться с последними изменениями в коде
- Определить активные задачи из WAL

## Архитектура проекта

```
jwl-backup-merger/
├── jwl_backup_merger.py    # Основной модуль (spec://core/merger)
├── tests/
│   ├── test_hash_generation.py   # Тесты хэшей (spec://core/hash)
│   └── test_integration.py       # Интеграционные тесты (spec://test/integration)
├── docs/
│   ├── BOOT.md              # Этот файл
│   ├── WAL.md               # Журнал решений
│   ├── documentation.md     # Общая документация
│   └── usage.md             # Руководство пользователя
└── specs/                   # Спецификации (создаются)
```

## Компоненты системы

| Компонент | Описание | Spec-ссылка |
|-----------|----------|-------------|
| Hash Generation | Генерация SHA-256 хэшей для дедупликации | `spec://core/hash#generation` |
| Archive Extractor | Извлечение userData.db из .jwlibrary | `spec://core/archive#extract` |
| Schema Validator | Валидация схемы БД | `spec://core/schema#validation` |
| Record Merger | Слияние записей с дедупликацией | `spec://core/merger#records` |
| ID Mapper | Маппинг ID для связанных таблиц | `spec://core/merger#id-mapping` |
| Manifest Creator | Создание manifest.json | `spec://core/manifest` |
| Archive Builder | Создание финального .jwlibrary | `spec://core/archive#build` |

## Поддерживаемые таблицы БД

```
ALLOWED_TABLES = {
    'Note',       # Заметки
    'UserMark',   # Выделения
    'Location',   # Местоположения
    'Tag',        # Теги
    'TagMap',     # Связи тегов
    'Bookmark',   # Закладки
    'BlockRange'  # Диапазоны блоков
}
```

## Порядок обработки таблиц

```
TABLE_ORDER = ['Location', 'UserMark', 'Tag', 'Note', 'TagMap', 'Bookmark', 'BlockRange']
```

Обоснование: сначала родительские таблицы (Location, Tag), потом дочерние (TagMap, BlockRange).

## Конфигурация окружения

- **ОС**: NixOS (использовать `nix-shell` для окружения)
- **Python**: 3.6+
- **Зависимости**: sqlite3, hashlib, json, zipfile (стандартная библиотека)
- **Опционально**: tqdm, pytest, pyinstaller

## Команды разработки

```bash
# Запуск основного скрипта
python jwl_backup_merger.py <input_dir>

# Запуск тестов
pytest

# Сборка бинарника
./build_binary.sh
```

## Протокол взаимодействия

1. **Адресация**: Любое изменение кода должно иметь ссылку `spec://...`
2. **Иерархия истины**: Человек → Specs → Code → Tests
3. **Атомарность**: Одно изменение = Spec + Code + Tests
4. **Память**: Все решения записываются в WAL

---
*Последнее обновление: 2026-02-26*
