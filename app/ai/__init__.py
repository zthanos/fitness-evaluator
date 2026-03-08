"""
Context Engineering (CE) Architecture for AI Subsystem

This module provides a formal architecture for managing AI task data,
behavioral rules, output contracts, and evidence traceability.

Submodules:
- contracts: Pydantic input/output schemas
- prompts: Versioned Jinja2 templates for system and task instructions
- config: YAML configuration files for domain knowledge and model profiles
- context: Context builders for different operations
- retrieval: RAG system and intent routing
- derived: Deterministic metric computation
- adapter: LLM provider abstraction
- tools: LangChain StructuredTools
- validators: Context and output validation
- telemetry: Invocation logging
"""

__version__ = "1.0.0"
