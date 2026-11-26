# Music: choose and place recordings

Once a storyboard and aligned voice exist, the agent chooses a few recordings
from the local, publishable recording library and places them on the timeline.
The task template describes the musical approach and the document shape. Music
is optional and has no approval gate. `music.set` validates a supplied document;
`music.clear` removes it. Changes only require a new sound mix and mux.

<!-- BEGIN GENERATED: actions -->
| id | step | page button | gate | cost | long job |
|---|---|---|---|---|---|
| `music.auto` | export | Chọn nhạc lại |  | model: about 1 minute | yes |
| `music.set` | export | Đặt nhạc |  |  |  |
| `music.clear` | export | Bỏ nhạc |  |  |  |
<!-- END GENERATED: actions -->
