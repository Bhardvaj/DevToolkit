# DevToolkit Working Rules & Contribution Guidelines

To ensure code quality, build reliability, and clear project tracking across development phases, all work in this repository must follow these rules.

*Last Updated: Phase 12 Rules Enforcement*

---

## 1. Protected Main Branch
- The `main` branch is **locked**. Direct pushes to `main` are strictly prohibited.
- All new features, tasks, improvements, and bug fixes must be submitted via a **Pull Request (PR)**.

---

## 2. Branch Naming Convention
Every task must be developed on its own isolated branch following the phase and task numbering convention:

* **Format**: `phase-<PhaseNumber>-<TaskNumber>/<description>` or `Phase-<PhaseNumber>-<TaskNumber>-<description>`
* **Examples**:
  - `phase-12-05/fixed-buggy-ui-issue`
  - `Phase-12-05-fixed-buggy-ui-issue`
  - `phase-10-04/comprehensive-signatures`

> **Note**: Git branch names cannot contain spaces or colons. Use hyphens or forward slashes to separate words.

---

## 3. Pull Request Title Convention
Every Pull Request title **must strictly match** the repository naming convention. This is enforced automatically by the PR CI check.

* **Format**: `Phase <PhaseNumber> - <TaskNumber>: <PR Title>`
* **Examples**:
  - `Phase 12 - 05: fixed buggy UI issue`
  - `Phase 10 - 04: Comprehensive tool signature detection`
  - `Phase 11 - 01: Fast search engine integration`

---

## 4. Automated CI/CD Workflows

### A. Pull Request Build (`.github/workflows/pr.yml`)
Runs automatically whenever a PR targeting `main` is opened, edited, or synchronized:
1. **Validate PR Title & Naming Convention**: Validates that the PR title matches `^Phase \d+ - \d+: .+$` and branch origin.
2. **Test & Package Validation**: Runs the entire test suite on Windows (`pytest -v`), builds the standalone `DevToolkit.exe` binary, and verifies CLI smoke tests (`--help`, `inspect`).
3. **Status Check Requirement**: This check must pass successfully before a PR can be merged into `main`.

### B. Post-Merge CI (`.github/workflows/post-merge.yml`)
Runs automatically **whenever a PR is merged into `main`**:
1. Runs the entire test suite on Windows (`pytest -v`).
2. Packages the standalone Windows binary (`DevToolkit.exe`).
3. Runs CLI smoke tests (`--help`, `inspect`) to guarantee `main` branch stability.
4. Generates and uploads the `DevToolkit-Main-Windows-x64` artifact for immediate download and verification.
5. Does *not* create or publish a GitHub release tag.

### C. Build & Release DevToolkit (`.github/workflows/build.yml`)
Automated release pipeline that publishes official GitHub Releases:
1. **Daily Scheduled Run**: Runs every day at **7:00 AM EDT (11:00 UTC)**. If new commits or PRs have been merged into `main` since the previous release, it automatically increments the patch version (e.g. `v0.5.1` -> `v0.5.2`), generates GitHub release notes, builds the standalone binary, and attaches release assets. If no new commits were merged, the release creation is safely skipped to avoid empty duplicates.
2. **Manual Dispatch**: Can be triggered manually with `create_release: true` (with an optional custom `tag_name` override).
3. **Official Release**: Triggers whenever a release is published via GitHub.
