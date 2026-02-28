"""
call_graph -- Paragraph dependency graph with edge type classification.

Builds a directed graph of paragraph relationships from COBOL source code.
Edge types:
    PERFORM     -- Structured call (PERFORM paragraph-name)
    PERFORM_THRU -- Range execution (PERFORM A THRU B)
    GOTO        -- Unconditional jump (GO TO paragraph-name)
    ALTER       -- Runtime-modified jump target (ALTER P-030 TO PROCEED TO P-040)
    FALL_THROUGH -- Sequential execution into next paragraph

The trace_execution() method is the killer feature: given an entry point,
it follows the execution path through GO TO chains and ALTER modifications,
returning the ordered sequence of paragraphs that will execute. No vanilla
LLM can do this reliably across 500 lines of spaghetti.
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class Edge:
    """A directed edge in the call graph."""
    source: str       # Source paragraph
    target: str       # Target paragraph
    edge_type: str    # PERFORM, PERFORM_THRU, GOTO, ALTER, FALL_THROUGH
    line_number: int = 0
    condition: str = ""  # Non-empty if edge is conditional (inside IF/EVALUATE)


@dataclass
class ParagraphInfo:
    """Information about a single paragraph."""
    name: str
    start_line: int
    end_line: int = 0
    statements: List[str] = field(default_factory=list)


@dataclass
class CallGraph:
    """Complete call graph for a COBOL program."""
    paragraphs: Dict[str, ParagraphInfo] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    alter_targets: Dict[str, List[str]] = field(default_factory=dict)
    # Maps paragraph names to their order of appearance
    paragraph_order: List[str] = field(default_factory=list)

    def get_edges_from(self, paragraph: str) -> List[Edge]:
        return [e for e in self.edges if e.source == paragraph]

    def get_edges_to(self, paragraph: str) -> List[Edge]:
        return [e for e in self.edges if e.target == paragraph]

    def to_dict(self) -> Dict:
        return {
            "paragraphs": list(self.paragraphs.keys()),
            "edges": [
                {"source": e.source, "target": e.target, "type": e.edge_type,
                 "line": e.line_number, "condition": e.condition}
                for e in self.edges
            ],
            "alter_targets": self.alter_targets,
            "paragraph_count": len(self.paragraphs),
            "edge_count": len(self.edges),
        }


class CallGraphAnalyzer:
    """Builds call graphs from COBOL source text."""

    # Regex patterns for control flow statements
    _PARAGRAPH = re.compile(r'^(\s{7}[\w-]+)\.\s*$', re.MULTILINE)
    _PERFORM = re.compile(r'PERFORM\s+([\w-]+)', re.IGNORECASE)
    _PERFORM_THRU = re.compile(r'PERFORM\s+([\w-]+)\s+THRU\s+([\w-]+)', re.IGNORECASE)
    _GOTO = re.compile(r'GO\s+TO\s+([\w-]+)', re.IGNORECASE)
    _ALTER = re.compile(r'ALTER\s+([\w-]+)\s+TO\s+PROCEED\s+TO\s+([\w-]+)', re.IGNORECASE)
    _COMMENT = re.compile(r'^\s*\*>')

    def analyze(self, source: str) -> CallGraph:
        """Build a call graph from COBOL source text."""
        graph = CallGraph()
        lines = source.split('\n')

        # Phase 1: Identify all paragraphs and their line ranges
        self._find_paragraphs(lines, graph)

        # Phase 2: Analyze each paragraph for control flow
        self._find_edges(lines, graph)

        # Phase 3: Detect fall-through between adjacent paragraphs
        self._find_fall_throughs(lines, graph)

        return graph

    def _find_paragraphs(self, lines: List[str], graph: CallGraph):
        """Identify paragraph boundaries."""
        in_procedure = False
        para_names = []

        for i, line in enumerate(lines):
            if re.search(r'PROCEDURE\s+DIVISION', line, re.IGNORECASE):
                in_procedure = True
                continue

            if not in_procedure:
                continue

            if self._COMMENT.match(line):
                continue

            match = self._PARAGRAPH.match(line)
            if match:
                name = match.group(1).strip()
                info = ParagraphInfo(name=name, start_line=i + 1)
                graph.paragraphs[name] = info
                para_names.append(name)

        # Set end lines based on next paragraph start
        for idx, name in enumerate(para_names):
            if idx + 1 < len(para_names):
                graph.paragraphs[name].end_line = graph.paragraphs[para_names[idx + 1]].start_line - 1
            else:
                graph.paragraphs[name].end_line = len(lines)

        graph.paragraph_order = para_names

    def _find_edges(self, lines: List[str], graph: CallGraph):
        """Find PERFORM, GO TO, and ALTER edges."""
        current_para = None
        in_condition = False

        for i, line in enumerate(lines):
            if self._COMMENT.match(line):
                continue

            # Check if we're in a new paragraph
            match = self._PARAGRAPH.match(line)
            if match:
                current_para = match.group(1).strip()
                in_condition = False
                continue

            if current_para is None:
                continue

            upper_line = line.upper().strip()

            # Track if we're inside a conditional
            if 'IF ' in upper_line and not upper_line.startswith('END-IF'):
                in_condition = True
            if 'END-IF' in upper_line or upper_line.endswith('.'):
                in_condition = False

            # ALTER (must check before PERFORM/GOTO since it contains "TO")
            alter_match = self._ALTER.search(line)
            if alter_match:
                from_para = alter_match.group(1)
                to_para = alter_match.group(2)
                graph.edges.append(Edge(
                    source=current_para, target=to_para,
                    edge_type="ALTER", line_number=i + 1,
                ))
                if from_para not in graph.alter_targets:
                    graph.alter_targets[from_para] = []
                graph.alter_targets[from_para].append(to_para)
                continue

            # PERFORM THRU (must check before plain PERFORM)
            thru_match = self._PERFORM_THRU.search(line)
            if thru_match:
                start_para = thru_match.group(1)
                end_para = thru_match.group(2)
                graph.edges.append(Edge(
                    source=current_para, target=start_para,
                    edge_type="PERFORM_THRU", line_number=i + 1,
                    condition="conditional" if in_condition else "",
                ))
                # Also add edges to all paragraphs in the THRU range
                in_range = False
                for name in graph.paragraph_order:
                    if name == start_para:
                        in_range = True
                    if in_range and name != start_para:
                        graph.edges.append(Edge(
                            source=current_para, target=name,
                            edge_type="PERFORM_THRU", line_number=i + 1,
                        ))
                    if name == end_para:
                        break
                continue

            # Plain PERFORM
            perform_match = self._PERFORM.search(line)
            if perform_match:
                target = perform_match.group(1)
                if target.upper() not in ('UNTIL', 'VARYING', 'WITH', 'TEST'):
                    graph.edges.append(Edge(
                        source=current_para, target=target,
                        edge_type="PERFORM", line_number=i + 1,
                        condition="conditional" if in_condition else "",
                    ))
                continue

            # GO TO
            goto_match = self._GOTO.search(line)
            if goto_match:
                target = goto_match.group(1)
                graph.edges.append(Edge(
                    source=current_para, target=target,
                    edge_type="GOTO", line_number=i + 1,
                    condition="conditional" if in_condition else "",
                ))

    def _find_fall_throughs(self, lines: List[str], graph: CallGraph):
        """Detect fall-through between adjacent paragraphs.

        A paragraph falls through to the next if its last statement is
        not a GO TO or STOP RUN.
        """
        for idx in range(len(graph.paragraph_order) - 1):
            name = graph.paragraph_order[idx]
            next_name = graph.paragraph_order[idx + 1]
            info = graph.paragraphs[name]

            # Check if last effective statement is GO TO or STOP RUN
            last_stmt = ""
            for line_num in range(info.end_line - 1, info.start_line - 1, -1):
                if line_num < len(lines):
                    line = lines[line_num].strip()
                    if line and not line.startswith('*>') and line != '.':
                        last_stmt = line.upper()
                        break

            has_goto = bool(self._GOTO.search(last_stmt))
            has_stop = 'STOP RUN' in last_stmt
            has_exit = last_stmt.strip() == 'EXIT.'

            if not has_goto and not has_stop and not has_exit:
                graph.edges.append(Edge(
                    source=name, target=next_name,
                    edge_type="FALL_THROUGH", line_number=info.end_line,
                ))

    def trace_execution(self, source: str, entry_point: str,
                        max_steps: int = 100) -> List[Dict]:
        """Trace execution path from an entry point through GO TO chains.

        This is the KILLER FEATURE. Given an entry paragraph, follows
        the execution flow through GO TO, ALTER modifications, and
        PERFORM THRU ranges, returning the ordered sequence.

        Returns a list of dicts: [{"paragraph": name, "step": n, "via": edge_type}]

        The max_steps limit prevents infinite loops in circular GO TO chains.
        """
        graph = self.analyze(source)
        path = []
        visited_count: Dict[str, int] = {}
        current = entry_point
        step = 0

        # Track ALTER state (runtime GO TO target modifications)
        alter_state: Dict[str, str] = {}
        for para, targets in graph.alter_targets.items():
            if targets:
                alter_state[para] = targets[0]  # First ALTER target

        while current and step < max_steps:
            # Record this step
            path.append({
                "paragraph": current,
                "step": step,
                "via": "entry" if step == 0 else path[-1].get("next_via", "sequential"),
            })

            visited_count[current] = visited_count.get(current, 0) + 1
            if visited_count[current] > 3:
                path[-1]["note"] = "loop detected — visited 3+ times"
                break

            # Find outgoing edges from current paragraph
            edges = graph.get_edges_from(current)
            goto_edges = [e for e in edges if e.edge_type == "GOTO"]
            fallthrough_edges = [e for e in edges if e.edge_type == "FALL_THROUGH"]

            # Check if this paragraph has an ALTER-modified GO TO
            if current in alter_state:
                next_para = alter_state[current]
                path[-1]["next_via"] = "ALTER→GOTO"
                current = next_para
                step += 1
                continue

            # Follow GO TO (first unconditional one)
            unconditional_gotos = [e for e in goto_edges if not e.condition]
            if unconditional_gotos:
                edge = unconditional_gotos[0]
                path[-1]["next_via"] = "GOTO"
                current = edge.target
                step += 1
                continue

            # Follow fall-through
            if fallthrough_edges:
                edge = fallthrough_edges[0]
                path[-1]["next_via"] = "FALL_THROUGH"
                current = edge.target
                step += 1
                continue

            # No outgoing edges — execution ends
            path[-1]["note"] = "execution ends (STOP RUN or EXIT)"
            break

            step += 1

        return path
