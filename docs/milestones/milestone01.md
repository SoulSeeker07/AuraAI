# Milestone 1 — Aura Brain

## Goal
Create the central intelligence of Aura as the single request entry point that coordinates all other subsystems.

## Architecture

### Pipeline
```
User
    ↓
Aura Brain
    ↓
Planner
    ↓
Memory
    ↓
Capability Router
    ↓
Provider / Tool
    ↓
Response
```

### Responsibilities
- Single request entry point
- Context assembly
- Decision making
- Planning initiation
- Response coordination
- State management

## Core Components
- Planners (various types for different scenarios)
- Context assembler
- Decision engine
- Response coordinator
- State manager

## Dependencies
- Memory system (Milestone 3)
- Capability Router (Milestone 2)
- Planner subsystems

## Current Progress
- ❌ NOT COMPLETE - Implementation found in src/brain/

## Completion %
- 0%

## Future Work
- Implement Planner subsystem
- Develop Context assembler
- Create Decision engine
- Build Response coordinator
- Implement State manager
- Add context management
- Develop request routing logic
