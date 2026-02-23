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
    ALLOWED_TABLES,
    TABLE_ORDER,
    PRIMARY_KEYS,
    validate_database_schema
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


class TestTableOrder:
    """Тесты для порядка обработки таблиц"""

    def test_table_order_is_list(self):
        """TABLE_ORDER должен быть списком"""
        assert isinstance(TABLE_ORDER, list)

    def test_tag_before_tagmap(self):
        """Tag должен быть перед TagMap"""
        assert TABLE_ORDER.index('Tag') < TABLE_ORDER.index('TagMap')

    def test_usermark_before_blockrange(self):
        """UserMark должен быть перед BlockRange"""
        assert TABLE_ORDER.index('UserMark') < TABLE_ORDER.index('BlockRange')

    def test_location_before_note_bookmark(self):
        """Location должен быть перед Note и Bookmark"""
        loc_idx = TABLE_ORDER.index('Location')
        assert loc_idx < TABLE_ORDER.index('Note')
        assert loc_idx < TABLE_ORDER.index('Bookmark')


class TestPrimaryKeys:
    """Тесты для первичных ключей"""

    def test_primary_keys_is_dict(self):
        """PRIMARY_KEYS должен быть dict"""
        assert isinstance(PRIMARY_KEYS, dict)

    def test_all_tables_have_primary_keys(self):
        """Все таблицы должны иметь первичные ключи"""
        for table in ALLOWED_TABLES:
            assert table in PRIMARY_KEYS, f"Таблица {table} не имеет первичного ключа"


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

    def test_invalid_table_name_raises_error(self, temp_dbs):
        """Недопустимое имя таблицы должно вызывать ошибку"""
        src_db, dst_db = temp_dbs

        src_conn = sqlite3.connect(src_db)
        dst_conn = sqlite3.connect(dst_db)

        with pytest.raises(ValueError, match="Недопустимое имя таблицы"):
            copy_unique_records(src_conn, dst_conn, 'InvalidTable', set(), {})

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


class TestValidateDatabaseSchema:
    """Тесты для валидации схемы БД"""

    @pytest.fixture
    def valid_db(self):
        """Создаёт валидную БД со всеми таблицами"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'valid.db'

        conn = sqlite3.connect(db_path)
        for table in ALLOWED_TABLES:
            conn.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)')
        conn.commit()
        conn.close()

        yield db_path
        db_path.unlink()
        Path(temp_dir).rmdir()

    def test_valid_schema(self, valid_db):
        """Валидная схема должна проходить проверку"""
        is_valid, missing, message = validate_database_schema(valid_db)
        assert is_valid is True
        assert len(missing) == 0

    def test_empty_schema(self):
        """Пустая схема должна возвращать список недостающих таблиц"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'empty.db'

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE some_other_table (id INTEGER)")
        conn.commit()
        conn.close()

        is_valid, missing, message = validate_database_schema(db_path)
        assert is_valid is False
        assert len(missing) > 0
        assert all(table in ALLOWED_TABLES for table in missing)

        db_path.unlink()
        Path(temp_dir).rmdir()
