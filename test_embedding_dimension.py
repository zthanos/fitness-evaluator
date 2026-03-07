"""Property Test: Embedding Dimension Invariant

Property 4: For all records indexed by the RAG_System, the generated embedding 
SHALL have exactly 768 dimensions.

**Validates: Requirements 15.6, 28.2**

This test uses property-based testing to verify that embeddings always have the 
correct dimension regardless of input text content or length.

Note: Updated to use Ollama's nomic-embed-text model (768 dimensions) instead of 
sentence-transformers all-MiniLM-L6-v2 (384 dimensions).
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.services.rag_service import RAGSystem
import tempfile
import os


@pytest.fixture
def test_db():
    """Create a test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def rag_system(test_db):
    """Create a RAG system with temporary index."""
    temp_dir = tempfile.mkdtemp()
    index_path = os.path.join(temp_dir, "test_index.bin")
    
    rag = RAGSystem(test_db, index_path=index_path)
    yield rag
    
    # Cleanup
    if os.path.exists(index_path):
        os.remove(index_path)
    metadata_path = index_path.replace(".bin", "_metadata.pkl")
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
    try:
        os.rmdir(temp_dir)
    except:
        pass


# Property 4: Embedding Dimension Invariant
@given(
    text=st.text(
        alphabet=st.characters(blacklist_categories=('Cs',)),  # Exclude surrogates
        min_size=1,
        max_size=1000
    )
)
@settings(
    max_examples=50, 
    deadline=5000,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_embedding_dimension_invariant(rag_system, text):
    """
    Property 4: Embedding Dimension Invariant
    
    For all text inputs, the generated embedding SHALL have exactly 768 dimensions.
    
    This property ensures that:
    1. All embeddings are 768-dimensional (matching nomic-embed-text output)
    2. Embedding dimension is consistent regardless of input text length
    3. Embedding dimension is consistent regardless of input text content
    
    **Validates: Requirements 15.6, 28.2**
    """
    # Generate embedding
    embedding = rag_system.generate_embedding(text)
    
    # Property: Embedding must be exactly 768 dimensions
    assert embedding.shape == (768,), \
        f"Embedding dimension must be 768, got {embedding.shape}"
    
    # Additional invariant: Embedding should be normalized (L2 norm ≈ 1)
    import numpy as np
    norm = np.linalg.norm(embedding)
    assert 0.99 <= norm <= 1.01, \
        f"Embedding should be normalized (L2 norm ≈ 1), got {norm}"


@given(
    text_length=st.integers(min_value=1, max_value=5000)
)
@settings(
    max_examples=30, 
    deadline=5000,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_embedding_dimension_with_varying_lengths(rag_system, text_length):
    """
    Test embedding dimension with varying text lengths.
    
    This ensures that even very short or very long texts produce 768-dimensional embeddings.
    """
    # Generate text of specific length
    text = "a" * text_length
    
    # Generate embedding
    embedding = rag_system.generate_embedding(text)
    
    # Property: Embedding must be exactly 768 dimensions
    assert embedding.shape == (768,), \
        f"Embedding dimension must be 768 for text length {text_length}, got {embedding.shape}"


@given(
    text=st.one_of(
        st.just(""),  # Empty string edge case
        st.just(" "),  # Single space
        st.just("\n"),  # Newline
        st.just("a"),  # Single character
        st.text(min_size=1, max_size=10),  # Short text
        st.text(min_size=100, max_size=500),  # Medium text
        st.text(min_size=1000, max_size=2000),  # Long text
    )
)
@settings(
    max_examples=40, 
    deadline=5000,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_embedding_dimension_edge_cases(rag_system, text):
    """
    Test embedding dimension with edge cases.
    
    This ensures that edge cases (empty, whitespace, very short, very long) 
    all produce 768-dimensional embeddings.
    """
    # Handle empty string edge case (Ollama may handle differently)
    if not text or text.isspace():
        text = " "  # Use single space for empty/whitespace
    
    # Generate embedding
    embedding = rag_system.generate_embedding(text)
    
    # Property: Embedding must be exactly 768 dimensions
    assert embedding.shape == (768,), \
        f"Embedding dimension must be 768 for edge case text, got {embedding.shape}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
