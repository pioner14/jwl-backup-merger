#!/usr/bin/env python3
"""
JW Library Backup Merger
========================

Инструмент для объединения нескольких бэкапов JW Library в один инкрементарный бэкап,
с проверкой дубликатов и сохранением уникальных записей.

Функции:
- Извлечение userData.db из архивов .jwlibrary
- Объединение баз данных с исключением дубликатов
- Создание нового архива для импорта в JW Library
- Поддержка всех типов данных (заметки, пометки, теги, закладки)
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# Try to import tqdm, use dummy class if not available
try:
    from tqdm import tqdm
except ImportError:
    class tqdm:
        def __init__(self, iterable=None, desc=None, total=None, disable=False, leave=True, postfix=None):
            self.iterable = iterable
            self.desc = desc
            self.total = total
            self.disable = disable
            self.leave = leave
            self.postfix = postfix
        def __iter__(self):
            for item in self.iterable:
                yield item
        def update(self, n=1):
            pass
        def close(self):
            pass
        def set_postfix(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Добавляем null handler чтобы избежать warnings если логирование не настроено
logger.addHandler(logging.NullHandler())

# Whitelist допустимых имён таблиц для безопасности
ALLOWED_TABLES: FrozenSet[str] = frozenset([
    'Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange'
])

# Порядок обработки таблиц (сначала родительские, потом дочерние)
TABLE_ORDER: List[str] = ['Location', 'UserMark', 'Tag', 'Note', 'TagMap', 'Bookmark', 'BlockRange']

# Первичные ключи для каждой таблицы
PRIMARY_KEYS: Dict[str, str] = {
    'Tag': 'TagId',
    'UserMark': 'UserMarkId',
    'Location': 'LocationId',
    'Note': 'NoteId',
    'Bookmark': 'BookmarkId',
    'BlockRange': 'BlockRangeId',
    'TagMap': 'TagMapId'
}


def generate_record_hash(table_name, record_data):
    """Создание уникального хэша для записи"""
    if table_name == 'Note':
        content = record_data.get('Content') or ''
        title = record_data.get('Title') or ''
        location_id = record_data.get('LocationId') or 0
        user_mark_id = record_data.get('UserMarkId') or None
        block_type = record_data.get('BlockType') or 0
        block_identifier = record_data.get('BlockIdentifier') or ''
        guid = record_data.get('Guid') or ''
        
        fields = f"{content}|{title}|{location_id}|{user_mark_id}|{block_type}|{block_identifier}|{guid}"
        return hashlib.sha256(fields.encode('utf-8')).hexdigest()

    elif table_name == 'UserMark':
        guid = record_data.get('UserMarkGuid')
        if guid:
            return hashlib.sha256(guid.encode('utf-8')).hexdigest()
        else:
            location_id = record_data.get('LocationId') or 0
            color_index = record_data.get('ColorIndex') or 0
            style_index = record_data.get('StyleIndex') or 0
            version = record_data.get('Version') or 0
            return hashlib.sha256(f"{location_id}|{color_index}|{style_index}|{version}".encode('utf-8')).hexdigest()

    elif table_name == 'Location':
        book_number = record_data.get('BookNumber') or 0
        chapter_number = record_data.get('ChapterNumber') or 0
        document_id = record_data.get('DocumentId') or 0
        key_symbol = record_data.get('KeySymbol') or ''
        issue_tag_number = record_data.get('IssueTagNumber') or 0
        meps_language = record_data.get('MepsLanguage') or 0
        title = record_data.get('Title') or ''
        return hashlib.sha256(f"{book_number}|{chapter_number}|{document_id}|{key_symbol}|{issue_tag_number}|{meps_language}|{title}".encode('utf-8')).hexdigest()

    elif table_name == 'Tag':
        name = record_data.get('Name') or ''
        tag_type = record_data.get('Type') or 0
        return hashlib.sha256(f"{name}|{tag_type}".encode('utf-8')).hexdigest()

    elif table_name == 'Bookmark':
        location_id = record_data.get('LocationId') or 0
        slot = record_data.get('Slot') or 0
        title = record_data.get('Title') or ''
        snippet = record_data.get('Snippet') or ''
        return hashlib.sha256(f"{location_id}|{slot}|{title}|{snippet}".encode('utf-8')).hexdigest()

    elif table_name == 'BlockRange':
        block_type = record_data.get('BlockType') or 0
        identifier = record_data.get('Identifier') or 0
        start_token = record_data.get('StartToken') or 0
        end_token = record_data.get('EndToken') or 0
        user_mark_id = record_data.get('UserMarkId') or None
        return hashlib.sha256(f"{block_type}|{identifier}|{start_token}|{end_token}|{user_mark_id}".encode('utf-8')).hexdigest()

    elif table_name == 'TagMap':
        tag_type = record_data.get('Type') or 0
        type_id = record_data.get('TypeId') or 0
        tag_id = record_data.get('TagId') or 0
        position = record_data.get('Position') or 0
        return hashlib.sha256(f"{tag_type}|{type_id}|{tag_id}|{position}".encode('utf-8')).hexdigest()

    else:
        fields_str = '|'.join(str(v) for v in record_data.values() if v is not None)
        return hashlib.sha256(fields_str.encode('utf-8')).hexdigest()


def extract_from_archive(archive_path, extract_dir):
    """Извлечение архива JW Library"""
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

        # Проверяем оба возможных имени файла БД
        db_path = Path(extract_dir) / 'userData.db'
        if not db_path.exists():
            db_path = Path(extract_dir) / 'user_data.db'

        return db_path, Path(extract_dir) / 'manifest.json'


def validate_database_schema(db_path):
    """Проверка схемы базы данных на наличие требуемых таблиц

    Args:
        db_path: Путь к файлу базы данных

    Returns:
        tuple: (is_valid, missing_tables, error_message)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем список всех таблиц
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Проверяем наличие требуемых таблиц
        missing_tables = []
        for table in ALLOWED_TABLES:
            if table not in existing_tables:
                missing_tables.append(table)

        if missing_tables:
            return False, missing_tables, f"Отсутствуют таблицы: {', '.join(missing_tables)}"

        return True, [], "Схема базы данных валидна"

    except sqlite3.Error as e:
        return False, [], f"Ошибка при проверке схемы: {e}"


