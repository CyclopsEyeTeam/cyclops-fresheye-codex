# Cyclops FreshEye for Codex

**Experimental V0 — owner tested for code review and creative use.** Keep the main Codex chat open, then start a fresh investigation from a second terminal in the same project directory:

```bash
codex-fresheye "Review this project with fresh eyes."
```

Or run `codex-fresheye` and enter a question. First use guides normal Codex sign-in in a separate settings directory. Switch terminals to return to the main chat. `--once` runs one reply and exits; the default opens the normal native Codex CLI.

Browser tools, workspace writes and command networking are ready by default, with normal Codex approvals. The tester can inspect the project, start the app when needed and discover its address. You do not need to supply a URL or choose access flags:

```bash
codex-fresheye "Make a small artwork, revise it, save and reopen it, then export it. Do not edit application source files."
```

Use `--read-only` for a restricted code review without browser, writes or command networking. If you already know an app's address, optional `--app URL` checks it and tells FreshEye to reuse a responding service. The older `--browser`, `--writable` and `--network` flags remain accepted but are unnecessary. Access settings do not copy the main conversation, memory, plugins or full configuration. [Browser setup and validation](docs/browser-access.md).

FreshEye creates a named thread with App Server and hands it to `codex resume`. It does not fork the main conversation, replace Codex, inject terminal keystrokes, or depend on Cyclops Studio. Receipts record the fresh thread, evidence hashes and an optional main-chat link. The main ID is metadata and is not included in fresh model input. Receipts appear in the FreshEye terminal; automatic display in the main terminal is not implemented.

## Install

Requires Linux, Python **3.10+**, and the native `codex` command on `PATH`. Default testing access also requires Chrome, Node.js and [Playwright MCP](docs/browser-access.md); `--read-only` does not need the browser backend. The protocol was live-tested with Codex CLI **0.164.0**; compatibility with other releases needs verification. Python runtime dependencies: **standard library only**. Setuptools and wheel are build-time dependencies for Python distributions.

```bash
git clone https://github.com/CyclopsEyeTeam/cyclops-fresheye-codex.git
cd cyclops-fresheye-codex
./install.sh
```

The installer copies a self-contained version under `~/.local/share/cyclops-fresheye-codex/versions/` and installs `~/.local/bin/codex-fresheye`. Ensure `~/.local/bin` is on `PATH`. It does not download Codex, run model sessions or alter existing runtime data. An unrelated existing command is refused; `--replace` explicitly backs it up before replacement. Earlier installed versions remain available.

Optional installation locations:

```bash
./install.sh --prefix "$HOME/.local" --data-dir "/your/storage/FreshEye"
```

There is no required disk, UUID or mount path. Without an explicit installation setting, state defaults to `$XDG_STATE_HOME/cyclops-fresheye-codex` or `~/.local/state/cyclops-fresheye-codex`. Override with `CYCLOPS_FRESHEYE_DATA_DIR` or `--data-dir`; `--home` and `--receipts-dir` override individual locations. Project, main Codex home and FreshEye state must be separate. Paths and selected evidence are validated before setup/login; existing directory permissions are not silently changed.

`./install.sh --uninstall` removes only an installer-owned command. Sessions, settings, receipts, backups and installed versions remain. The package also has a standard `pyproject.toml` and console entry point for Python packaging.

## Evidence and main-chat links

```bash
codex-fresheye --evidence README.md "Which claims need stronger evidence?"
codex-fresheye --read-only --once "Review src/parser.py."
```

The main Codex chat can register itself by running `codex-fresheye --bind` through its command tool. Alternatively, use `--bind --origin MAIN_CHAT_ID` once in a terminal. This is an explicit saved registration, not detection of the currently active terminal. A launch uses explicit `--origin`, then its launching Codex environment, then the saved project registration. Without any link it is marked unbound. Rebind when changing the main chat.

Memory use/generation are disabled for the fresh thread. Project/global instructions and trusted hook behavior still apply. Project files are accessible under native `workspace-write` with `on-request` approvals; `--read-only` restricts this explicitly. Files, instructions, hooks, skills or managed policy can still provide context: **complete isolation is not claimed**. Selected evidence must be regular UTF-8 files, limited to 64 KiB each. Relative `--evidence` paths resolve from the selected project (`--cwd`, or the launching directory when omitted); absolute paths retain their meaning. Avoid selecting private conversation notes when seeking an independent perspective.

## Validation and remaining acceptance

```bash
./tools/test.sh
```

The automated suite uses disposable filesystem/process fixtures and a fake Codex protocol boundary. It tests startup error/EOF/timeout cleanup, validation before mutation, portable paths, receipt/input separation and standalone installation. It makes **no authenticated model requests**. On this shared machine, set `TMPDIR` to an HDD scratch directory when running tests or builds.

[The validation summary](docs/validation.md) distinguishes automated checks, native capability probes and owner-reported live use. Machine-specific logs, local memory, runtime state and earlier build artifacts are retained locally and excluded from this repository.

The earlier bounded PTY probe demonstrated a native FreshEye title and final reply, then was intentionally interrupted. On **2026-10-24 the owner confirmed two working live examples: code review and creative use**, and authorized this GitHub upload. Detailed follow-up, clean-exit and resume checks have not been individually recorded. See [the acceptance record and remaining checks](docs/acceptance.md).

Published as an experimental source repository; no stable release or compatibility beyond the tested setup is claimed. License: [MIT](LICENSE), matching the existing Cyclops Eye Team FreshEye project.
