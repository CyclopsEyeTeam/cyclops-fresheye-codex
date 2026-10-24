# Validation - 24 October 2026

Tested implementation: 0.1.0a5, native Codex CLI 0.164.0, Linux Mint 22.3. Other versions and operating systems need verification.

## Automated checks

All 44 offline tests passed with no skips on the development machine, including two tests against actual aliases of the same mounted filesystem. The five file-handling regression tests also passed against the installed launcher.

The suite covers process cleanup after App Server startup failures, bounded shutdown, path validation before mutation, portable state locations, standalone installation, receipt/input separation, default tester permissions and explicit read-only access. Regression tests cover stale temporary files blocking rebinding, special evidence files hanging or being read, and relative evidence selecting the wrong project's README. Absolute evidence paths retain their meaning.

Additional controlled probes rejected a regular file swapped to a named pipe during open and completed eight concurrent private atomic saves with intact JSON. These probes do not establish general resistance to adversarial filesystems.

Tests use disposable files and a fake Codex protocol boundary. They make no authenticated model requests. To run them:

```bash
./tools/test.sh
```

On machines with long temporary paths, set `FRESHEYE_TEST_SHORT_ROOT` to a short temporary directory for the browser-path fixtures. On the development machine, both `TMPDIR` and that root reside on the designated scratch disk. The two mount-alias tests require `FRESHEYE_TEST_MOUNT_ROOT` and `FRESHEYE_TEST_ALIAS_ROOT` to name actual aliases of the same mounted filesystem; they skip when those inputs are absent.

## Native capability probes

Earlier bounded checks used real native capabilities, separately from the offline suite:

- App Server exposed 25 isolated Playwright browser tools and returned workspace-write, on-request approvals and command networking enabled.
- An isolated browser loaded the running creative app; a separate controlled fixture verified a browser download.
- A native sandbox permitted a workspace write and denied a write outside its boundary.
- With command networking disabled, a Node server reproduced `listen EPERM`. With networking enabled, it hosted a temporary loopback server and reached the existing app.

The file-handling update did not repeat authenticated model or browser sessions.

## Context and lifecycle evidence

Historical synthetic-marker checks distinguished a new thread from a fork: the new thread omitted the original conversation marker, while a fork retained it. Normal project/global instructions, persistent configuration and trusted hooks could still supply context. A dedicated controlled home with selected evidence demonstrated a narrower fresh-context fixture, not universal isolation.

The launcher uses a dedicated Codex home, disables memory use/generation, removes inherited thread identifiers and puts any main-chat identifier in receipt metadata rather than model input. Project/global instructions still apply, and tools can read accessible files. **Complete isolation is not claimed.**

A bounded native interactive probe showed the FreshEye title and a final reply before intentional interruption. Historical original/fresh resume-marker checks are distinct from full acceptance of the current interactive lifecycle.

## Owner confirmation

On 24 October 2026 the owner confirmed successful live use in two examples: **code review and creative use**, and authorized the GitHub upload. Specific clean-exit, follow-up, saved-session resume and creative save/export steps were not individually itemized. See [the acceptance record](acceptance.md).

Machine logs, local memory, owner session data, credentials and historical package artifacts are excluded from the public repository. The original local evidence remains preserved.
