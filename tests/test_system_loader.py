"""
Test SystemInstructionsLoader implementation
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from app.ai.prompts.system_loader import SystemInstructionsLoader


def test_system_loader_initialization():
    """Test that SystemInstructionsLoader can be initialized"""
    loader = SystemInstructionsLoader()
    assert loader is not None
    assert loader.templates_dir.exists()


def test_list_versions_empty():
    """Test list_versions returns empty list when no templates exist"""
    loader = SystemInstructionsLoader()
    versions = loader.list_versions()
    assert isinstance(versions, list)
    # May be empty if no templates exist yet
    print(f"Available versions: {versions}")


def test_load_missing_template():
    """Test that loading a non-existent template raises FileNotFoundError"""
    loader = SystemInstructionsLoader()
    
    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load(version="999.999.999")
    
    assert "not found" in str(exc_info.value).lower()


def test_load_with_custom_dirs():
    """Test SystemInstructionsLoader with custom directories"""
    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        templates_dir = temp_path / "templates"
        config_dir = temp_path / "config"
        
        templates_dir.mkdir()
        config_dir.mkdir()
        
        # Create a simple template
        template_file = templates_dir / "coach_persona_v1.0.0.j2"
        template_file.write_text("""
# Persona
You are an AI coach.

# Behavioral Constraints
- Be helpful
- Be accurate

# Output Format
Use structured responses.
""")
        
        # Create a simple config
        config_file = config_dir / "coach_persona.yaml"
        config_file.write_text("""
coach_name: "Test Coach"
certifications:
  - "Test Cert"
tone: "friendly"
max_recommendations: 3
""")
        
        # Test loader
        loader = SystemInstructionsLoader(templates_dir=templates_dir, config_dir=config_dir)
        
        # Test list_versions
        versions = loader.list_versions()
        assert "1.0.0" in versions
        
        # Test load
        rendered = loader.load(version="1.0.0")
        assert "Persona" in rendered
        assert "Behavioral Constraints" in rendered
        assert "Output Format" in rendered


def test_validation_missing_sections():
    """Test that validation catches missing required sections"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        templates_dir = temp_path / "templates"
        config_dir = temp_path / "config"
        
        templates_dir.mkdir()
        config_dir.mkdir()
        
        # Create a template missing required sections
        template_file = templates_dir / "coach_persona_v1.0.0.j2"
        template_file.write_text("""
# Persona
You are an AI coach.
""")
        
        loader = SystemInstructionsLoader(templates_dir=templates_dir, config_dir=config_dir)
        
        with pytest.raises(ValueError) as exc_info:
            loader.load(version="1.0.0")
        
        assert "missing required sections" in str(exc_info.value).lower()


if __name__ == "__main__":
    # Run basic tests
    print("Testing SystemInstructionsLoader...")
    
    test_system_loader_initialization()
    print("✓ Initialization test passed")
    
    test_list_versions_empty()
    print("✓ List versions test passed")
    
    test_load_missing_template()
    print("✓ Missing template test passed")
    
    test_load_with_custom_dirs()
    print("✓ Custom directories test passed")
    
    test_validation_missing_sections()
    print("✓ Validation test passed")
    
    print("\nAll tests passed!")
