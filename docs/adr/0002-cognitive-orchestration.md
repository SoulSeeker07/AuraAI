# ADR 0002: Cognitive Orchestration Layer & Groq Executive Role

* **Status:** Accepted  
* **Date:** 2026-08-06  
* **Author:** Sreekanta YR  

## Context & Problem Statement
Using LLMs directly as monolithic code generators or tool invokers created several runtime failure modes:
1. LLMs output raw code snippets into chat instead of modifying workspace files on disk.
2. Status queries ("How's it going?") triggered expensive and slow LLM inference loops.
3. Lack of a central cognitive supervisor led to fragmented state across desktop, browser, and coding operations.

## Decision
Establish the **Cognitive Orchestration Layer** where **Groq acts exclusively as the Executive Coordinator (Project Manager)**:
- Groq understands user intent, breaks down goals into subtasks, and assigns work to domain supervisors.
- Groq **never** emits raw code blocks into user chat.
- Control commands (`"status?"`, `"pause engineering"`, `"show active workers"`) bypass LLM inference entirely via zero-LLM interception in `AuraBrain` and `WorkerManager`.

## Alternatives Considered
* **Groq as All-in-One Engine**: Rejected because code generation, browser manipulation, and OS control require specialized engines and state tracking.
* **Direct Tool Calls in Prompt**: Rejected due to high token cost and lack of persistent session state for long-running operations.

## Consequences
* **Positive**: Fast, deterministic control queries; clear separation of planning vs. execution; zero raw code pollution in chat interfaces.
* **Negative**: Requires formal supervisor-worker contract interfaces for all execution backends.
