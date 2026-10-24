# Experimental V0 acceptance status

Current status: experimental V0. The owner confirmed code-review and creative examples and authorized GitHub publication on 2026-10-24. A stable release is not claimed.

## Evidence already available

- Historical 0.164.0 model-marker tests and a bounded interactive PTY probe are preserved locally. See [the public validation summary](validation.md).
- The hardening suite uses offline transport/filesystem fixtures. It proves the exercised lifecycle and packaging behavior, not model isolation or artistic/owner acceptance.
- The main conversation, credentials and earlier sessions are not copied into the package or new model input.

## Owner live-use report - 2026-10-24

The owner reported: "confirmed good and working well", alongside a FreshEye review identifying three reproducible file-handling flaws. This records successful owner-reported live use of the one-command launcher. The review itself reports offline validation, with no authenticated Codex or browser sessions exercised during that review.

The owner subsequently confirmed testing two working examples, **code review and creative use**, and requested upload to GitHub. This is owner-reported acceptance of those two examples, separate from automated validation.

Individual follow-up, clean-exit, resume and creative save/export checks were not specified in the confirmation. Complete isolation and stable-release readiness are not established by this report.

## Detailed lifecycle checks still to record

These checks remain individually unrecorded; they do not block the authorized file-handling fixes.

1. Keep the main chat open. Open a second terminal in the chosen project.
2. Run `codex-fresheye "A suitable independent investigation question"` and complete normal sign-in if required.
3. Confirm the native FreshEye label, intended project, selected evidence and expected permissions.
4. Complete an initial reply and at least one follow-up without a forced timeout or external interruption.
5. Exit normally, check the receipt and resume that fresh session using its saved resume command.
6. Switch back to the original terminal and confirm its history and working state are preserved.

Record owner observations and explicit acceptance separately. Do not turn fixture passes or the earlier intentionally interrupted probe into an owner acceptance claim.
