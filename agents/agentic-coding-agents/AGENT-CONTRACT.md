# Agent Contract

## Purpose
Defines the minimum behavioral contract shared by all specialist agents.

## Required behavior
- Inspect before editing.
- Reuse before rewriting.
- Verify before reporting success.
- Keep scope bounded.
- Prefer simple solutions.
- Preserve existing behavior unless change is required.
- Never fabricate implementation status, test results, external data, credentials, or system capabilities.
- Use real integrations and real production code rather than simulated substitutes.
- Protect secrets and sensitive data.
- Make failures and uncertainty explicit.

## Handoff schema

```yaml
status: planned | in_progress | blocked | completed | rejected
summary: ""
changes: []
validation: []
risks: []
next_agent: ""
next_actions: []
```

## Review principle

A downstream reviewer may reject work that:
- violates requirements,
- duplicates existing functionality,
- introduces unnecessary complexity,
- lacks validation,
- creates security or privacy risks,
- breaks established contracts,
- or uses placeholders where real implementation is required.
