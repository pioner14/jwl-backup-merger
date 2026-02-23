"""
Тесты для валидации схемы БД
"""
import pytest
import sqlite3
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from jwl_backup_merger import validate_database_schema, ALLOWED_TABLES


class TestValidateDatabaseSchema:
    """Тесты для функции validate_database_schema"""

    @pytest.fixture
    def valid_db(self):
        """Создаёт валидную БД со всеми таблицами"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'valid.db'
        
        conn = sqlite3.connect(db_path)
        for table in ALLOWED_TABLES:
            if table == 'Tag':
                conn.execute(f"""
                    CREATE TABLE {table} (
                        TagId INTEGER PRIMARY KEY,
                        Name TEXT,
                        Type INTEGER
                    )
                """)
            elif table == 'UserMark':
                conn.execute(f"""
                    CREATE TABLE {table} (
                        UserMarkId INTEGER PRIMARY KEY,
                        LocationId INTEGER,
                        ColorIndex INTEGER
                    )
                """)
            elif table == 'Location':
                conn.execute(f"""
                    CREATE TABLE {table} (
                        LocationId INTEGER PRIMARY KEY,
                        BookNumber INTEGER
                    )
                """)
            elif table == 'Note':
                conn.execute(f"""
                    CREATE TABLE {table} (
                        NoteId INTEGER PRIMARY KEY,
                        Content TEXT,
                        LocationId INTEGER
                    )
                """)
            elif table == 'TagMap':
                conn.execute(f"""
                    CREATE TABLE {table} (
                        TagMapId INTEGER PRIMARY KEY,
                        TagId INTEGER,
                        TypeId INTEGER
                    )
                """)
            elif table == 'Bookmark':
                conn.execute(f"""
                    CREATE TABLE {table} (
                        BookmarkId INTEGER PRIMARY KEY,
                        LocationId INTEGER,
                        Title TEXT
                    )
                """)
            elif table == 'BlockRange':
                conn.execute(f"""
                    CREATE TABLE {table} (
                        BlockRangeId INTEGER PRIMARY KEY,
                        UserMarkId INTEGER,
                        StartToken INTEGER
                    )
                """)
        conn.commit()
        conn.close()
        
        yield db_path
        
        # Cleanup
        db_path.unlink()
        Path(temp_dir).rmdir()

    @pytest.fixture
    def empty_db(self):
        """Создаёт пустую БД без таблиц"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'empty.db'
        
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE some_other_table (id INTEGER)")
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
        assert "валидна" in message.lower()

    def test_empty_schema(self, empty_db):
        """Пустая схема должна возвращать список недостающих таблиц"""
        is_valid, missing, message = validate_database_schema(empty_db)
        assert is_valid is False
        assert len(missing) > 0
        assert all(table in ALLOWED_TABLES for table in missing)

    def test_nonexistent_db(self):
        """Несуществующий файл должен возвращать ошибку"""
        is_valid, missing, message = validate_database_schema('/nonexistent/path/db.sqlite')
        assert is_valid is False
        assert "ошибка" in message.lower() or "error" in message.lower()
