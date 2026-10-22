# One-time GitHub repository settings

The workflows in this directory enforce checks and enable auto-merge after a
maintainer applies the `automerge` label. Configure the following GitHub
repository settings once so that those workflows have the intended effect.

## General: Pull Requests

- Enable **Allow merge commits**.
- Disable **Allow squash merging**.
- Disable **Allow rebase merging**.
- Enable **Allow auto-merge**.
- Enable **Automatically delete head branches**.

This guarantees that both a manual merge and an `automerge` merge create a
merge commit. The automation additionally calls `gh pr merge --merge`, which
explicitly selects that method.

## Ruleset or branch protection for `main`

Create a ruleset that targets `main` and turn on:

- Require a pull request before merging, with **1 approving review**.
- Dismiss stale approvals when new commits are pushed.
- Require conversation resolution before merging.
- Require status checks before merging: `Backend tests`, `Frontend build`, and
  `Conventional PR title`.
- Block force pushes and branch deletion.

Do not require the auto-merge workflow itself as a status check: it only runs
after a maintainer chooses to add the `automerge` label.

## Required labels

The labeler creates `backend`, `frontend`, `documentation`, and
`github-actions` when it first needs them. Create `automerge` manually and
restrict who can apply it to maintainers through your team process.
