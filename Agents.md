# AGENTS.md

This repository uses automated coding agents. Follow these rules strictly

## Scope

- Operate only on the current pull request (PR) context
- Review and comment only on:
  - Files changed in the PR
  - Lines within the PR diff (current head commit)
- Do not comment on, suggest changes to, or open discussions about:
  - Unchanged files
  - Repo-wide refactors
  - Style cleanups not required by the PR
  - “Future work” or “nice-to-have” improvements outside the diff

## Review Output Requirements

- Every comment must reference a specific diff hunk and be actionable
- If a concern relates to code not modified in the PR, do not comment on it
- Prefer blocking issues only:
  - correctness bugs introduced by the PR
  - security issues introduced by the PR
  - build/test failures caused by the PR
  - clear regressions caused by the PR
- Non-blocking feedback must be minimal and strictly relevant to the changed lines

## Evidence Standard

- Tie each finding to one of:
  - a concrete failure mode
  - a violated invariant already present in the codebase
  - an existing test expectation
  - a documented behavior in this repo
- No speculative “might be better” statements
- No generalized best-practice lectures

## Suggestions

- Provide the smallest viable patch for the issue
- Avoid broad rewrites. Preserve existing patterns unless the PR already changes them
- Do not introduce new dependencies unless the PR already does

## Tests

- If the PR adds or changes behavior, require:
  - updated or new tests, or
  - explicit justification (in the PR discussion) for why tests are not applicable
- Only request tests relevant to the PR’s changes

## When to Stay Silent

If you cannot find any issue strictly within the PR diff respond with:  
“LGTM :rocket: ”
