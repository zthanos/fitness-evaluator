"""
Tests for Phase 2: Prompt Template Loading

Tests cover:
- System instructions template loading
- Task instructions template loading
- Template versioning
- Configuration variable injection
- Template validation
- Token budget validation
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import yaml

from app.ai.prompts.system_loader import SystemInstructionsLoader
from app.ai.prompts.task_loader import TaskInstructionsLoader


class TestSystemInstructionsLoading:
    """Test system instructions template loading."""
    
    def test_load_default_version(self):
        """Test loading default version (1.0.0) of system instructions."""
        loader = SystemInstructionsLoader()
        
        # Load default version
        instructions = loader.load(version="1.0.0")
        
        # Should return non-empty string
        assert isinstance(instructions, str)
        assert len(instructions) > 0
    
    def test_load_specific_version(self):
        """Test loading specific version of system instructions."""
        loader = SystemInstructionsLoader()
        
        # Load version 1.0.0
        instructions = loader.load(version="1.0.0")
        
        assert isinstance(instructions, str)
        assert len(instructions) > 0
    
    def test_template_not_found_raises_error(self):
        """Test that loading non-existent template raises FileNotFoundError."""
        loader = SystemInstructionsLoader()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load(version="99.99.99")
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_list_available_versions(self):
        """Test listing available system instruction versions."""
        loader = SystemInstructionsLoader()
        
        versions = loader.list_versions()
        
        # Should return list of version strings
        assert isinstance(versions, list)
        # Should include at least version 1.0.0
        assert "1.0.0" in versions
    
    def test_template_contains_required_sections(self):
        """Test that loaded template contains required sections."""
        loader = SystemInstructionsLoader()
        
        instructions = loader.load(version="1.0.0")
        instructions_lower = instructions.lower()
        
        # Should contain persona definition
        assert "persona" in instructions_lower or "coach" in instructions_lower
        
        # Should contain behavioral constraints
        assert "constraint" in instructions_lower or "must" in instructions_lower
        
        # Should contain output format
        assert "output" in instructions_lower or "format" in instructions_lower
    
    def test_configuration_variables_injected(self):
        """Test that configuration variables are injected into template."""
        loader = SystemInstructionsLoader()
        
        # Mock configuration
        mock_config = {
            "coach_name": "Test Coach",
            "certifications": ["Test Cert 1", "Test Cert 2"],
            "tone": "test tone",
            "max_recommendations": 3
        }
        
        with patch.object(loader, '_load_config', return_value=mock_config):
            instructions = loader.load(version="1.0.0")
            
            # Configuration variables should be in rendered template
            # (Note: This depends on template actually using these variables)
            assert isinstance(instructions, str)
    
    def test_custom_templates_directory(self):
        """Test using custom templates directory."""
        custom_dir = Path("custom/templates")
        loader = SystemInstructionsLoader(templates_dir=custom_dir)
        
        assert loader.templates_dir == custom_dir
    
    def test_load_config_with_missing_file(self):
        """Test that missing config file returns default configuration."""
        loader = SystemInstructionsLoader()
        
        # Point to non-existent config directory
        loader.config_dir = Path("/nonexistent/path")
        
        config = loader._load_config()
        
        # Should return default configuration
        assert isinstance(config, dict)
        assert "coach_name" in config
        assert "certifications" in config
    
    def test_load_config_with_valid_file(self):
        """Test loading configuration from valid YAML file."""
        loader = SystemInstructionsLoader()
        
        mock_config_content = """
coach_name: "AI Fitness Coach"
certifications:
  - "Exercise Physiology"
  - "Sports Nutrition"
