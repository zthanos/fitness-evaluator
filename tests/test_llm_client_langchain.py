"""
Test LLMClient LangChain integration.

Tests the enhanced LLMClient with LangChain support for:
- generate_response() with retry logic
- stream_response() with retry logic
- _build_prompt() with context and history
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.services.llm_client import LLMClient


@pytest.mark.asyncio
async def test_llm_client_initialization():
    """Test that LLMClient initializes with correct settings."""
    with patch('app.services.llm_client.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            LLM_TYPE='ollama',
            llm_base_url='http://localhost:11434',
            OLLAMA_MODEL='mistral',
            LM_STUDIO_MODEL='mistral',
            is_ollama=True
        )
        
        client = LLMClient()
        
        assert client.model_name == 'mistral'
        assert 'localhost:11434' in client.endpoint_url


@pytest.mark.asyncio
async def test_generate_response_success():
    """Test generate_response returns content successfully."""
    with patch('app.services.llm_client.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            LLM_TYPE='ollama',
            llm_base_url='http://localhost:11434',
            OLLAMA_MODEL='mistral',
            LM_STUDIO_MODEL='mistral',
            is_ollama=True
        )
        
        client = LLMClient()
        
        # Mock the LangChain ChatOpenAI
        with patch('app.services.llm_client.ChatOpenAI') as mock_chat:
            mock_llm = Mock()
            mock_result = Mock()
            mock_result.content = "Test response"
            
            # Mock the chain
            mock_chain = Mock()
            mock_chain.ainvoke = AsyncMock(return_value=mock_result)
            
            # Mock the pipe operator
            mock_prompt = Mock()
            mock_prompt.__or__ = Mock(return_value=mock_chain)
            
            with patch('app.services.llm_client.ChatPromptTemplate') as mock_template:
                mock_template.from_messages = Mock(return_value=mock_prompt)
                
                response = await client.generate_response(
                    prompt="Hello",
                    system_prompt="You are a coach",
                    temperature=0.7,
                    max_tokens=500
                )
                
                assert response == "Test response"


@pytest.mark.asyncio
async def test_generate_response_retry_on_connection_error():
    """Test generate_response retries on connection errors."""
    import httpx
    
    with patch('app.services.llm_client.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            LLM_TYPE='ollama',
            llm_base_url='http://localhost:11434',
            OLLAMA_MODEL='mistral',
            LM_STUDIO_MODEL='mistral',
            is_ollama=True
        )
        
        client = LLMClient()
        
        with patch('app.services.llm_client.ChatOpenAI') as mock_chat:
            mock_chain = Mock()
            # Fail twice, succeed on third attempt
            mock_result = Mock()
            mock_result.content = "Success after retry"
            mock_chain.ainvoke = AsyncMock(
                side_effect=[
                    httpx.ConnectError("Connection failed"),
                    httpx.ConnectError("Connection failed"),
                    mock_result
                ]
            )
            
            mock_prompt = Mock()
            mock_prompt.__or__ = Mock(return_value=mock_chain)
            
            with patch('app.services.llm_client.ChatPromptTemplate') as mock_template:
                mock_template.from_messages = Mock(return_value=mock_prompt)
                
                response = await client.generate_response(
                    prompt="Hello",
                    temperature=0.7,
                    max_tokens=500
                )
                
                assert response == "Success after retry"
                assert mock_chain.ainvoke.call_count == 3


@pytest.mark.asyncio
async def test_stream_response_success():
    """Test stream_response yields chunks successfully."""
    with patch('app.services.llm_client.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            LLM_TYPE='ollama',
            llm_base_url='http://localhost:11434',
            OLLAMA_MODEL='mistral',
            LM_STUDIO_MODEL='mistral',
            is_ollama=True
        )
        
        client = LLMClient()
        
        with patch('app.services.llm_client.ChatOpenAI') as mock_chat:
            # Mock streaming chunks
            async def mock_astream(input_dict):
                chunks = [Mock(content="Hello"), Mock(content=" "), Mock(content="world")]
                for chunk in chunks:
                    yield chunk
            
            mock_chain = Mock()
            mock_chain.astream = mock_astream
            
            mock_prompt = Mock()
            mock_prompt.__or__ = Mock(return_value=mock_chain)
            
            with patch('app.services.llm_client.ChatPromptTemplate') as mock_template:
                mock_template.from_messages = Mock(return_value=mock_prompt)
                
                chunks = []
                async for chunk in client.stream_response(
                    prompt="Hello",
                    temperature=0.7,
                    max_tokens=500
                ):
                    chunks.append(chunk)
                
                assert chunks == ["Hello", " ", "world"]


def test_build_prompt_with_all_context():
    """Test _build_prompt includes all context elements."""
    with patch('app.services.llm_client.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            LLM_TYPE='ollama',
            llm_base_url='http://localhost:11434',
            OLLAMA_MODEL='mistral',
            LM_STUDIO_MODEL='mistral',
            is_ollama=True
        )
        
        client = LLMClient()
        
        # Mock ChatPromptTemplate
        with patch('app.services.llm_client.ChatPromptTemplate') as mock_template:
            mock_prompt = Mock()
            mock_prompt.format = Mock(return_value="Formatted prompt")
            mock_template.from_messages = Mock(return_value=mock_prompt)
            
            result = client._build_prompt(
                user_message="What should I do?",
                context="Activity: 10km run on 2024-01-15",
                history=[
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"}
                ],
                athlete_profile={
                    "name": "John Doe",
                    "goals": "Lose weight",
                    "current_plan": "Marathon training"
                }
            )
            
            assert result == "Formatted prompt"
            
            # Verify the messages passed to from_messages
            call_args = mock_template.from_messages.call_args[0][0]
            
            # Should have system message, history, and user message
            assert len(call_args) >= 4  # system + 2 history + current user
            
            # First message should be system
            assert call_args[0][0] == "system"
            
            # System message should contain athlete profile
            system_content = call_args[0][1]
            assert "John Doe" in system_content
            assert "Lose weight" in system_content
            assert "Marathon training" in system_content
            
            # System message should contain RAG context
            assert "Activity: 10km run on 2024-01-15" in system_content


def test_build_prompt_with_history_limit():
    """Test _build_prompt limits history to last 10 messages."""
    with patch('app.services.llm_client.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            LLM_TYPE='ollama',
            llm_base_url='http://localhost:11434',
            OLLAMA_MODEL='mistral',
            LM_STUDIO_MODEL='mistral',
            is_ollama=True
        )
        
        client = LLMClient()
        
        # Create 15 messages
        history = []
        for i in range(15):
            history.append({"role": "user", "content": f"Message {i}"})
            history.append({"role": "assistant", "content": f"Response {i}"})
        
        with patch('app.services.llm_client.ChatPromptTemplate') as mock_template:
            mock_prompt = Mock()
            mock_prompt.format = Mock(return_value="Formatted prompt")
            mock_template.from_messages = Mock(return_value=mock_prompt)
            
            result = client._build_prompt(
                user_message="Current message",
                history=history
            )
            
            # Verify only last 10 messages from history were included
            call_args = mock_template.from_messages.call_args[0][0]
            
            # Should have: system + 10 history messages + current user = 12 total
            assert len(call_args) == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
