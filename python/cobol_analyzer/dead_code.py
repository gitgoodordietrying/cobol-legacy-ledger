"""
dead_code -- Unreachable paragraph detection in COBOL programs.

Classifies every paragraph as:
    REACHABLE        -- Can be reached from the entry point
    DEAD             -- Cannot be reached by any PERFORM, GO TO, or fall-through
    ALTER_CONDITIONAL -- Reachable ONLY through ALTER-modified GO TO targets
                        (may or may not execute depending on runtime ALTER state)

Dead paragraphs are extremely common in legacy COBOL — they accumulate over
decades as features are "disabled" by removing the PERFORM call but leaving
the paragraph in place. Removing dead code requires a change request, testing,
and sign-off, so it's universally considered "safer" to leave it.
"""

import re
from typing import Dict, List, Set
from dataclasses import dataclass, field as dc_field
from .call_graph import CallGraphAnalyzer, CallGraph


@dataclass
class DeadCodeResult:
    """Classification of all paragraphs by reachability."""
    reachable: Set[str] = dc_field(default_factory=set)
    dead: Set[str] = dc_field(default_factory=set)
    alter_conditional: Set[str] = dc_field(default_factory=set)
    entry_point: str = ""

    def to_dict(self) -> Dict:
        return {
            "reachable": sorted(self.reachable),
            "dead": sorted(self.dead),
            "alter_conditional": sorted(self.alter_conditional),
            "entry_point": self.entry_point,
            "total_paragraphs": len(self.reachable) + len(self.dead) + len(self.alter_conditional),
            "dead_count": len(self.dead),
            "alter_conditional_count": len(self.alter_conditional),
        }


class DeadCodeAnalyzer:
    """Detects unreachable paragraphs in COBOL programs."""

    def __init__(self):
        self._cg_analyzer = CallGraphAnalyzer()

    def analyze(self, source: str, entry_point: str = None) -> DeadCodeResult:
        """Classify all paragraphs by reachability.

        :param source: COBOL source text
        :param entry_point: Entry paragraph name (defaults to first paragraph)
        """
        graph = self._cg_analyzer.analyze(source)
        result = DeadCodeResult()

        if not graph.paragraph_order:
            return result

        # Default entry point is first paragraph
        if entry_point is None:
            entry_point = graph.paragraph_order[0]
        result.entry_point = entry_point

        # Phase 1: Find paragraphs reachable WITHOUT ALTER
        reachable_no_alter = self._find_reachable(graph, entry_point, include_alter=False)

        # Phase 2: Find paragraphs reachable WITH ALTER
        reachable_with_alter = self._find_reachable(graph, entry_point, include_alter=True)

        # Phase 3: Classify
        all_paras = set(graph.paragraphs.keys())
        result.reachable = reachable_no_alter
        result.alter_conditional = reachable_with_alter - reachable_no_alter
        result.dead = all_paras - reachable_with_alter

        return result

    def _find_reachable(self, graph: CallGraph, entry: str,
                        include_alter: bool) -> Set[str]:
        """BFS to find all reachable paragraphs from entry point."""
        visited = set()
        queue = [entry]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            if current not in graph.paragraphs:
                continue
            visited.add(current)

            for edge in graph.get_edges_from(current):
                if edge.edge_type == "ALTER" and not include_alter:
                    continue
                if edge.target not in visited:
                    queue.append(edge.target)

            # For PERFORM THRU, also mark intervening paragraphs
            for edge in graph.get_edges_from(current):
                if edge.edge_type == "PERFORM_THRU":
                    if edge.target not in visited:
                        queue.append(edge.target)

        return visited
