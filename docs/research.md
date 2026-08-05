# Autonomous Research Engine

The Research Engine (`src/research/`) provides deep, autonomous web and document research capabilities with evidence evaluation and multi-format citation formatting.

---

## 1. Subsystem Components

- **`ResearchPlanner`**: Query decomposition, provider selection (Tavily, GitHub, Wikipedia, arXiv), budget estimation.
- **`ResearchReasoner`**: Fact verification, conflict detection between sources, recency weighting, confidence scoring (0.0 to 1.0).
- **`CitationFormatter`**: Converts gathered evidence into APA, MLA, or IEEE formatted citations.

---

## 2. Research Execution Flow

```
User Query ──► Query Decomposition ──► Multi-Provider Search ──► Evidence Gathering ──► Conflict & Trust Analysis ──► Citation Generation
```
