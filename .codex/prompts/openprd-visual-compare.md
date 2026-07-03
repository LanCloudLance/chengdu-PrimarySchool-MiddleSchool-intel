<!-- OPENPRD:GENERATED
adapter=codex
source=command:visual-compare
version=0.1.11
checksum=e1aff81a43d37fd8
-->

# OpenPrd Visual Compare

When UI work has a confirmed reference effect image or user-provided design, capture the implemented UI screenshot, then run `openprd visual-compare . --reference <effect-image> --actual <implementation-screenshot>`.
Treat newly generated images as candidate references until the user confirms they match expectations, should be used for later effect-image vs implementation comparison, and should drive implementation.
The command creates a side-by-side JPG under `.openprd/harness/visual-reviews/` by default, with Simplified Chinese labels: left `效果图`, right `实现截图`.
When UI work has no reference image, first distinguish new UI from existing UI changes. For new screens, return to the pre-implementation three-direction visual review. For existing UI changes, capture the before screenshot first, implement the change, capture the after screenshot from the same entry, viewport, account, and data state, then run `openprd visual-compare . --before <before-screenshot> --after <after-screenshot>` for a before/after self-check labeled `修改前` / `修改后`.
When one reference image contains multiple sub-images, grid cells, or objects, run `openprd visual-prepare . --reference <effect-image> --grid <columns>x<rows>` or `--boxes <plan.json>` first so the agent compares item by item instead of comparing the whole board blindly.
When local detail matters more than the whole screen, prepare a board JSON and run `openprd visual-compare . --board <board.json>` to generate a `focus-board` with overview boxes plus numbered zoom panels.
When the agent explores multiple optimization directions in parallel, use `openprd visual-compare . --board <board.json>` with `mode=parallel-board` to assemble screenshots, GIF first frames, and key metrics into one review board.
Inspect the generated image and keep iterating until there are no obvious visual differences before claiming completion. If the user says the implementation looks wrong, ugly, inconsistent, or asks for replication, do not claim you already compared it without producing at least one visual evidence artifact.
For large UI changes before implementation, decide from user goal, information architecture change, visual decision cost, and validation risk. If an existing screen is available, capture the current in-product screen with Codex Computer Use; if this is a cold-start screen, create a design brief from the confirmed PRD, audience, first slice, and visual goal. Generate at least three Image 2 directions from that screenshot or brief, combine them into one horizontal numbered contact sheet as a candidate effect-image board, and ask the user whether it matches expectations, should be used for later comparison, and should drive implementation before you store the chosen reference-set under `.openprd/harness/visual-reviews/`.

Always rebuild state from `.openprd/` before acting.