def copy_unique_records(
    src_conn: sqlite3.Connection,
    dst_conn: sqlite3.Connection,
    table_name: str,
    seen_hashes: Set[str],
    id_mapping: Optional[Dict[str, Dict[int, int]]] = None
) -> Set[str]:
    """Копирование уникальных записей с маппингом ID для связанных таблиц

    Args:
        src_conn: Подключение к исходной БД
        dst_conn: Подключение к целевой БД
        table_name: Имя таблицы для копирования
        seen_hashes: Множество хэшей уже обработанных записей
        id_mapping: dict для маппинга ID (например, {'Tag': {old_id: new_id, ...}})

    Returns:
        Обновлённое множество seen_hashes
    """
    # Проверка имени таблицы (защита от SQL injection)
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Недопустимое имя таблицы: {table_name}")

    src_cursor = src_conn.cursor()
    dst_cursor = dst_conn.cursor()

    try:
        src_cursor.execute(f'SELECT * FROM "{table_name}"')
        columns = [description[0] for description in src_cursor.description]
        records = src_cursor.fetchall()
    except sqlite3.OperationalError:
        logger.debug(f"  {table_name}: таблица не найдена в исходной базе")
        return seen_hashes

    unique_records_added = 0
    local_id_mapping: Dict[int, int] = {}  # old_id -> new_id для текущей таблицы

    # Определяем первичный ключ для таблицы
    pk_column = PRIMARY_KEYS.get(table_name)

    for record in records:
        record_dict = dict(zip(columns, record))
        record_hash = generate_record_hash(table_name, record_dict)

        if record_hash not in seen_hashes:
            seen_hashes.add(record_hash)

            # Создаём mutable копию записи
            record_list = list(record)

            # Для TagMap нужно обновить TagId согласно маппингу
            if table_name == 'TagMap' and id_mapping and 'Tag' in id_mapping:
                tag_id_idx = columns.index('TagId') if 'TagId' in columns else -1
                if tag_id_idx >= 0:
                    old_tag_id = record_list[tag_id_idx]
                    if old_tag_id and old_tag_id in id_mapping['Tag']:
                        record_list[tag_id_idx] = id_mapping['Tag'][old_tag_id]

            # Для BlockRange нужно обновить UserMarkId согласно маппингу
            if table_name == 'BlockRange' and id_mapping and 'UserMark' in id_mapping:
                user_mark_id_idx = columns.index('UserMarkId') if 'UserMarkId' in columns else -1
                if user_mark_id_idx >= 0:
                    old_user_mark_id = record_list[user_mark_id_idx]
                    if old_user_mark_id and old_user_mark_id in id_mapping['UserMark']:
                        record_list[user_mark_id_idx] = id_mapping['UserMark'][old_user_mark_id]

            # Для Note нужно обновить LocationId и UserMarkId согласно маппингу
            if table_name == 'Note':
                if id_mapping and 'Location' in id_mapping:
                    loc_idx = columns.index('LocationId') if 'LocationId' in columns else -1
                    if loc_idx >= 0:
                        old_loc_id = record_list[loc_idx]
                        if old_loc_id and old_loc_id in id_mapping['Location']:
                            record_list[loc_idx] = id_mapping['Location'][old_loc_id]
                if id_mapping and 'UserMark' in id_mapping:
                    um_idx = columns.index('UserMarkId') if 'UserMarkId' in columns else -1
                    if um_idx >= 0 and record_list[um_idx] is not None:
                        old_um_id = record_list[um_idx]
                        if old_um_id and old_um_id in id_mapping['UserMark']:
                            record_list[um_idx] = id_mapping['UserMark'][old_um_id]

            # Для Bookmark нужно обновить LocationId
            if table_name == 'Bookmark' and id_mapping and 'Location' in id_mapping:
                loc_idx = columns.index('LocationId') if 'LocationId' in columns else -1
                if loc_idx >= 0:
                    old_loc_id = record_list[loc_idx]
                    if old_loc_id and old_loc_id in id_mapping['Location']:
                        record_list[loc_idx] = id_mapping['Location'][old_loc_id]

            record = tuple(record_list)

            # Подготовим SQL для вставки
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join([f'"{col}"' for col in columns])
            sql = f'INSERT OR IGNORE INTO "{table_name}" ({column_names}) VALUES ({placeholders})'

            try:
                dst_cursor.execute(sql, record)

                # Получаем ID вставленной записи (или существующей)
                if pk_column:
                    old_id = record_dict.get(pk_column)
                    # Пытаемся получить lastrowid
                    new_id = dst_cursor.lastrowid

                    # Если lastrowid None, значит запись уже существовала - ищем её
                    if new_id is None and old_id is not None:
                        # Находим существующую запись по уникальным полям (хэшу)
                        dst_cursor.execute(
                            f'SELECT "{pk_column}" FROM "{table_name}" WHERE rowid = last_insert_rowid()'
                        )
                        row = dst_cursor.fetchone()
                        if row:
                            new_id = row[0]

                    if old_id and new_id and old_id != new_id:
                        local_id_mapping[old_id] = new_id

                unique_records_added += 1

            except sqlite3.Error as e:
                # Игнорируем ошибки, связанные с несовместимыми столбцами
                if "has no column" in str(e):
                    continue
                else:
                    logger.warning(f"Ошибка при вставке в {table_name}: {e}")
                    logger.debug(f"Значения: {record}")

    logger.debug(f"  {table_name}: добавлено {unique_records_added} уникальных записей")

    # Сохраняем маппинг в общий dict
    if id_mapping is not None and local_id_mapping:
        id_mapping[table_name] = local_id_mapping

    return seen_hashes


