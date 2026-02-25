"""
cobol_codegen -- Bi-directional COBOL source code interface.

This package enables Python to read, parse, generate, and modify COBOL source
code. It is the "bi-directional" complement to bridge.py: while bridge.py
runs COBOL programs and reads their output, cobol_codegen reads and writes
COBOL source code itself.

Architecture:
    ast_nodes.py   — Data classes representing COBOL program structure
    parser.py      — Read .cob/.cpy files into AST nodes
    generator.py   — Emit valid COBOL source from AST nodes
    templates.py   — Factory functions for common program types
    editor.py      — High-level AST edit operations
    validator.py   — Convention checking against project standards

Design note for Layer 3 (LLM integration):
    The AST is the interface between AI and COBOL. An LLM produces
    COBOLProgram objects (structured data), and the generator converts
    them to valid COBOL source. This decouples "understanding COBOL
    structure" from "generating text" -- the LLM doesn't need to know
    about column positions or PIC clause formatting.
"""

from .ast_nodes import (
    COBOLProgram, DataItem, ConditionItem, Paragraph, Statement,
    FileDeclaration, ProgramMetadata,
)
from .parser import COBOLParser
from .generator import COBOLGenerator
from .templates import (
    crud_program, report_program, batch_program, copybook_record,
)
from .editor import COBOLEditor
from .validator import COBOLValidator

__all__ = [
    'COBOLProgram', 'DataItem', 'ConditionItem', 'Paragraph', 'Statement',
    'FileDeclaration', 'ProgramMetadata',
    'COBOLParser', 'COBOLGenerator',
    'crud_program', 'report_program', 'batch_program', 'copybook_record',
    'COBOLEditor', 'COBOLValidator',
]
