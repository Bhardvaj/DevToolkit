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

### B. Build & Release DevToolkit (`.github/workflows/build.yml`)
Runs automatically **only when a PR is merged into `main`** (or when manually dispatched/released):
1. Runs full test suite and packages the standalone Windows binary.
2. Generates and uploads the `DevToolkit-Windows-x64` artifact (`DevToolkit.exe` + `devtoolkit.config.yaml`).
3. If a release tag is specified or an official release is published, automatically attaches the standalone binary to the GitHub Release.