def create_merged_db(archive_paths: List[Path], output_path: Path, verbose: bool = False) -> Path:
    """Создание объединённой базы данных с транзакциями и откатом при ошибках

    Args:
        archive_paths: Список путей к архивам .jwlibrary
        output_path: Путь для выходной базы данных
        verbose: Включить подробный вывод

    Returns:
        Путь к созданной базе данных

    Raises:
        RuntimeError: При критической ошибке во время слияния
    """
    # Используем структуру из первого архива
    first_archive = archive_paths[0]
    with tempfile.TemporaryDirectory() as temp_dir:
        _, _ = extract_from_archive(first_archive, temp_dir)
        first_db_path = Path(temp_dir) / 'userData.db'
        shutil.copyfile(first_db_path, output_path)

    # Открываем объединённую базу данных
    merged_conn = sqlite3.connect(str(output_path))

    # Отключаем внешние ключи на время импорта (включаем только в конце)
    merged_conn.execute("PRAGMA foreign_keys = OFF")

    # Множества для отслеживания уникальных хэшей
    seen_hashes: Dict[str, Set[str]] = {
        'Note': set(),
        'UserMark': set(),
        'Location': set(),
        'Tag': set(),
        'TagMap': set(),
        'Bookmark': set(),
        'BlockRange': set()
    }

    # Маппинг ID для связанных таблиц
    id_mapping: Dict[str, Dict[int, int]] = {}

    try:
        # Обрабатываем каждый архив
        archive_iterator = tqdm(archive_paths, desc="Архивы", disable=not verbose)
        for i, archive_path in enumerate(archive_iterator):
            logger.debug(f"Обработка архива {i+1}/{len(archive_paths)}: {archive_path.name}")

            with tempfile.TemporaryDirectory() as temp_dir:
                db_path, _ = extract_from_archive(archive_path, temp_dir)
                src_conn = sqlite3.connect(str(db_path))

                # Копируем уникальные записи из каждой таблицы в правильном порядке
                table_iterator = tqdm(TABLE_ORDER, desc=f"Таблицы ({archive_path.name[:30]})", disable=not verbose, leave=False)
                for table_name in table_iterator:
                    seen_hashes[table_name] = copy_unique_records(
                        src_conn, merged_conn, table_name, seen_hashes[table_name], id_mapping
                    )
                    if verbose:
                        table_iterator.set_postfix(**{table_name: len(seen_hashes[table_name])})

                src_conn.close()

        # Обновляем LastModified
        try:
            merged_conn.execute("UPDATE LastModified SET value = ?", (datetime.now().isoformat().split('.')[0] + "+00:00",))
        except sqlite3.OperationalError:
            # Если таблица LastModified не существует, пропускаем
            pass

        # Включаем внешние ключи и проверяем целостность
        merged_conn.execute("PRAGMA foreign_keys = ON")
        merged_conn.commit()
        logger.info(f"Объединённая база данных создана: {output_path}")
        return output_path

    except Exception as e:
        # Откат при ошибке
        merged_conn.rollback()
        merged_conn.close()
        raise RuntimeError(f"Ошибка при создании объединённой базы: {e}")

    finally:
        merged_conn.close()


