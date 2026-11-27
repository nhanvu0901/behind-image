# Edit the visual script

Read `inputs/visual.json`, `inputs/scope.json`, the narration, timing, painting and catalogue. Apply the owner's request to the selected moments. Keep every unselected moment and existing wanted entry unchanged. You may split or join moments only inside the selected word spans; add cast entries or adjust them where needed, while keeping cast used by unselected moments unchanged. Use existing regions or pool pictures, or add an open wanted picture with a sensible fallback. Do not create regions here.

Apply the picture, name, mark and source principles in `inputs/PLAN.md` to the changed moments; do not start the script afresh. Write the complete updated script to `out/visual.json`, preserving `made_from`. Run {{CHECK_CMD}} and fix every ERROR.
