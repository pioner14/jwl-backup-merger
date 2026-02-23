"""
Интеграционные тесты для слияния баз данных
"""
import pytest
import sqlite3
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from jwl_backup_merger import (
    copy_unique_records, 
    create_merged_db,
    extract_from_archive,
    ALLOWED_TABLES
)


class TestAllowedTables:
    """Тесты для whitelist таблиц"""

    def test_allowed_tables_contains_all_tables(self):
        """Whitelist должен содержать все поддерживаемые таблицы"""
        required_tables = {'Note', 'UserMark', 'Location', 'Tag', 'TagMap', 'Bookmark', 'BlockRange'}
        assert required_tables.issubset(ALLOWED_TABLES)

    def test_allowed_tables_is_frozenset(self):
        """ALLOWED_TABLES должен быть frozenset для безопасности"""
        assert isinstance(ALLOWED_TABLES, frozenset)


class TestCopyUniqueRecords:
    """Тесты для функции copy_unique_records"""

    @pytest.fixture
    def temp_dbs(self):
        """Создаёт временные БД для тестов"""
        temp_dir = tempfile.mkdtemp()
        src_db = Path(temp_dir) / 'source.db'
        dst_db = Path(temp_dir) / 'dest.db'
        
        # Создаём исходную БД
        src_conn = sqlite3.connect(src_db)
        src_conn.execute("""
            CREATE TABLE Tag (
                TagId INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Type INTEGER NOT NULL
            )
        """)
        src_conn.execute("INSERT INTO Tag (Name, Type) VALUES ('Test1', 1)")
        src_conn.execute("INSERT INTO Tag (Name, Type) VALUES ('Test2', 2)")
        src_conn.commit()
        src_conn.close()
        
        # Создаём целевую БД с такой же структурой
        dst_conn = sqlite3.connect(dst_db)
        dst_conn.execute("""
            CREATE TABLE Tag (
                TagId INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Type INTEGER NOT NULL
            )
        """)
        dst_conn.execute("INSERT INTO Tag (Name, Type) VALUES ('Existing', 0)")
        dst_conn.commit()
        dst_conn.close()
        
        yield src_db, dst_db
        
        # Cleanup
        shutil.rmtree(temp_dir)

    def test_copy_tags(self, temp_dbs):
        """Копирование тегов из одной БД в другую"""
        src_db, dst_db = temp_dbs
        
        src_conn = sqlite3.connect(src_db)
        dst_conn = sqlite3.connect(dst_db)
        
        seen_hashes = set()
        id_mapping = {}
        
        # Копируем теги
        copy_unique_records(src_conn, dst_conn, 'Tag', seen_hashes, id_mapping)
        
        # Проверяем результат
        cursor = dst_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Tag")
        count = cursor.fetchone()[0]
        
        # Должно быть 3 тега (1 существующий + 2 новых)
        assert count == 3
        
        src_conn.close()
        dst_conn.close()

    def test_id_mapping_created(self, temp_dbs):
        """Проверка создания маппинга ID"""
        src_db, dst_db = temp_dbs
        
        src_conn = sqlite3.connect(src_db)
        dst_conn = sqlite3.connect(dst_db)
        
        seen_hashes = set()
        id_mapping = {}
        
        copy_unique_records(src_conn, dst_conn, 'Tag', seen_hashes, id_mapping)
        
        # Маппинг должен быть создан
        assert 'Tag' in id_mapping
        assert len(id_mapping['Tag']) == 2  # 2 новых тега
        
        src_conn.close()
        dst_conn.close()


class TestTagMapIntegration:
    """Интеграционные тесты для Tag → TagMap"""

    @pytest.fixture
    def temp_dbs_with_tagmap(self):
        """Создаёт БД с Tag и TagMap"""
        temp_dir = tempfile.mkdtemp()
        src_db = Path(temp_dir) / 'source.db'
        dst_db = Path(temp_dir) / 'dest.db'
        
        # Создаём исходную БД
        src_conn = sqlite3.connect(src_db)
        src_conn.execute("""
            CREATE TABLE Tag (
                TagId INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Type INTEGER NOT NULL
            )
        """)
        src_conn.execute("""
            CREATE TABLE TagMap (
                TagMapId INTEGER PRIMARY KEY AUTOINCREMENT,
                Type INTEGER NOT NULL,
                TypeId INTEGER NOT NULL,
                TagId INTEGER NOT NULL,
                Position INTEGER NOT NULL
            )
        """)
        src_conn.execute("INSERT INTO Tag (Name, Type) VALUES ('MyTag', 1)")
        src_conn.execute("INSERT INTO TagMap (Type, TypeId, TagId, Position) VALUES (1, 100, 1, 0)")
        src_conn.commit()
        src_conn.close()
        
        # Создаём целевую БД
        dst_conn = sqlite3.connect(dst_db)
        dst_conn.execute("""
            CREATE TABLE Tag (
                TagId INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Type INTEGER NOT NULL
            )
        """)
        dst_conn.execute("""
            CREATE TABLE TagMap (
                TagMapId INTEGER PRIMARY KEY AUTOINCREMENT,
                Type INTEGER NOT NULL,
                TypeId INTEGER NOT NULL,
                TagId INTEGER NOT NULL,
                Position INTEGER NOT NULL
            )
        """)
        dst_conn.commit()
        dst_conn.close()
        
        yield src_db, dst_db
        shutil.rmtree(temp_dir)

    def test_tagmap_references_correct_tag_id(self, temp_dbs_with_tagmap):
        """TagMap должен ссылаться на правильный TagId после копирования"""
        src_db, dst_db = temp_dbs_with_tagmap
        
        src_conn = sqlite3.connect(src_db)
        dst_conn = sqlite3.connect(dst_db)
        
        seen_hashes = {'Tag': set(), 'TagMap': set()}
        id_mapping = {}
        
        # Сначала копируем Tag
        copy_unique_records(src_conn, dst_conn, 'Tag', seen_hashes['Tag'], id_mapping)
        
        # Затем копируем TagMap (должен использовать маппинг)
        copy_unique_records(src_conn, dst_conn, 'TagMap', seen_hashes['TagMap'], id_mapping)
        
        # Проверяем что TagId в TagMap правильный
        cursor = dst_conn.cursor()
        
        # Получаем новый TagId для тега 'MyTag'
        cursor.execute("SELECT TagId FROM Tag WHERE Name = 'MyTag'")
        row = cursor.fetchone()
        assert row is not None
        new_tag_id = row[0]
        
        # Проверяем что TagMap ссылается на этот TagId
        cursor.execute("SELECT TagId FROM TagMap")
        tagmap_row = cursor.fetchone()
        assert tagmap_row is not None
        assert tagmap_row[0] == new_tag_id
        
        src_conn.close()
        dst_conn.close()
