# Project Rules

## General

- REQUIRED: ensure any created/dispatched sub-agents understand these rules.
- Installing from existing lockfiles/manifests (npm install, pip install from pyproject.toml) is fine
- NEVER run system-level installs (dnf, apt, brew, etc.) without asking the user first

## Python Environment

- ALWAYS use the project's virtual environment (`.venv/`) for Python operations
- Run Python commands via `.venv/bin/python` or `.venv/bin/<tool>` (e.g., `.venv/bin/pytest`)
- NEVER use `uv` or other global package managers - keep dependencies isolated in the venv
- This is analogous to always using git worktrees: isolation prevents contamination of global/project state

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

## Code Quality

- ALWAYS remove unused imports after refactoring or when pyright reports them
- Run `.venv/bin/pyright src/` before committing to catch type errors and unused imports
- The project uses `typeCheckingMode = "strict"` - all code must pass strict type checking

## Script Usage

When needing to check or verify something programmatically:

1. **Prefer simple commands first** - Use existing CLI tools, grep, or direct file reads before writing scripts
2. **Evaluate necessity** - Ask: "Can this be done with a simpler method?" before writing a bespoke script
3. **Reusable scripts** - If a script would be useful for repeated tasks, consider adding it to `scripts/` directory with documentation
4. **One-off checks** - For truly one-off checks, inline scripts are acceptable but keep them minimal

## Testing

- REQUIRED: Use `superpowers:test-driven-development` skill for all implementation work
- After invoking the TDD skill, create the marker file: `touch /tmp/.superpowers-tdd-session-$(date +%Y%m%d)`
  - A PreToolUse hook blocks edits to production code until this marker exists
- Write tests first, then implementation (red-green-refactor)
- Unit tests for all logic: detectors, clip boundaries, database operations, filename generation
- No snapshot tests
- Skip tests for non-logic code (HTML templates, static config, etc.)
- Integration tests for capture pipeline (with mocked Dolphin/ffmpeg)

## Attribution

When crediting Claude Code as author, co-author, or generator of code, PRs, commits, or features, always frame it as a human using Claude as a tool. Never imply Claude acted autonomously.

Examples:

- ✓ "Created by Noah Swartz using Claude Code"
- ✓ "Noah Swartz built this with Claude Code"
- ✗ "Generated with Claude Code" (implies autonomous generation)
- ✗ "Co-Authored-By: Claude" (implies equal authorship)
