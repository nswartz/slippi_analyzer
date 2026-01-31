# Project Rules

## General

- REQUIRED: ensure any created/dispatched sub-agents understand these rules.

## Git Workflow

- There is an issue in superpowers 4.1.1 where the skills arent being run correctly. Make sure the brainstorming skill includes the following:

```md
## Remember

- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Reference skills when plan says to
- Between batches: just report and wait
- Stop when blocked, don't guess
- Never start implementation on main/master branch without explicit user consent

## Integration

**Required workflow skills:**

- **superpowers:using-git-worktrees** - REQUIRED: Set up isolated workspace before starting
```

- There are other skills with updated instructions in v4.1.2, but it is not available yet.

## Attribution

When crediting Claude Code as author, co-author, or generator of code, PRs, commits, or features, always frame it as a human using Claude as a tool. Never imply Claude acted autonomously.

Examples:

- ✓ "Created by Noah Swartz using Claude Code"
- ✓ "Noah Swartz built this with Claude Code"
- ✗ "Generated with Claude Code" (implies autonomous generation)
- ✗ "Co-Authored-By: Claude" (implies equal authorship)