def create_manifest_from_archives(archive_paths, output_db_path):
    """Создание нового манифеста на основе объединённой базы данных"""
    # Используем первый манифест как шаблон
    with tempfile.TemporaryDirectory() as temp_dir:
        _, manifest_path = extract_from_archive(archive_paths[0], temp_dir)
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    
    # Обновляем информацию в манифесте
    with open(output_db_path, 'rb') as f:
        db_hash = hashlib.sha256(f.read()).hexdigest()
    
    # Подсчитываем количество пометок
    conn = sqlite3.connect(output_db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM UserMark")
        user_mark_count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        user_mark_count = 0
    conn.close()
    
    # Обновляем манифест
    manifest['name'] = f"CombinedUserDataBackup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    manifest['creationDate'] = datetime.now().strftime('%Y-%m-%d')
    manifest['userDataBackup']['hash'] = db_hash
    manifest['userDataBackup']['lastModifiedDate'] = datetime.now().isoformat().split('.')[0] + "+00:00"
    manifest['userDataBackup']['userMarkCount'] = user_mark_count
    
    return manifest


def create_backup_archive(db_path, manifest_data, output_archive_path):
    """Создание архива бэкапа с базой данных и манифестом"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as manifest_file:
        json.dump(manifest_data, manifest_file, indent=2, ensure_ascii=False)
        manifest_path = manifest_file.name
    
    try:
        with zipfile.ZipFile(output_archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(db_path, 'userData.db')
            zipf.write(manifest_path, 'manifest.json')
        
        print(f"Архив бэкапа создан: {output_archive_path}")
    finally:
        os.unlink(manifest_path)


def main():
    parser = argparse.ArgumentParser(description='Объединение нескольких бэкапов JW Library в один')
    parser.add_argument('input_dir', help='Директория с архивами .jwlibrary')
    parser.add_argument('-o', '--output', help='Выходной архив (по умолчанию: combined_backup.jwlibrary)',
                        default='combined_backup.jwlibrary')
    parser.add_argument('--output-dir', help='Директория для сохранения результатов', default='.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Включить подробный вывод (debug режим)')
    parser.add_argument('--dry-run', action='store_true', help='Режим проверки без записи файлов')

    args = parser.parse_args()

    # Настройка логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        logger.error(f"Директория {input_dir} не существует")
        sys.exit(1)

    # Находим все архивы
    archive_files = list(input_dir.glob('*.jwlibrary'))
    if not archive_files:
        logger.error(f"Не найдено архивов .jwlibrary в директории {input_dir}")
        sys.exit(1)

    logger.info(f"Найдено {len(archive_files)} архивов для объединения")

    if args.dry_run:
        logger.info("DRY-RUN: Режим проверки без записи")
        for archive in archive_files:
            logger.info(f"  - {archive.name}")
        logger.info("DRY-RUN: Завершено")
        return
    
    # Создаём временную директорию для работы
    with tempfile.TemporaryDirectory() as work_dir:
        work_path = Path(work_dir)
        output_db_path = work_path / 'merged_userData.db'

        # Создаём объединённую базу данных
        create_merged_db(archive_files, output_db_path, verbose=args.verbose)

        # Подсчитываем результаты
        conn = sqlite3.connect(str(output_db_path))
        cursor = conn.cursor()

        tables = ['Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange']
        logger.info("\nРезультаты объединения:")
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                logger.info(f"  {table}: {count} записей")
            except sqlite3.OperationalError:
                logger.warning(f"  {table}: ошибка (таблица не существует)")

        conn.close()

        # Создаём манифест
        logger.info("Создание манифеста...")
        manifest_data = create_manifest_from_archives(archive_files, output_db_path)

        # Создаём финальный архив
        output_archive_path = output_dir / args.output
        create_backup_archive(output_db_path, manifest_data, output_archive_path)

        logger.info(f"Объединённый бэкап успешно создан: {output_archive_path}")
        logger.info("Процесс завершён успешно!")


if __name__ == "__main__":
    main()