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
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


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
        return Path(extract_dir) / 'userData.db', Path(extract_dir) / 'manifest.json'


def copy_unique_records(src_conn, dst_conn, table_name, seen_hashes):
    """Копирование уникальных записей с улучшенной логикой"""
    src_cursor = src_conn.cursor()
    dst_cursor = dst_conn.cursor()
    
    try:
        src_cursor.execute(f"SELECT * FROM {table_name}")
        columns = [description[0] for description in src_cursor.description]
        records = src_cursor.fetchall()
    except sqlite3.OperationalError:
        print(f"  {table_name}: таблица не найдена в исходной базе")
        return seen_hashes
    
    unique_records_added = 0
    
    for record in records:
        record_dict = dict(zip(columns, record))
        record_hash = generate_record_hash(table_name, record_dict)
        
        if record_hash not in seen_hashes:
            seen_hashes.add(record_hash)
            
            # Подготовим SQL для вставки
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join([f'"{col}"' for col in columns])
            sql = f"INSERT OR IGNORE INTO {table_name} ({column_names}) VALUES ({placeholders})"
            
            try:
                dst_cursor.execute(sql, record)
                unique_records_added += 1
            except sqlite3.Error as e:
                # Игнорируем ошибки, связанные с несовместимыми столбцами
                if "has no column" in str(e):
                    continue
                else:
                    print(f"Ошибка при вставке в {table_name}: {e}")
                    print(f"Значения: {record}")
    
    print(f"  {table_name}: добавлено {unique_records_added} уникальных записей")
    
    return seen_hashes


def create_merged_db(archive_paths, output_path):
    """Создание объединённой базы данных"""
    # Используем структуру из первого архива
    first_archive = archive_paths[0]
    with tempfile.TemporaryDirectory() as temp_dir:
        _, _ = extract_from_archive(first_archive, temp_dir)
        first_db_path = Path(temp_dir) / 'userData.db'
        shutil.copyfile(first_db_path, output_path)
    
    # Открываем объединённую базу данных
    merged_conn = sqlite3.connect(output_path)
    
    # Множества для отслеживания уникальных хэшей
    seen_hashes = {
        'Note': set(),
        'UserMark': set(),
        'Location': set(),
        'Tag': set(),
        'TagMap': set(),
        'Bookmark': set(),
        'BlockRange': set()
    }
    
    # Обрабатываем каждый архив
    for i, archive_path in enumerate(archive_paths):
        print(f"Обработка архива {i+1}/{len(archive_paths)}: {Path(archive_path).name}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path, _ = extract_from_archive(archive_path, temp_dir)
            src_conn = sqlite3.connect(db_path)
            
            # Копируем уникальные записи из каждой таблицы
            for table_name in seen_hashes.keys():
                print(f"  Обработка {table_name}...")
                seen_hashes[table_name] = copy_unique_records(
                    src_conn, merged_conn, table_name, seen_hashes[table_name]
                )
            
            src_conn.close()
    
    # Обновляем LastModified
    try:
        merged_conn.execute("DELETE FROM LastModified")
        merged_conn.execute("INSERT INTO LastModified VALUES (?)", (datetime.now().isoformat().split('.')[0] + "+00:00",))
    except sqlite3.OperationalError:
        # Если таблица LastModified не существует, пропускаем
        pass
    
    merged_conn.commit()
    merged_conn.close()
    
    print(f"Объединённая база данных создана: {output_path}")


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
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not input_dir.exists():
        print(f"Ошибка: директория {input_dir} не существует")
        sys.exit(1)
    
    # Находим все архивы
    archive_files = list(input_dir.glob('*.jwlibrary'))
    if not archive_files:
        print(f"Ошибка: не найдено архивов .jwlibrary в директории {input_dir}")
        sys.exit(1)
    
    print(f"Найдено {len(archive_files)} архивов для объединения")
    
    # Создаём временную директорию для работы
    with tempfile.TemporaryDirectory() as work_dir:
        work_path = Path(work_dir)
        output_db_path = work_path / 'merged_userData.db'
        
        # Создаём объединённую базу данных
        create_merged_db(archive_files, output_db_path)
        
        # Подсчитываем результаты
        conn = sqlite3.connect(output_db_path)
        cursor = conn.cursor()
        
        tables = ['Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange']
        print("\nРезультаты объединения:")
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} записей")
            except sqlite3.OperationalError:
                print(f"  {table}: ошибка (таблица не существует)")
        
        conn.close()
        
        # Создаём манифест
        print("\nСоздание манифеста...")
        manifest_data = create_manifest_from_archives(archive_files, output_db_path)
        
        # Создаём финальный архив
        output_archive_path = output_dir / args.output
        create_backup_archive(output_db_path, manifest_data, output_archive_path)
        
        print(f"\nОбъединённый бэкап успешно создан: {output_archive_path}")
        print("Процесс завершён успешно!")


if __name__ == "__main__":
    main()