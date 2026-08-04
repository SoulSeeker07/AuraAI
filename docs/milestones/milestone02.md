# Milestone 2 — Capability Router

## Goal
Create a router that directs requests to the correct subsystem instead of sending everything to an LLM.

## Architecture
Routes requests to the appropriate subsystem based on:
- Intent routing
- Tool routing
- Plugin routing
- LLM routing
- Local execution
- Cost optimization

### Example Routing
```
Open Chrome
      ↓
Desktop Plugin

Delete File
      ↓
Filesystem Plugin

Explain OSPF
      ↓
LLM
```

## Core Components
- Intent recognition system
- Tool router
- Plugin router
- LLM router
- Local execution handler
- Cost optimization engine

## Dependencies
- Aura Brain (Milestone 1)
- Tool execution engine (Milestone 5)

## Current Progress
- 🟡 PARTIAL - Implementation found in src/routing/

## Completion %
- 40%

## Future Work
- Improve intent recognition accuracy
- Add machine learning-based routing
- Optimize for cost reduction
- Add request prioritization
