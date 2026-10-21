# Agentic Coding Organization

This directory defines the specialist agents for an end-to-end software engineering and AI/ML organization.

## Architecture

```text
JARVIS / Orchestrator
├── Product & Research
├── Architecture
├── Implementation
├── AI/ML
├── MLOps
├── Quality
├── DevOps / Production
├── Security
├── Documentation
└── Engineering Operations
```

The 90 specialists are intentionally represented as Markdown contracts. They should not all run as independent autonomous processes. Prefer a smaller set of orchestrated agents with these files acting as role/skill specifications.

## Agent contract

Every agent:
1. Reads the current project state.
2. Checks existing implementation before changing it.
3. Performs only its assigned responsibility.
4. Produces verifiable outputs.
5. Hands structured results to the next agent.
6. Escalates ambiguity or high-impact decisions instead of guessing.

## Suggested core runtime agents

- Orchestrator
- Product/Research
- Architecture
- Coding
- AI/ML
- QA
- Security
- DevOps/MLOps
- Reviewer
- Documentation/Knowledge

The remaining specialists can be loaded as skills or delegated capabilities.
