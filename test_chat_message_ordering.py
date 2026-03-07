"""
Property-Based Test for Chat Message Ordering

Property 6: Chat Message Ordering
For any Chat_Session, messages SHALL be ordered by created_at timestamp in ascending order,
and for all messages M1 and M2 where M1 is before M2, M1.created_at <= M2.created_at.

**Validates: Requirements 17**

This test verifies that chat messages maintain proper chronological ordering.
"""

import pytest
from hypothesis import given, strategies as st, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from app.models.base import Base
from app.models.athlete import Athlete
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage


# Strategy for generating message content
message_content_strategy = st.text(min_size=1, max_size=500, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'Zs'),
    blacklist_characters='\x00'
))

# Strategy for generating timestamps with microsecond precision
def timestamp_strategy(base_time=None):
    """Generate timestamps that are monotonically increasing."""
    if base_time is None:
        base_time = datetime.utcnow()
    return st.datetimes(
        min_value=base_time,
        max_value=base_time + timedelta(hours=24)
    )


class ChatMessageOrderingStateMachine(RuleBasedStateMachine):
    """
    Stateful property test for chat message ordering.
    
    This test creates chat sessions and adds messages with various timestamps,
    then verifies that messages are always returned in chronological order.
    """
    
    def __init__(self):
        super().__init__()
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        
        # Create test athlete
        self.athlete = Athlete(
            name="Test Athlete",
            email="test@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(self.athlete)
        self.db.commit()
        
        # Track sessions
        self.sessions = []
    
    def teardown(self):
        """Clean up database."""
        self.db.close()
        self.engine.dispose()
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path)
        except PermissionError:
            # On Windows, file may still be locked
            pass
    
    @rule()
    def create_session(self):
        """Create a new chat session."""
        session = ChatSession(
            athlete_id=self.athlete.id,
            title=f"Test Session {len(self.sessions)}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(session)
        self.db.commit()
        self.sessions.append(session.id)
    
    @rule(
        session_idx=st.integers(min_value=0, max_value=10),
        content=message_content_strategy,
        role=st.sampled_from(['user', 'assistant'])
    )
    def add_message(self, session_idx, content, role):
        """Add a message to a random session."""
        if not self.sessions:
            return
        
        session_id = self.sessions[session_idx % len(self.sessions)]
        
        # Get the latest message timestamp for this session
        latest_message = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).first()
        
        # Ensure new message has timestamp >= latest message
        if latest_message:
            # Add a small delay to ensure ordering
            created_at = latest_message.created_at + timedelta(microseconds=1)
        else:
            created_at = datetime.utcnow()
        
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=created_at
        )
        self.db.add(message)
        self.db.commit()
    
    @invariant()
    def messages_are_ordered(self):
        """
        Verify that all messages in all sessions are ordered by created_at.
        
        Property: For all messages M1 and M2 in a session where M1 appears before M2,
        M1.created_at <= M2.created_at
        """
        for session_id in self.sessions:
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            # Check that timestamps are monotonically non-decreasing
            for i in range(len(messages) - 1):
                assert messages[i].created_at <= messages[i + 1].created_at, (
                    f"Message ordering violated: "
                    f"Message {messages[i].id} at {messages[i].created_at} "
                    f"appears before message {messages[i + 1].id} at {messages[i + 1].created_at}"
                )


# Run the stateful test
TestChatMessageOrdering = ChatMessageOrderingStateMachine.TestCase


