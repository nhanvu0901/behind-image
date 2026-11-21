"""The video's title: written by an agent after the narration is approved (step 2, `title.generate`), kept in `projects/<pid>/title.json`, used by the storyboard's
channel-name beat (`identity.video_title`), the export's description and the output folder, and changeable at any time by a person or an operator (`title.set`).

    rules.py      the limits and the refused phrases, ONE place (the task template and the check both read it)
    check.py      the program's check of the agent's file, and of a title a person types
    store.py      the document, its state (none | done | stale), setting a title, writing a generation
    inputs.py     what the job reads (the approved narration, the outline's thesis and hook, the painting)
    workspace.py  the agent's work folder;   helper.py  its `./check` command
    job.py        the long job `title.generate` (kind `title`, role `script.title`)
    view.py       the answers of GET /api/projects/{pid}/title and of the state answer
    apply.py      the hook that applies a new title to an existing storyboard
    texts.py      the Vietnamese sentences

The skill for an operator is skills/title/SKILL.md (`bti doc title`); the agent's own task is skills/title/TASK.template.md."""
from .store import TitleError, chosen_text, state

__all__ = ["TitleError", "chosen_text", "state"]