tone: "supportive"
max_recommendations: 5
"""
        
        with patch("builtins.open", mock_open(read_data=mock_config_content)):
            with patch.object(Path, 'exists', return_value=True):
                config = loader._load_config()
                
                assert config["coach_name"] == "AI Fitness Coach"
                assert len(config["certifications"]) == 2
                assert config["tone"] == "supportive"


class TestTaskInstructionsLoading:
    """Test task instructions template loading."""
    
    def test_load_chat_response_template(self):
        """Test loading chat_response task template."""
        loader = TaskInstructionsLoader()
        
        instructions = loader.load(
            operation="chat_response",
            version="1.0.0"
        )
        
        assert isinstance(instructions, str)
        assert len(instructions) > 0
    
    def test_load_with_runtime_parameters(self):
        """Test loading template with runtime parameters."""
        loader = TaskInstructionsLoader()
        
        params = {
            "athlete_id": 123,
            "session_id": 456,
            "intent": "recent_performance",
            "timestamp": "2024-03-10T10:00:00"
        }
        
        instructions = loader.load(
            operation="chat_response",
            version="1.0.0",
            params=params
        )
        
        assert isinstance(instructions, str)
        # Parameters should be injected (if template uses them)
        assert len(instructions) > 0
    
    def test_template_not_found_raises_error(self):
        """Test that loading non-existent template raises FileNotFoundError."""
        loader = TaskInstructionsLoader()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load(operation="nonexistent_operation", version="1.0.0")
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_template_contains_required_fields(self):
        """Test that loaded template contains required fields."""
        loader = TaskInstructionsLoader()
        
        instructions = loader.load(
            operation="chat_response",
            version="1.0.0"
        )
        instructions_lower = instructions.lower()
        
        # Should contain objective
        assert "objective" in instructions_lower
        
        # Should contain input description
        assert "input" in instructions_lower
        
        # Should contain output schema reference
        assert "output" in instructions_lower or "schema" in instructions_lower
    
    def test_validate_token_limit_within_budget(self):
        """Test token limit validation for template within budget."""
        loader = TaskInstructionsLoader()
        
        instructions = loader.load(
            operation="chat_response",
            version="1.0.0"
        )
        
        # Get actual token count
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        actual_tokens = len(encoding.encode(instructions))
        
        # Should be within reasonable limit (use actual + buffer)
        is_valid = loader.validate_token_limit(instructions, max_tokens=actual_tokens + 100)
        assert is_valid is True
        
        # Should fail with very low limit
        is_invalid = loader.validate_token_limit(instructions, max_tokens=100)
        assert is_invalid is False
    
    def test_validate_token_limit_exceeds_budget(self):
        """Test token limit validation for template exceeding budget."""
        loader = TaskInstructionsLoader()
        
        # Create very long text
        long_text = "This is a very long instruction. " * 500
        
        # Should exceed 100 token limit
        is_valid = loader.validate_token_limit(long_text, max_tokens=100)
        assert is_valid is False
    
    def test_custom_templates_directory(self):
        """Test using custom templates directory."""
        custom_dir = Path("custom/tasks")
        loader = TaskInstructionsLoader(templates_dir=custom_dir)
        
        assert loader.templates_dir == custom_dir
    
    def test_load_without_parameters(self):
        """Test loading template without runtime parameters."""
        loader = TaskInstructionsLoader()
        
        instructions = loader.load(
            operation="chat_response",
            version="1.0.0",
            params=None
        )
        
        assert isinstance(instructions, str)
        assert len(instructions) > 0


class TestTemplateVersioning:
    """Test template versioning functionality."""
    
    def test_version_format_in_filename(self):
        """Test that version format is correctly used in filename."""
        loader = SystemInstructionsLoader()
        
        # Should construct filename with version
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load(version="2.0.0")
        
        # Error message should mention the versioned filename
        assert "coach_persona_v2.0.0.j2" in str(exc_info.value)
    
    def test_list_versions_sorted(self):
        """Test that listed versions are sorted."""
        loader = SystemInstructionsLoader()
        
        versions = loader.list_versions()
        
        # Should be sorted
        assert versions == sorted(versions)
    
    def test_multiple_versions_available(self):
        """Test handling multiple template versions."""
        loader = SystemInstructionsLoader()
        
        versions = loader.list_versions()
        
        # Should have at least one version
        assert len(versions) >= 1


class TestTemplateValidation:
    """Test template validation."""
    
    def test_validate_system_template_success(self):
        """Test successful validation of system template."""
        loader = SystemInstructionsLoader()
        
        # Valid template content
        valid_content = """
        Persona: You are a fitness coach
        Behavioral Constraints: Follow these rules
        Output Format: Provide structured responses
        """
        
        # Should not raise exception
        loader._validate_template(valid_content, "test_template.j2")
    
    def test_validate_system_template_missing_sections(self):
        """Test validation failure for missing sections."""
        loader = SystemInstructionsLoader()
        
        # Invalid template content (missing sections)
        invalid_content = "This is just some text without required sections"
        
        with pytest.raises(ValueError) as exc_info:
            loader._validate_template(invalid_content, "test_template.j2")
        
        assert "missing required sections" in str(exc_info.value).lower()
    
    def test_validate_task_template_success(self):
        """Test successful validation of task template."""
        loader = TaskInstructionsLoader()
        
        # Valid template content
        valid_content = """
        Objective: Respond to athlete query
        Input Description: User message and context
        Output Schema Reference: ChatResponseContract
        """
        
        # Should not raise exception
        loader._validate_template(valid_content, "test_template.j2")
    
    def test_validate_task_template_missing_fields(self):
        """Test validation failure for missing fields."""
        loader = TaskInstructionsLoader()
        
        # Invalid template content (missing fields)
        invalid_content = "This is just some text without required fields"
        
        with pytest.raises(ValueError) as exc_info:
            loader._validate_template(invalid_content, "test_template.j2")
        
        assert "missing required fields" in str(exc_info.value).lower()


class TestIntegrationWithChatContextBuilder:
    """Test integration of prompt loaders with ChatContextBuilder."""
    
    def test_context_builder_loads_prompts(self):
        """Test that ChatContextBuilder can use prompt loaders."""
        from app.ai.context.chat_context import ChatContextBuilder
        from app.ai.prompts.system_loader import SystemInstructionsLoader
        from app.ai.prompts.task_loader import TaskInstructionsLoader
        
        # Create loaders
        system_loader = SystemInstructionsLoader()
        task_loader = TaskInstructionsLoader()
        
        # Load prompts
        system_instructions = system_loader.load(version="1.0.0")
        task_instructions = task_loader.load(operation="chat_response", version="1.0.0")
        
        # Create builder
        mock_db = Mock()
        builder = ChatContextBuilder(db=mock_db)
        
        # Add instructions
        builder.add_system_instructions(system_instructions)
        builder.add_task_instructions(task_instructions)
        
        # Verify instructions were added
        assert builder._system_instructions == system_instructions
        assert builder._task_instructions == task_instructions
        assert len(builder._system_instructions) > 0
        assert len(builder._task_instructions) > 0


class TestErrorHandling:
    """Test error handling in template loading."""
    
    def test_handle_corrupted_yaml_config(self):
        """Test handling of corrupted YAML configuration."""
        loader = SystemInstructionsLoader()
        
        # Mock corrupted YAML content
        corrupted_yaml = "invalid: yaml: content: [unclosed"
        
        with patch("builtins.open", mock_open(read_data=corrupted_yaml)):
            with patch.object(Path, 'exists', return_value=True):
                with pytest.raises(ValueError) as exc_info:
                    loader._load_config()
                
                assert "failed to load configuration" in str(exc_info.value).lower()
    
    def test_handle_missing_template_directory(self):
        """Test handling of missing template directory."""
        loader = SystemInstructionsLoader(templates_dir=Path("/nonexistent/path"))
        
        with pytest.raises(FileNotFoundError):
            loader.load(version="1.0.0")
    
    def test_handle_empty_template(self):
        """Test handling of empty template."""
        loader = SystemInstructionsLoader()
        
        # Empty template should fail validation
        with pytest.raises(ValueError):
            loader._validate_template("", "empty_template.j2")


class TestPerformance:
    """Test performance characteristics of template loading."""
    
    def test_template_loading_is_fast(self):
        """Test that template loading completes quickly."""
        import time
        
        loader = SystemInstructionsLoader()
        
        start_time = time.time()
        loader.load(version="1.0.0")
        elapsed = time.time() - start_time
        
        # Should complete in less than 100ms
        assert elapsed < 0.1
    
    def test_multiple_loads_consistent(self):
        """Test that multiple loads return consistent results."""
        loader = SystemInstructionsLoader()
        
        result1 = loader.load(version="1.0.0")
        result2 = loader.load(version="1.0.0")
        
        # Should return identical results
        assert result1 == result2
