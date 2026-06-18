# Project Rules

This file is for project-specific rules set by the repository owner.

Rules in this file must not override `CONTRIBUTING.md` or `AGENTS.md`. Add only
guidance that is specific to this repository, team, product, stack, or workflow.

## Rules

- Application state must be owned by the established state managers and route managers. Do not spread durable app state, routing decisions, selection persistence, or workflow transition logic across ad hoc component-level effects or one-off local storage paths.
- Use state managers when state needs to be managed. Do not duplicate state management across unrelated components.
- Only use async behavior for work that is actually long-running. Routing to a new view should not require async control flow; route and state machines are responsible for view transitions.
- Use `verlyn changes deliver <change-id>` for hosted source-control closeout. It performs the PR step by creating or updating the pull request, merging it, and recording closeout.
- Use `verlyn changes deploy <change-id>` when the same hosted PR closeout should also deploy to the configured provider.
