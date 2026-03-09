"""Tests for CodeAnalyzer class."""

import tempfile
from pathlib import Path

from .code_analyzer import CodeAnalyzer


def test_temporary_file_detection():
    """Test that temporary files are correctly identified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create a temporary test file
        temp_file = workspace / "test_debug_something.py"
        temp_file.write_text("def test_foo(): pass")
        
        report = analyzer.analyze_test_file(temp_file)
        
        assert report.is_obsolete is True
        assert "debug" in report.reason.lower()
        assert report.confidence >= 0.8


def test_non_obsolete_file():
    """Test that normal test files are not marked as obsolete."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create a normal test file
        test_file = workspace / "test_normal.py"
        test_file.write_text("def test_foo(): pass")
        
        report = analyzer.analyze_test_file(test_file)
        
        assert report.is_obsolete is False
        assert report.confidence == 0.0


def test_unparseable_file():
    """Test that unparseable files are not marked as obsolete (conservative)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create a file with syntax errors
        bad_file = workspace / "test_bad.py"
        bad_file.write_text("def test_foo( invalid syntax")
        
        report = analyzer.analyze_test_file(bad_file)
        
        assert report.is_obsolete is False
        assert "Could not parse" in report.reason


def test_superseded_file_detection():
    """Test that superseded files are correctly identified."""
    import time
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create an old test file
        old_file = workspace / "test_feature.py"
        old_file.write_text("def test_foo(): pass")
        
        # Wait a bit to ensure different modification times
        time.sleep(0.1)
        
        # Create a newer version
        new_file = workspace / "test_feature_v2.py"
        new_file.write_text("def test_foo(): pass")
        
        # Analyze the old file
        report = analyzer.analyze_test_file(old_file)
        
        # The old file should be marked as superseded
        assert report.is_obsolete is True
        assert "superseded" in report.reason.lower()


def test_duplicate_detection():
    """Test that duplicate test files are correctly identified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create first test file
        file1 = workspace / "test_first.py"
        file1.write_text("""
import pytest
from app.models import User

def test_user_creation():
    pass

def test_user_update():
    pass

def test_user_delete():
    pass
""")
        
        # Create duplicate test file with same functions
        file2 = workspace / "test_second.py"
        file2.write_text("""
import pytest
from app.models import User

def test_user_creation():
    pass

def test_user_update():
    pass

def test_user_delete():
    pass
""")
        
        # Analyze both files
        report1 = analyzer.analyze_test_file(file1)
        report2 = analyzer.analyze_test_file(file2)
        
        # The second file should be marked as duplicate
        assert report2.is_obsolete is True
        assert "duplicate" in report2.reason.lower()


def test_extract_test_functions():
    """Test that test functions are correctly extracted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create a test file with multiple test functions
        test_file = workspace / "test_example.py"
        test_file.write_text("""
def test_foo():
    pass

def test_bar():
    pass

def helper_function():
    pass

def test_baz():
    pass
""")
        
        # Parse and extract test functions
        with open(test_file, 'r') as f:
            import ast
            tree = ast.parse(f.read())
        
        test_functions = analyzer._extract_test_functions(tree)
        
        assert len(test_functions) == 3
        assert "test_foo" in test_functions
        assert "test_bar" in test_functions
        assert "test_baz" in test_functions
        assert "helper_function" not in test_functions


def test_extract_imports():
    """Test that imports are correctly extracted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create a test file with various imports
        test_file = workspace / "test_example.py"
        test_file.write_text("""
import os
import sys
from pathlib import Path
from app.models import User
from app.services.auth import authenticate
""")
        
        # Parse and extract imports
        with open(test_file, 'r') as f:
            import ast
            tree = ast.parse(f.read())
        
        imports = analyzer._extract_imports(tree)
        
        assert "os" in imports
        assert "sys" in imports
        assert "pathlib" in imports
        assert "app" in imports


def test_find_duplicate_tests_with_duplicates():
    """Test that find_duplicate_tests identifies duplicate test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create first test file
        file1 = workspace / "test_user_api.py"
        file1.write_text("""
import pytest
from app.models import User

def test_create_user():
    pass

def test_update_user():
    pass

def test_delete_user():
    pass
""")
        
        # Create duplicate test file with same functions
        file2 = workspace / "test_user_duplicate.py"
        file2.write_text("""
import pytest
from app.models import User

def test_create_user():
    pass

def test_update_user():
    pass

def test_delete_user():
    pass
""")
        
        # Create a different test file
        file3 = workspace / "test_auth.py"
        file3.write_text("""
import pytest
from app.auth import login

def test_login():
    pass

def test_logout():
    pass
""")
        
        # Find duplicates
        test_files = [file1, file2, file3]
        duplicate_groups = analyzer.find_duplicate_tests(test_files)
        
        # Should find one duplicate group containing file1 and file2
        assert len(duplicate_groups) == 1
        assert len(duplicate_groups[0].files) == 2
        assert file1 in duplicate_groups[0].files
        assert file2 in duplicate_groups[0].files
        assert file3 not in duplicate_groups[0].files
        
        # Check shared test functions
        assert "test_create_user" in duplicate_groups[0].shared_test_functions
        assert "test_update_user" in duplicate_groups[0].shared_test_functions
        assert "test_delete_user" in duplicate_groups[0].shared_test_functions
        
        # Check similarity score
        assert duplicate_groups[0].similarity_score >= 0.6


def test_find_duplicate_tests_no_duplicates():
    """Test that find_duplicate_tests returns empty list when no duplicates exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create different test files
        file1 = workspace / "test_user.py"
        file1.write_text("""
def test_create_user():
    pass
""")
        
        file2 = workspace / "test_auth.py"
        file2.write_text("""
def test_login():
    pass
""")
        
        file3 = workspace / "test_product.py"
        file3.write_text("""
def test_create_product():
    pass
""")
        
        # Find duplicates
        test_files = [file1, file2, file3]
        duplicate_groups = analyzer.find_duplicate_tests(test_files)
        
        # Should find no duplicate groups
        assert len(duplicate_groups) == 0


