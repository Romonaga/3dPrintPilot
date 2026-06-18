# Verlyn Public CLI Agent Skill

Use the installed public `verlyn` CLI as the control path for governed repository work. Treat the target repository's governance files as authoritative; this reference must not override repo-local policy.

## Start Every Governed Session

Read the repo governance files before editing or making workflow claims:

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `RULES.md`
4. `.verlyn/runtime_context.json` when present
5. `Documentation/AI_USAGE_POLICY.md` when present
6. `Documentation/guides/VERLYN_AGENT_WORKFLOW.md` when present
7. `Documentation/guides/VERLYN_PUBLIC_CLI.md` when present

After session compaction, compressed-summary recovery, or any resume where governance may be stale, reread the governed files and visibly tell the operator:

```text
Governance was reloaded and required repo rules were reread.
```

Then run the installed public CLI startup checks from the repository root:

```bash
verlyn auth status
verlyn workflow assistant-startup --json
verlyn workflow assert-edit-route --json
verlyn target show --json
verlyn changes list
verlyn changes list --owner-scope all --status-scope all
verlyn runs --limit 3 --json
```

Use the JSON output to confirm auth, repo binding, current branch, visible changes, runs, and edit-route status.

## Respect Edit Routing

Before manual code edits, confirm `verlyn workflow assert-edit-route --json` allows editing.

If the route is blocked because no active change is bound, create or activate the applicable Verlyn change before editing:

```bash
verlyn changes create --title "..." --change-type <type> --effort-band <small|medium|large>
verlyn changes show <change-id> --json
verlyn work-items list <change-id>
verlyn work-items update <change-id> --updates-json '[{"task_id":"<starter-work-item-id>","notes":"Concrete scope, acceptance, and validation details."}]'
verlyn changes activate <change-id>
```

If repo policy allows direct work for a narrow documentation or inspection task, record the direct-work reason through the product path required by the repo. Do not treat a missing active change as permission to edit from memory.

## Work Through Verlyn Records

Use Verlyn-managed records as the durable workflow truth:

- Inspect active change details before feature, behavior, API, workflow, governance, or bug-fix work.
- Update starter work items in place with concrete scope before implementation.
- Keep work-item status current while working.
- Record review findings and dispositions in Verlyn before summarizing them in chat.
- Record skipped checks, residual risks, and handoff notes before closeout.

Common commands:

```bash
verlyn changes list
verlyn changes show <change-id> --json
verlyn work-items list <change-id>
verlyn work-items show <change-id> <work-item-id> --json
verlyn work-items update <change-id> --updates-json '[{"task_id":"<work-item-id>","status":"done"}]'
verlyn reviews record <change-id> --tier 1 --disposition accepted --summary "Reviewed changed files and verification evidence."
verlyn workflow gate <change-id> --scope delivery
```

## Deliver Or Deploy Through Verlyn

Use the installed Verlyn hosted closeout path when the change is ready.

- Use `deliver` for PR/source-control closeout without deployment.
- Use `deploy` for PR/source-control closeout followed by configured provider deployment.

```bash
verlyn changes deliver <change-id> --merge-method squash
verlyn changes deploy <change-id> --merge-method squash
```

If local branch repair or checkout cleanup is blocked, follow the deterministic repair command reported by Verlyn instead of using raw Git or provider tools as a bypass.

## Avoid Unsupported Paths

Do not use private Verlyn developer commands, direct database access, direct workflow-file edits, or shell provider tools such as `gh` as substitutes for public CLI workflow paths.

Do not ask users for provider tokens. Verlyn resolves provider credentials through its product workflow.

Do not reconstruct durable workflow truth from chat summaries, generated scratch files, old local workstream files, or guessed branch names.

When the public CLI path is missing or blocked, record the blocker as workflow feedback in Verlyn and explain the blocked state to the operator.
