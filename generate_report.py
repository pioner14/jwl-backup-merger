#!/usr/bin/env python3
"""Генерация полного отчёта об объединении JW Library Backup"""

import zipfile
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("ПОЛНЫЙ ОТЧЁТ ОБ ОБЪЕДИНЕНИИ JW LIBRARY BACKUP")
print("=" * 80)
print(f"Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Исходные архивы
input_dir = Path('UserdataBackup_2026-02-22_DESKTOP-PDFDOOU/')
archive_files = sorted(input_dir.glob('*.jwlibrary'))

print("ИСХОДНЫЕ АРХИВЫ:")
print("-" * 80)

stats = {}
for archive in archive_files:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive, 'r') as z:
            z.extractall(tmp)
            db_path = Path(tmp) / 'userData.db'
            if not db_path.exists():
                db_path = Path(tmp) / 'user_data.db'
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            data = {'name': archive.name}
            
            # Количество записей
            for table in ['Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange']:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                data[table] = cursor.fetchone()[0]
            
            # Уникальные Guid для UserMark
            cursor.execute('SELECT COUNT(DISTINCT UserMarkGuid) FROM UserMark WHERE UserMarkGuid IS NOT NULL')
            data['UserMarkGuid_unique'] = cursor.fetchone()[0]
            
            # Уникальные Guid для Note
            cursor.execute('SELECT COUNT(DISTINCT Guid) FROM Note WHERE Guid IS NOT NULL')
            data['NoteGuid_unique'] = cursor.fetchone()[0]
            
            stats[archive.name] = data
            conn.close()

# Печать статистики
print(f"{'Архив':<45} {'Note':>8} {'UserMark':>10} {'Location':>9} {'Tag':>6} {'TagMap':>7} {'Bookmark':>9} {'BlockR':>8}")
print("-" * 80)

for name, data in stats.items():
    print(f"{name[:44]:<45} {data['Note']:>8} {data['UserMark']:>10} {data['Location']:>9} {data['Tag']:>6} {data['TagMap']:>7} {data['Bookmark']:>9} {data['BlockRange']:>8}")

print("-" * 80)

# Суммы
totals = {k: sum(d[k] for d in stats.values()) for k in ['Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange']}
print(f"{'ВСЕГО (сумма):':<45} {totals['Note']:>8} {totals['UserMark']:>10} {totals['Location']:>9} {totals['Tag']:>6} {totals['TagMap']:>7} {totals['Bookmark']:>9} {totals['BlockRange']:>8}")
print()

# Результат слияния
print("РЕЗУЛЬТАТ СЛИЯНИЯ:")
print("-" * 80)

with tempfile.TemporaryDirectory() as tmp:
    with zipfile.ZipFile('combined_backup_new.jwlibrary', 'r') as z:
        z.extractall(tmp)
        db_path = Path(tmp) / 'userData.db'
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        result = {}
        for table in ['Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange']:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            result[table] = cursor.fetchone()[0]
        
        # Уникальные Guid
        cursor.execute('SELECT COUNT(DISTINCT UserMarkGuid) FROM UserMark WHERE UserMarkGuid IS NOT NULL')
        result['UserMarkGuid_unique'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT Guid) FROM Note WHERE Guid IS NOT NULL')
        result['NoteGuid_unique'] = cursor.fetchone()[0]
        
        conn.close()

print(f"{'combined_backup_new.jwlibrary':<45} {result['Note']:>8} {result['UserMark']:>10} {result['Location']:>9} {result['Tag']:>6} {result['TagMap']:>7} {result['Bookmark']:>9} {result['BlockRange']:>8}")
print()

# Дедупликация
print("ДЕДУПЛИКАЦИЯ (сколько удалено дубликатов):")
print("-" * 80)
for k in ['Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange']:
    removed = totals[k] - result[k]
    percent = (removed / totals[k] * 100) if totals[k] > 0 else 0
    print(f"{k:<15} {removed:>8} ({percent:>5.1f}%)")

print()
print("УНИКАЛЬНЫЕ ЗАПИСИ ПО АРХИВАМ (UserMark по Guid):")
print("-" * 80)

# Проверка уникальности по Guid для UserMark
all_guids = {}
for archive in archive_files:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive, 'r') as z:
            z.extractall(tmp)
            db_path = Path(tmp) / 'userData.db'
            if not db_path.exists():
                db_path = Path(tmp) / 'user_data.db'
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT UserMarkGuid FROM UserMark WHERE UserMarkGuid IS NOT NULL')
            all_guids[archive.name[:30]] = {r[0] for r in cursor.fetchall()}
            conn.close()

for name, guids in all_guids.items():
    other_guids = set()
    for other_name, other_guids_set in all_guids.items():
        if other_name != name:
            other_guids |= other_guids_set
    
    unique = guids - other_guids
    unique_percent = len(unique) / len(guids) * 100 if guids else 0
    print(f"{name:<35} {len(unique):>8} уникальных из {len(guids):>8} ({unique_percent:>5.1f}%)")

print()
print("=" * 80)
print("ОТЧЁТ ЗАВЕРШЁН")
print("=" * 80)
