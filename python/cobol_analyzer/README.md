# COBOL Analyzer — Static Analysis for Legacy Spaghetti Code

Static analysis tools that feed structured context to the LLM, making it genuinely better at understanding messy COBOL than any vanilla model.

## The Problem

An LLM cannot reliably trace GO TO chains across 500 lines of spaghetti COBOL. It loses track of ALTER-modified jump targets, misses fall-through paths, and can't determine which paragraphs are dead code. These tools solve that deterministically and feed results back as structured context.

## Modules

| Module | Purpose | Key Method |
|--------|---------|------------|
| `call_graph.py` | Paragraph dependency graph | `analyze()` → CallGraph, `trace_execution()` → ordered path |
| `data_flow.py` | Field read/write tracking | `analyze()` → DataFlowResult, `trace_field()` → single-field trace |
| `dead_code.py` | Unreachable paragraph detection | `analyze()` → DeadCodeResult (REACHABLE/DEAD/ALTER_CONDITIONAL) |
| `complexity.py` | Per-paragraph complexity scoring | `analyze()` → ComplexityResult with rating |
| `knowledge_base.py` | COBOL pattern encyclopedia | `lookup()`, `search()`, `list_patterns()` |

## Edge Types (Call Graph)

| Type | Meaning | Example |
|------|---------|---------|
| `PERFORM` | Structured call | `PERFORM INIT-PARA` |
| `PERFORM_THRU` | Range execution | `PERFORM STEP-A THRU STEP-C` |
| `GOTO` | Unconditional jump | `GO TO P-040` |
| `ALTER` | Runtime-modified target | `ALTER P-010 TO PROCEED TO P-020` |
| `FALL_THROUGH` | Sequential into next paragraph | (no explicit statement) |

## Complexity Scoring

| Pattern | Weight | Rationale |
|---------|--------|-----------|
| GO TO | +5 | Unconditional jump breaks structured flow |
| ALTER | +10 | Runtime flow modification — hardest to trace |
| PERFORM THRU | +3 | Range execution with fall-through risk |
| Nested IF | +2/level | Exponential readability cost |
| EVALUATE | +1 | Structured but adds decision paths |
| Magic number | +1 | Unnamed literal reduces clarity |

**Ratings**: clean (<20), moderate (20–50), spaghetti (50+)

## LLM Tools

Five tools exposed via `python/llm/tools.py`:

1. **analyze_call_graph** — Build paragraph dependency graph
2. **trace_execution** — Follow execution through GO TO/ALTER chains (the killer feature)
3. **analyze_data_flow** — Track field reads/writes per paragraph
4. **detect_dead_code** — Classify paragraphs by reachability
5. **explain_cobol_pattern** — Knowledge base lookup for unfamiliar constructs

## Usage

```python
from python.cobol_analyzer import CallGraphAnalyzer

analyzer = CallGraphAnalyzer()
graph = analyzer.analyze(cobol_source)
path = analyzer.trace_execution(cobol_source, "P-000")
```
