# Browser and writable testing access

Fresh conversation context is independent of tool availability and filesystem permissions. Earlier V0 forced read-only access and its separate Codex settings had no browser MCP server. This blocked interactive creative testing even when the app was running.

## Use

```bash
codex-fresheye "Make, revise, save, reopen and export a small artwork. No application source changes."
```

The plain command now enables browser, workspace writes and command networking with normal Codex approvals. FreshEye can inspect the project, determine how to run the app, start a needed server and discover its address. No URL or access flags are required. Start a new FreshEye session to use the new defaults; an older running thread does not gain them retroactively. The main chat stays open.

Optional `--app URL` is useful when you already know the address. It checks the chosen URL before the model task and includes the observed availability as selected launch context. When an HTTP service already responds, FreshEye is instructed to open it with browser tools and not start/stop/restart it. The launcher itself never starts the app; the tester can do so through its command tools. A failed host check tells FreshEye to verify with the browser before considering startup.

For a restricted review, use `codex-fresheye --read-only "your question"`. It disables browser tools, workspace writes and command networking for that launch. It cannot be combined with the older access flags or `--app`. The older `--browser`, `--writable` and `--network` flags remain compatibility aliases for default testing access. For diagnosis, read the receipt's access fields. Explicit command networking in default testing access addresses the native `listen EPERM` failure seen when workspace-write had networking off.

Default testing access adds the selected Playwright MCP server for the launch and saved resume command. It runs headless Chrome with an isolated browser profile and a per-receipt output directory. Existing personal browser profiles/cookies and the main chat's full plugin configuration are not imported. Browser isolation here is profile separation, not a security boundary for the websites it visits.

Default testing access uses native `workspace-write` plus `on-request` approvals. It allows writes within the chosen project directory; it does not enforce a separate source-versus-artwork boundary. Keep “no source changes” in the intended task, or use a disposable project copy if source files must remain technically unwritable. Command networking is enabled for that run, not restricted to loopback. Browser MCP networking is separate. No `danger-full-access`, approval bypass or managed-policy override is used. If the runtime reports that requested networking is denied, startup fails before the model task with that reason in the receipt.

The receipt records requested/effective sandbox settings, browser enablement, browser output and temporary locations. All choices are propagated to App Server preparation, native CLI execution and the saved resume command. Memory use/generation stay off.

## Browser dependency

Requires Chrome, Node.js and Playwright MCP. This machine already has a usable Playwright MCP 0.0.83 installation in its npm cache. The launcher uses an installed `playwright-mcp` command when present, otherwise discovers the tested cached version and invokes it directly with Node. It does not install dependencies silently. To install the tested backend elsewhere:

```bash
npm install -g @playwright/mcp@0.0.83
```

Chrome's Unix socket paths need short temporary paths. Set `CYCLOPS_FRESHEYE_BROWSER_TMP` to a short private directory if your normal temporary directory is long. An installation can save that choice once:

```bash
./install.sh --data-dir /your/FreshEye/state --browser-temp-dir /your/short/browser-tmp
```

The current local installation uses a short private HDD directory, respecting this machine's storage rules. Browser temporaries are separate from the project, main Codex home and receipts. Other machines have no fixed disk/path requirement.

## Verified scope

- Offline tests cover the plain command's browser/write/network defaults, the explicit read-only option, propagation to all launch/resume stages, setup errors and long socket paths.
- A real isolated browser loaded `http://127.0.0.1:4877/` and reported the title `CyclopsDraw`.
- A controlled fixture, separate from the artwork app, verified a browser download to the HDD.
- Native Codex App Server exposed 25 browser tools and returned a workspace-write sandbox with on-request approvals.
- A native sandbox probe allowed a file write inside the test workspace and denied a write outside it.
- A paired native Node probe reproduced `listen EPERM` with networking off, then successfully hosted a temporary loopback HTTP server and reached the existing app with networking on.
- Native App Server returned workspace-write, `networkAccess: true`, on-request approvals and all 25 browser tools for app mode.

No authenticated model turn or actual artwork workflow was used for this capability check. No CyclopsDraw source changes were made. The earlier socket-path failure and probe corrections are retained locally. The owner later confirmed working code-review and creative examples on 2026-10-24; individual creative save/export and lifecycle checks remain unrecorded in [the acceptance record](acceptance.md).

See [the validation summary](validation.md) for the recorded scope. Machine-specific evidence and raw app snapshots are not bundled. On machines with long scratch paths, tests can use a short disposable root through `FRESHEYE_TEST_SHORT_ROOT`.

Official contracts: [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [sandbox/approval settings](https://learn.chatgpt.com/docs/agent-approvals-security).
