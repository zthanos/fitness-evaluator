"""Chat context builder for coach chat operations."""

from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.ai.context.builder import ContextBuilder, Context, ContextBudgetExceeded
from app.ai.retrieval.intent_router import IntentRouter
from app.ai.retrieval.rag_retriever import RAGRetriever


class ChatContextBuilder(ContextBuilder):
    """Context builder for coach chat operations."""

    def __init__(
        self,
        db: Session,
        token_budget: int = 32000,
        history_selection_policy: str = "last_n_turns",
        last_n_turns: int = 5,
        relevance_threshold: float = 0.7,
    ):
        """
        Initialize chat context builder.

        Args:
            db: SQLAlchemy database session
            token_budget: Maximum token count for context (default: 2400)
            history_selection_policy: Policy for selecting conversation history
                                     Options: "last_n_turns", "relevance", "token_aware"
            last_n_turns: Number of recent turns to include (default: 5)
            relevance_threshold: Minimum similarity score for relevance-based selection (default: 0.7)
        """
        super().__init__(token_budget)
        self.db = db
        self.intent_router = IntentRouter()

        # Allocate ~25% of token budget for retrieved data (600 tokens out of 2400)
        retrieval_budget = int(token_budget * 0.25)
        self.rag_retriever = RAGRetriever(db, token_budget_for_retrieval=retrieval_budget)

        self.history_selection_policy = history_selection_policy
        self.last_n_turns = last_n_turns
        self.relevance_threshold = relevance_threshold

        # Last classified intent — set by gather_data(), read by ChatAgent
        self.last_intent = None

        # Layer-by-layer token tracking
        self._layer_tokens: Dict[str, int] = {
            "system_instructions": 0,
            "task_instructions": 0,
            "domain_knowledge": 0,
            "athlete_summary": 0,
            "retrieved_data": 0,
            "conversation_history": 0,
        }

    def gather_data(
        self,
        query: str,
        athlete_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        intent=None,
    ) -> 'ChatContextBuilder':
        """
        Gather data for chat response using intent-aware retrieval.

        Args:
            query: User query string
            athlete_id: Athlete ID for filtering
            conversation_history: Optional list of previous messages
                                 Format: [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            Self for method chaining
        """
        # Accept a pre-classified intent (LLM-based) or fall back to keyword matching
        if intent is None:
            intent = self.intent_router.classify(query)
        self.last_intent = intent

        # Retrieve relevant data using intent-specific policy
        retrieved_data = self.rag_retriever.retrieve(
            query=query,
            athlete_id=athlete_id,
            intent=intent,
            generate_cards=True  # Generate evidence cards
        )

        # Add retrieved data to context
        self.add_retrieved_data(retrieved_data)

        # Select relevant conversation history if provided
        if conversation_history:
            selected_history = self.select_relevant_history(
                conversation_history=conversation_history,
                current_query=query
            )
            self.add_conversation_history(selected_history)

        return self

    def select_relevant_history(
        self,
        conversation_history: List[Dict[str, str]],
        current_query: str
    ) -> List[Dict[str, str]]:
        """
        Select relevant conversation history based on configured policy.

        Args:
            conversation_history: Full conversation history
                                 Format: [{"role": "user"|"assistant", "content": "..."}]
            current_query: Current user query for relevance calculation

        Returns:
            Selected conversation history based on policy
        """
        if not conversation_history:
            return []

        # Apply selection policy
        if self.history_selection_policy == "last_n_turns":
            return self._select_last_n_turns(conversation_history)
        elif self.history_selection_policy == "relevance":
            return self._select_by_relevance(conversation_history, current_query)
        elif self.history_selection_policy == "token_aware":
            return self._select_token_aware(conversation_history)
        else:
            # Default to last_n_turns
            return self._select_last_n_turns(conversation_history)

    def _select_last_n_turns(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Select last N conversation turns.

        A "turn" is a user message + assistant response pair.

        Args:
            conversation_history: Full conversation history

        Returns:
            Last N turns from conversation
        """
        if not conversation_history:
            return []

        # Calculate number of messages for N turns (2 messages per turn)
        num_messages = self.last_n_turns * 2

        # Return last N turns
        return conversation_history[-num_messages:]

    def _select_by_relevance(
        self,
        conversation_history: List[Dict[str, str]],
        current_query: str
    ) -> List[Dict[str, str]]:
        """
        Select conversation history based on semantic relevance to current query.

        Uses embeddings to calculate similarity between current query and past messages.
        Always includes the most recent turn, then adds relevant past turns.

        Args:
            conversation_history: Full conversation history
            current_query: Current user query

        Returns:
            Relevant conversation history (most recent + semantically similar)
        """
        if not conversation_history:
            return []

        # Always include the most recent turn (last 2 messages)
        recent_turn = conversation_history[-2:] if len(conversation_history) >= 2 else conversation_history

        # If history is short, return all
        if len(conversation_history) <= 4:  # 2 turns or less
            return conversation_history

        # Get embeddings for current query
        try:
            from app.services.rag_engine import RAGEngine
            rag_engine = RAGEngine(self.db)
            query_embedding = rag_engine.generate_embedding(current_query)

            # Calculate relevance scores for past turns (excluding most recent)
            past_history = conversation_history[:-2]
            scored_messages = []

            # Process messages in pairs (turns)
            for i in range(0, len(past_history), 2):
                # Get user message from this turn
                if i < len(past_history):
                    user_msg = past_history[i]
                    if user_msg.get("role") == "user":
                        # Generate embedding for user message
                        msg_embedding = rag_engine.generate_embedding(user_msg["content"])

                        # Calculate cosine similarity
                        import numpy as np
                        similarity = np.dot(query_embedding, msg_embedding)

                        # Store turn with score
                        turn_messages = past_history[i:i + 2]  # User + assistant
                        scored_messages.append((similarity, turn_messages))

            # Filter by relevance threshold and sort by score
            relevant_turns = [
                turn for score, turn in scored_messages
                if score >= self.relevance_threshold
            ]
            relevant_turns.sort(key=lambda x: scored_messages[relevant_turns.index(x)][0], reverse=True)

            # Flatten relevant turns and combine with recent turn
            selected_history = []
            for turn in relevant_turns[:self.last_n_turns - 1]:  # Reserve 1 slot for recent turn
                selected_history.extend(turn)

            # Add most recent turn at the end
            selected_history.extend(recent_turn)

            return selected_history

        except Exception as e:
            # Fallback to last_n_turns on error
            print(f"[ChatContextBuilder] Error in relevance-based selection: {e}")
            return self._select_last_n_turns(conversation_history)

    def _select_token_aware(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Select conversation history with token budget awareness.

        Starts with most recent messages and adds older messages until
        token budget would be exceeded. Trims oldest messages first.

        Args:
            conversation_history: Full conversation history

        Returns:
            Token-aware selected conversation history
        """
        if not conversation_history:
            return []

        # Reserve tokens for other context layers (rough estimate)
        # System: 300, Task: 150, Domain: 200, Retrieved: 500, Athlete: 200
        reserved_tokens = 1350
        available_tokens = self.token_budget - reserved_tokens

        # Start from most recent and work backwards
        selected_history = []
        current_tokens = 0

        for message in reversed(conversation_history):
            # Estimate tokens for this message
            message_tokens = len(self.encoding.encode(message["content"])) + 4

            # Check if adding this message would exceed budget
            if current_tokens + message_tokens > available_tokens:
                break

            # Add message to front of selected history
            selected_history.insert(0, message)
            current_tokens += message_tokens

        return selected_history

    def _count_layer_tokens(self, content: str) -> int:
        """
        Count tokens in a content string.

        Args:
            content: Content string to count tokens for

        Returns:
            Token count including message formatting overhead
        """
        if not content:
            return 0
        return len(self.encoding.encode(content)) + 4

    def _count_dict_tokens(self, data: Dict[str, Any]) -> int:
        """
        Count tokens in a dictionary (for domain knowledge, etc.).

        Handles nested custom objects (dataclasses) by converting them
        to dicts via to_dict() or dataclasses.asdict() before serialization.

        Args:
            data: Dictionary to count tokens for

        Returns:
            Token count for JSON representation
        """
        if not data:
            return 0
        import json
        from dataclasses import asdict, fields as dc_fields

        def _make_serializable(obj):
            """Recursively convert non-serializable objects to dicts."""
            if isinstance(obj, dict):
                return {k: _make_serializable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_make_serializable(item) for item in obj]
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            try:
                dc_fields(obj)
                return asdict(obj)
            except TypeError:
                return obj

        serializable_data = _make_serializable(data)
        json_str = json.dumps(serializable_data, indent=2)
        return len(self.encoding.encode(json_str)) + 4

    def _count_list_tokens(self, data: List[Dict[str, Any]]) -> int:
        """
        Count tokens in a list of dictionaries (for retrieved data, etc.).

        Args:
            data: List of dictionaries to count tokens for

        Returns:
            Token count for JSON representation
        """
        if not data:
            return 0
        import json
        json_str = json.dumps(data, indent=2)
        return len(self.encoding.encode(json_str)) + 4

    def _count_history_tokens(self, history: List[Dict[str, str]]) -> int:
        """
        Count tokens in conversation history.

        Args:
            history: List of conversation messages

        Returns:
            Total token count for all messages
        """
        if not history:
            return 0
        total = 0
        for message in history:
            total += len(self.encoding.encode(message.get("content", ""))) + 4
        return total

    def get_layer_tokens(self) -> Dict[str, int]:
        """
        Get token counts for each context layer.

        Returns:
            Dictionary mapping layer names to token counts
        """
        return self._layer_tokens.copy()

    def get_total_tokens(self) -> int:
        """
        Get total token count across all layers.

        Returns:
            Sum of all layer token counts
        """
        return sum(self._layer_tokens.values())

    def get_available_tokens(self) -> int:
        """
        Get remaining tokens available in budget.

        Returns:
            Tokens remaining (budget - used)
        """
        return self.token_budget - self.get_total_tokens()

    def add_system_instructions(self, instructions: str) -> 'ChatContextBuilder':
        """
        Add system instructions layer with token tracking.

        Args:
            instructions: System instructions text

        Returns:
            Self for method chaining
        """
        super().add_system_instructions(instructions)
        self._layer_tokens["system_instructions"] = self._count_layer_tokens(instructions)
        return self

    def add_task_instructions(self, instructions: str) -> 'ChatContextBuilder':
        """
        Add task instructions layer with token tracking.

        Args:
            instructions: Task instructions text

        Returns:
            Self for method chaining
        """
        super().add_task_instructions(instructions)
        self._layer_tokens["task_instructions"] = self._count_layer_tokens(instructions)
        return self

    def add_domain_knowledge(self, knowledge: Dict[str, Any]) -> 'ChatContextBuilder':
        """
        Add domain knowledge layer with token tracking.

        Args:
            knowledge: Domain knowledge dictionary

        Returns:
            Self for method chaining
        """
        super().add_domain_knowledge(knowledge)
        self._layer_tokens["domain_knowledge"] = self._count_dict_tokens(knowledge)
        return self

    def add_retrieved_data(self, data: List[Dict[str, Any]]) -> 'ChatContextBuilder':
        """
        Add retrieved data layer with token tracking.

        Args:
            data: List of retrieved data items

        Returns:
            Self for method chaining
        """
        super().add_retrieved_data(data)
        # Recalculate total for retrieved data (since it extends)
        self._layer_tokens["retrieved_data"] = self._count_list_tokens(self._retrieved_data)
        return self

    def add_conversation_history(self, history: List[Dict[str, str]]) -> 'ChatContextBuilder':
        """
        Add conversation history layer with token tracking.

        Args:
            history: List of conversation messages

        Returns:
            Self for method chaining
        """
        super().add_conversation_history(history)
        self._layer_tokens["conversation_history"] = self._count_history_tokens(history)
        return self

    def add_athlete_summary(self, summary: str) -> 'ChatContextBuilder':
        """
        Add athlete behavior summary layer with token tracking.

        Args:
            summary: Athlete behavior summary text

        Returns:
            Self for method chaining
        """
        # Store in domain knowledge or as separate field
        if not self._domain_knowledge:
            self._domain_knowledge = {}
        self._domain_knowledge["athlete_summary"] = summary
        self._layer_tokens["athlete_summary"] = self._count_layer_tokens(summary)
        return self

    def _trim_history_to_budget(self) -> None:
        """
        Trim conversation history to fit within token budget.

        Removes oldest messages first until budget is satisfied.
        Always preserves at least the most recent turn (2 messages).
        """
        if not self._conversation_history:
            return

        # Calculate how many tokens we need to free
        total_tokens = self.get_total_tokens()
        if total_tokens <= self.token_budget:
            return  # Already within budget

        tokens_to_free = total_tokens - self.token_budget

        # Keep track of removed tokens
        freed_tokens = 0

        # Remove messages from the beginning (oldest first)
        # Always keep at least the last 2 messages (most recent turn)
        while len(self._conversation_history) > 2 and freed_tokens < tokens_to_free:
            # Remove oldest message
            removed_message = self._conversation_history.pop(0)
            message_tokens = len(self.encoding.encode(removed_message.get("content", ""))) + 4
            freed_tokens += message_tokens

        # Recalculate history tokens
        self._layer_tokens["conversation_history"] = self._count_history_tokens(self._conversation_history)

    def _trim_retrieved_data_to_budget(self) -> None:
        """
        Trim retrieved data to fit within token budget.

        Removes lowest-relevance items first (items at the end of the list).
        The RAGRetriever already sorts by relevance (highest first), so we
        remove from the end.
        """
        if not self._retrieved_data:
            return

        # Calculate how many tokens we need to free
        total_tokens = self.get_total_tokens()
        if total_tokens <= self.token_budget:
            return  # Already within budget

        tokens_to_free = total_tokens - self.token_budget

        # Keep track of removed tokens
        freed_tokens = 0

        # Remove items from the end (lowest relevance first)
        # Keep at least 1 item if possible
        while len(self._retrieved_data) > 1 and freed_tokens < tokens_to_free:
            # Remove lowest relevance item
            self._retrieved_data.pop()

            # Recalculate tokens for remaining data
            new_tokens = self._count_list_tokens(self._retrieved_data)
            freed_tokens = self._layer_tokens["retrieved_data"] - new_tokens
            self._layer_tokens["retrieved_data"] = new_tokens

    def build(self) -> 'Context':
        """
        Build and validate context with automatic budget enforcement.

        If context exceeds budget, automatically trims in this order:
        1. Oldest conversation history messages
        2. Lowest-relevance retrieved data items

        Never trims:
        - System instructions
        - Task instructions
        - Domain knowledge
        - Athlete summary

        Returns:
            Validated Context object

        Raises:
            ContextBudgetExceeded: If budget cannot be satisfied even after trimming
        """
        # Check if we exceed budget
        total_tokens = self.get_total_tokens()

        if total_tokens > self.token_budget:
            # Try trimming history first
            self._trim_history_to_budget()
            total_tokens = self.get_total_tokens()

            # If still over budget, trim retrieved data
            if total_tokens > self.token_budget:
                self._trim_retrieved_data_to_budget()
                total_tokens = self.get_total_tokens()

            # If still over budget after trimming, raise exception
            if total_tokens > self.token_budget:
                raise ContextBudgetExceeded(
                    actual=total_tokens,
                    budget=self.token_budget
                )

        # Call parent build method
        return super().build()
