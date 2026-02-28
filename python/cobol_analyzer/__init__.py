"""
cobol_analyzer -- Static analysis tools for legacy COBOL spaghetti code.

This package provides analysis capabilities that make an LLM genuinely better
at understanding messy COBOL than any vanilla model. The key insight: an LLM
cannot reliably trace GO TO chains across 500 lines, but our tools can do it
deterministically and feed the results back as structured context.

Modules:
    call_graph     -- Paragraph dependency graph (PERFORM, GO TO, ALTER, fall-through)
    data_flow      -- Field read/write tracking per paragraph
    dead_code      -- Unreachable paragraph detection
    complexity     -- Per-paragraph complexity scoring
    knowledge_base -- COBOL pattern/idiom/anti-pattern encyclopedia
"""

from .call_graph import CallGraphAnalyzer
from .data_flow import DataFlowAnalyzer
from .dead_code import DeadCodeAnalyzer
from .complexity import ComplexityAnalyzer
from .knowledge_base import KnowledgeBase

__all__ = [
    "CallGraphAnalyzer",
    "DataFlowAnalyzer",
    "DeadCodeAnalyzer",
    "ComplexityAnalyzer",
    "KnowledgeBase",
]
