"""
Тесты для генерации хэшей записей
"""
import pytest
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jwl_backup_merger import generate_record_hash


class TestGenerateRecordHash:
    """Тесты для функции generate_record_hash"""

    def test_tag_same_name_same_type(self):
        """Одинаковые теги должны иметь одинаковый хэш"""
        data1 = {'Name': 'Test', 'Type': 1}
        data2 = {'Name': 'Test', 'Type': 1}
        assert generate_record_hash('Tag', data1) == generate_record_hash('Tag', data2)

    def test_tag_different_name(self):
        """Теги с разными именами должны иметь разный хэш"""
        data1 = {'Name': 'Test1', 'Type': 1}
        data2 = {'Name': 'Test2', 'Type': 1}
        assert generate_record_hash('Tag', data1) != generate_record_hash('Tag', data2)

    def test_tag_different_type(self):
        """Теги с разными типами должны иметь разный хэш"""
        data1 = {'Name': 'Test', 'Type': 1}
        data2 = {'Name': 'Test', 'Type': 2}
        assert generate_record_hash('Tag', data1) != generate_record_hash('Tag', data2)

    def test_tag_empty_name(self):
        """Тег с пустым именем"""
        data = {'Name': '', 'Type': 0}
        hash_result = generate_record_hash('Tag', data)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 = 64 hex chars

    def test_tag_none_values(self):
        """Тег с None значениями"""
        data = {'Name': None, 'Type': None}
        hash_result = generate_record_hash('Tag', data)
        assert isinstance(hash_result, str)

    def test_usermark_with_guid(self):
        """UserMark с GUID должен использовать GUID для хэша"""
        data1 = {'UserMarkGuid': 'abc-123', 'LocationId': 1, 'ColorIndex': 1}
        data2 = {'UserMarkGuid': 'abc-123', 'LocationId': 2, 'ColorIndex': 2}
        # Одинаковый GUID = одинаковый хэш
        assert generate_record_hash('UserMark', data1) == generate_record_hash('UserMark', data2)

    def test_usermark_without_guid(self):
        """UserMark без GUID должен использовать другие поля"""
        data1 = {'UserMarkGuid': None, 'LocationId': 1, 'ColorIndex': 1, 'StyleIndex': 0, 'Version': 0}
        data2 = {'UserMarkGuid': None, 'LocationId': 1, 'ColorIndex': 1, 'StyleIndex': 0, 'Version': 0}
        assert generate_record_hash('UserMark', data1) == generate_record_hash('UserMark', data2)

    def test_location_same_fields(self):
        """Location с одинаковыми полями"""
        data1 = {
            'BookNumber': 1, 'ChapterNumber': 2, 'DocumentId': 3,
            'KeySymbol': 'test', 'IssueTagNumber': 0, 'MepsLanguage': 0, 'Title': 'Test Title'
        }
        data2 = data1.copy()
        assert generate_record_hash('Location', data1) == generate_record_hash('Location', data2)

    def test_bookmark_same_fields(self):
        """Bookmark с одинаковыми полями"""
        data1 = {'LocationId': 1, 'Slot': 0, 'Title': 'Test', 'Snippet': 'Snippet'}
        data2 = data1.copy()
        assert generate_record_hash('Bookmark', data1) == generate_record_hash('Bookmark', data2)

    def test_not_same_content(self):
        """Note с одинаковым содержимым"""
        data1 = {
            'Content': 'Test content', 'Title': 'Test', 'LocationId': 1,
            'UserMarkId': None, 'BlockType': 0, 'BlockIdentifier': '', 'Guid': ''
        }
        data2 = data1.copy()
        assert generate_record_hash('Note', data1) == generate_record_hash('Note', data2)

    def test_not_different_content(self):
        """Note с разным содержимым"""
        data1 = {
            'Content': 'Test content 1', 'Title': 'Test', 'LocationId': 1,
            'UserMarkId': None, 'BlockType': 0, 'BlockIdentifier': '', 'Guid': ''
        }
        data2 = {
            'Content': 'Test content 2', 'Title': 'Test', 'LocationId': 1,
            'UserMarkId': None, 'BlockType': 0, 'BlockIdentifier': '', 'Guid': ''
        }
        assert generate_record_hash('Note', data1) != generate_record_hash('Note', data2)

    def test_tagmap_same_fields(self):
        """TagMap с одинаковыми полями"""
        data1 = {'Type': 1, 'TypeId': 100, 'TagId': 5, 'Position': 0}
        data2 = data1.copy()
        assert generate_record_hash('TagMap', data1) == generate_record_hash('TagMap', data2)

    def test_blockrange_same_fields(self):
        """BlockRange с одинаковыми полями"""
        data1 = {'BlockType': 1, 'Identifier': 100, 'StartToken': 5, 'EndToken': 10, 'UserMarkId': 3}
        data2 = data1.copy()
        assert generate_record_hash('BlockRange', data1) == generate_record_hash('BlockRange', data2)

    def test_unknown_table(self):
        """Неизвестная таблица должна использовать общий метод"""
        data = {'field1': 'value1', 'field2': 'value2'}
        hash_result = generate_record_hash('UnknownTable', data)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