@given(
    num_messages=st.integers(min_value=2, max_value=20),
    content_list=st.lists(message_content_strategy, min_size=2, max_size=20)
)
@settings(max_examples=50, deadline=None)
def test_message_ordering_property(num_messages, content_list):
    """
    Property test: Messages are always returned in chronological order.
    
    This test creates a session with multiple messages and verifies that
    when queried, they are returned in ascending order by created_at.
    """
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Create athlete
        athlete = Athlete(
            name="Test Athlete",
            email="test@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(athlete)
        db.commit()
        
        # Create session
        session = ChatSession(
            athlete_id=athlete.id,
            title="Test Session",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        
        # Add messages with incrementing timestamps
        base_time = datetime.utcnow()
        for i in range(min(num_messages, len(content_list))):
            message = ChatMessage(
                session_id=session.id,
                role='user' if i % 2 == 0 else 'assistant',
                content=content_list[i],
                created_at=base_time + timedelta(seconds=i)
            )
            db.add(message)
        db.commit()
        
        # Query messages
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        # Verify ordering property
        for i in range(len(messages) - 1):
            assert messages[i].created_at <= messages[i + 1].created_at, (
                f"Message ordering violated at index {i}: "
                f"{messages[i].created_at} > {messages[i + 1].created_at}"
            )
        
        # Verify that the order matches insertion order (since we used sequential timestamps)
        for i, message in enumerate(messages):
            expected_time = base_time + timedelta(seconds=i)
            assert message.created_at == expected_time, (
                f"Message {i} has unexpected timestamp: "
                f"expected {expected_time}, got {message.created_at}"
            )
    
    finally:
        db.close()
        engine.dispose()
        os.close(db_fd)
        try:
            os.unlink(db_path)
        except PermissionError:
            # On Windows, file may still be locked
            pass


@given(
    num_sessions=st.integers(min_value=1, max_value=5),
    messages_per_session=st.integers(min_value=2, max_value=10)
)
@settings(max_examples=30, deadline=None)
def test_multiple_sessions_ordering(num_sessions, messages_per_session):
    """
    Property test: Message ordering is maintained across multiple sessions.
    
    This test verifies that each session maintains its own message ordering
    independently of other sessions.
    """
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Create athlete
        athlete = Athlete(
            name="Test Athlete",
            email="test@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(athlete)
        db.commit()
        
        # Create multiple sessions with messages
        for session_num in range(num_sessions):
            session = ChatSession(
                athlete_id=athlete.id,
                title=f"Test Session {session_num}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(session)
            db.commit()
            
            # Add messages to this session
            base_time = datetime.utcnow()
            for msg_num in range(messages_per_session):
                message = ChatMessage(
                    session_id=session.id,
                    role='user' if msg_num % 2 == 0 else 'assistant',
                    content=f"Message {msg_num} in session {session_num}",
                    created_at=base_time + timedelta(seconds=msg_num)
                )
                db.add(message)
            db.commit()
        
        # Verify ordering for each session
        sessions = db.query(ChatSession).all()
        for session in sessions:
            messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            # Check ordering property
            for i in range(len(messages) - 1):
                assert messages[i].created_at <= messages[i + 1].created_at, (
                    f"Session {session.id} message ordering violated at index {i}"
                )
    
    finally:
        db.close()
        engine.dispose()
        os.close(db_fd)
        try:
            os.unlink(db_path)
        except PermissionError:
            # On Windows, file may still be locked
            pass


def test_concurrent_message_insertion():
    """
    Test that messages inserted with the same timestamp maintain database order.
    
    This edge case tests what happens when multiple messages have identical
    timestamps (which could happen in high-frequency scenarios).
    """
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Create athlete
        athlete = Athlete(
            name="Test Athlete",
            email="test@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(athlete)
        db.commit()
        
        # Create session
        session = ChatSession(
            athlete_id=athlete.id,
            title="Concurrent Test Session",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        
        # Add multiple messages with the same timestamp
        same_time = datetime.utcnow()
        for i in range(5):
            message = ChatMessage(
                session_id=session.id,
                role='user' if i % 2 == 0 else 'assistant',
                content=f"Concurrent message {i}",
                created_at=same_time
            )
            db.add(message)
        db.commit()
        
        # Query messages
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()
        
        # Verify all messages have the same timestamp
        for message in messages:
            assert message.created_at == same_time
        
        # Verify ordering by ID (insertion order) when timestamps are equal
        for i in range(len(messages) - 1):
            assert messages[i].id < messages[i + 1].id, (
                f"Messages with same timestamp not ordered by ID: "
                f"{messages[i].id} >= {messages[i + 1].id}"
            )
    
    finally:
        db.close()
        engine.dispose()
        os.close(db_fd)
        try:
            os.unlink(db_path)
        except PermissionError:
            # On Windows, file may still be locked
            pass


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--hypothesis-show-statistics'])
