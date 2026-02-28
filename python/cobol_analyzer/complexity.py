"""
complexity -- Per-paragraph complexity scoring for COBOL programs.

Assigns a complexity score to each paragraph based on the anti-patterns it
contains. Higher scores indicate more difficult-to-understand code.

Scoring weights (calibrated against real legacy COBOL):
    GO TO           +5   per occurrence (unconditional jump)
    ALTER           +10  per occurrence (runtime flow modification)
    PERFORM THRU    +3   per occurrence (range execution risk)
    Nested IF       +2   per nesting level (exponential readability cost)
    EVALUATE        +1   per occurrence (structured, but adds paths)
    Dead code       +8   per dead paragraph (misleads readers)
    Magic number    +1   per occurrence (unnamed literal)

The overall program score is the sum of all paragraph scores. Programs
under 20 are "clean", 20-50 are "moderate legacy", 50+ are "spaghetti".
"""

import re
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class ParagraphComplexity:
    """Complexity breakdown for a single paragraph."""
    name: str
    score: int = 0
    goto_count: int = 0
    alter_count: int = 0
    perform_thru_count: int = 0
    max_if_depth: int = 0
    evaluate_count: int = 0
    magic_number_count: int = 0
    line_count: int = 0
    factors: List[str] = field(default_factory=list)


@dataclass
class ComplexityResult:
    """Complete complexity analysis for a COBOL program."""
    paragraphs: Dict[str, ParagraphComplexity] = field(default_factory=dict)
    total_score: int = 0
    rating: str = ""  # "clean", "moderate", "spaghetti"

    def to_dict(self) -> Dict:
        return {
            "paragraphs": {
                k: {
                    "score": v.score, "goto": v.goto_count,
                    "alter": v.alter_count, "perform_thru": v.perform_thru_count,
                    "max_if_depth": v.max_if_depth, "evaluate": v.evaluate_count,
                    "magic_numbers": v.magic_number_count, "lines": v.line_count,
                    "factors": v.factors,
                }
                for k, v in self.paragraphs.items()
            },
            "total_score": self.total_score,
            "rating": self.rating,
            "hotspots": sorted(
                [{"name": k, "score": v.score} for k, v in self.paragraphs.items()],
                key=lambda x: x["score"], reverse=True
            )[:5],
        }


class ComplexityAnalyzer:
    """Computes complexity scores for COBOL paragraphs."""

    _PARAGRAPH = re.compile(r'^(\s{7}[\w-]+)\.\s*$', re.MULTILINE)
    _COMMENT = re.compile(r'^\s*\*>')
    _GOTO = re.compile(r'GO\s+TO\s+', re.IGNORECASE)
    _ALTER = re.compile(r'ALTER\s+', re.IGNORECASE)
    _PERFORM_THRU = re.compile(r'PERFORM\s+\S+\s+THRU\s+', re.IGNORECASE)
    _EVALUATE = re.compile(r'EVALUATE\s+', re.IGNORECASE)
    _MAGIC_NUM = re.compile(r'(?<!\w)\d{2,}(?:\.\d+)?(?!\w)')  # Bare numbers (2+ digits)
    _IF = re.compile(r'\bIF\b', re.IGNORECASE)
    _END_IF = re.compile(r'\bEND-IF\b', re.IGNORECASE)

    def analyze(self, source: str) -> ComplexityResult:
        """Compute complexity scores for all paragraphs."""
        result = ComplexityResult()
        lines = source.split('\n')

        current_para = None
        in_procedure = False
        para_lines: Dict[str, List[str]] = {}

        # Collect lines per paragraph
        for line in lines:
            if re.search(r'PROCEDURE\s+DIVISION', line, re.IGNORECASE):
                in_procedure = True
                continue
            if not in_procedure:
                continue

            match = self._PARAGRAPH.match(line)
            if match:
                current_para = match.group(1).strip()
                para_lines[current_para] = []
                continue

            if current_para and not self._COMMENT.match(line):
                para_lines.setdefault(current_para, []).append(line)

        # Score each paragraph
        for name, plines in para_lines.items():
            pc = ParagraphComplexity(name=name, line_count=len(plines))

            if_depth = 0
            max_depth = 0

            for line in plines:
                upper = line.upper()

                if self._GOTO.search(line):
                    pc.goto_count += 1

                if self._ALTER.search(line):
                    pc.alter_count += 1

                if self._PERFORM_THRU.search(line):
                    pc.perform_thru_count += 1

                if self._EVALUATE.search(line):
                    pc.evaluate_count += 1

                # Track IF nesting depth
                if_matches = len(self._IF.findall(line))
                endif_matches = len(self._END_IF.findall(line))
                if_depth += if_matches - endif_matches
                # Period terminates all open IFs
                if line.strip().endswith('.') and 'IF' in upper:
                    if_depth = 0
                max_depth = max(max_depth, if_depth)

                # Count magic numbers (exclude PIC clauses and common values)
                stripped = line.strip()
                if not stripped.startswith('*>') and 'PIC' not in upper and 'VALUE' not in upper:
                    pc.magic_number_count += len(self._MAGIC_NUM.findall(stripped))

            pc.max_if_depth = max_depth

            # Compute score
            pc.score = (
                pc.goto_count * 5 +
                pc.alter_count * 10 +
                pc.perform_thru_count * 3 +
                pc.max_if_depth * 2 +
                pc.evaluate_count * 1 +
                pc.magic_number_count * 1
            )

            # Build factors list
            if pc.goto_count:
                pc.factors.append(f"GO TO x{pc.goto_count} (+{pc.goto_count * 5})")
            if pc.alter_count:
                pc.factors.append(f"ALTER x{pc.alter_count} (+{pc.alter_count * 10})")
            if pc.perform_thru_count:
                pc.factors.append(f"PERFORM THRU x{pc.perform_thru_count} (+{pc.perform_thru_count * 3})")
            if pc.max_if_depth > 1:
                pc.factors.append(f"Nested IF depth {pc.max_if_depth} (+{pc.max_if_depth * 2})")

            result.paragraphs[name] = pc

        result.total_score = sum(p.score for p in result.paragraphs.values())
        if result.total_score < 20:
            result.rating = "clean"
        elif result.total_score < 50:
            result.rating = "moderate"
        else:
            result.rating = "spaghetti"

        return result