def test_find_duplicate_tests_partial_overlap():
    """Test that find_duplicate_tests handles partial overlap correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create first test file
        file1 = workspace / "test_user_v1.py"
        file1.write_text("""
import pytest
from app.models import User

def test_create_user():
    pass

def test_update_user():
    pass

def test_delete_user():
    pass

def test_list_users():
    pass
""")
        
        # Create file with partial overlap (75% similarity)
        file2 = workspace / "test_user_v2.py"
        file2.write_text("""
import pytest
from app.models import User

def test_create_user():
    pass

def test_update_user():
    pass

def test_delete_user():
    pass

def test_archive_user():
    pass
""")
        
        # Find duplicates
        test_files = [file1, file2]
        duplicate_groups = analyzer.find_duplicate_tests(test_files)
        
        # Should find one duplicate group (75% overlap is above 60% threshold)
        assert len(duplicate_groups) == 1
        assert len(duplicate_groups[0].files) == 2
        
        # Check shared test functions (only the common ones)
        assert "test_create_user" in duplicate_groups[0].shared_test_functions
        assert "test_update_user" in duplicate_groups[0].shared_test_functions
        assert "test_delete_user" in duplicate_groups[0].shared_test_functions
        assert "test_list_users" not in duplicate_groups[0].shared_test_functions
        assert "test_archive_user" not in duplicate_groups[0].shared_test_functions


def test_find_duplicate_tests_skips_non_python():
    """Test that find_duplicate_tests skips non-Python files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create Python test file
        file1 = workspace / "test_user.py"
        file1.write_text("""
def test_create_user():
    pass
""")
        
        # Create non-Python files
        file2 = workspace / "test_data.html"
        file2.write_text("<html><body>Test</body></html>")
        
        file3 = workspace / "test_data.db"
        file3.write_bytes(b"binary data")
        
        # Find duplicates
        test_files = [file1, file2, file3]
        duplicate_groups = analyzer.find_duplicate_tests(test_files)
        
        # Should not crash and should return empty list (no duplicates)
        assert len(duplicate_groups) == 0


def test_find_duplicate_tests_multiple_groups():
    """Test that find_duplicate_tests can identify multiple duplicate groups."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        analyzer = CodeAnalyzer(workspace)
        
        # Create first duplicate group (user tests)
        user1 = workspace / "test_user_v1.py"
        user1.write_text("""
def test_create_user():
    pass

def test_update_user():
    pass
""")
        
        user2 = workspace / "test_user_v2.py"
        user2.write_text("""
def test_create_user():
    pass

def test_update_user():
    pass
""")
        
        # Create second duplicate group (product tests)
        product1 = workspace / "test_product_v1.py"
        product1.write_text("""
def test_create_product():
    pass

def test_update_product():
    pass
""")
        
        product2 = workspace / "test_product_v2.py"
        product2.write_text("""
def test_create_product():
    pass

def test_update_product():
    pass
""")
        
        # Find duplicates
        test_files = [user1, user2, product1, product2]
        duplicate_groups = analyzer.find_duplicate_tests(test_files)
        
        # Should find two duplicate groups
        assert len(duplicate_groups) == 2
        
        # Each group should have 2 files
        assert all(len(group.files) == 2 for group in duplicate_groups)
        
        # Check that the groups are distinct
        all_files_in_groups = set()
        for group in duplicate_groups:
            for file in group.files:
                all_files_in_groups.add(file)
        
        assert len(all_files_in_groups) == 4


if __name__ == "__main__":
    # Run tests
    test_temporary_file_detection()
    print("✓ test_temporary_file_detection passed")
    
    test_non_obsolete_file()
    print("✓ test_non_obsolete_file passed")
    
    test_unparseable_file()
    print("✓ test_unparseable_file passed")
    
    test_superseded_file_detection()
    print("✓ test_superseded_file_detection passed")
    
    test_duplicate_detection()
    print("✓ test_duplicate_detection passed")
    
    test_extract_test_functions()
    print("✓ test_extract_test_functions passed")
    
    test_extract_imports()
    print("✓ test_extract_imports passed")
    
    test_find_duplicate_tests_with_duplicates()
    print("✓ test_find_duplicate_tests_with_duplicates passed")
    
    test_find_duplicate_tests_no_duplicates()
    print("✓ test_find_duplicate_tests_no_duplicates passed")
    
    test_find_duplicate_tests_partial_overlap()
    print("✓ test_find_duplicate_tests_partial_overlap passed")
    
    test_find_duplicate_tests_skips_non_python()
    print("✓ test_find_duplicate_tests_skips_non_python passed")
    
    test_find_duplicate_tests_multiple_groups()
    print("✓ test_find_duplicate_tests_multiple_groups passed")
    
    print("\nAll tests passed!")
