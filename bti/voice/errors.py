"""One error type for the voice stage. `code` is stable (the page translates it); `message` is English for the log; `extra`
carries what the page needs (for example the sentences that could not be spoken)."""
from __future__ import annotations


class VoiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra


CODES = (
    "narration_missing",        # there is no narration for the project
    "narration_not_approved",   # the narration is not approved (or no longer)
    "nothing_to_say",           # the narration has no sentence
    "voice_not_configured",     # this machine has no voice worker configured
    "voice_busy",               # a voice job is already running for the project
    "voice_worker_failed",      # the voice worker crashed or wrote nothing
    "voice_chunks_failed",      # some sentences could not be spoken (extra.sentences)
    "voice_chunks_missing",     # a sentence has no audio file at assembly (the narration changed during the run)
    "voice_assemble_failed",    # ffmpeg failed while making the mix
    "voice_align_failed",       # the aligner failed
    "no_voice",                 # no mix to play yet
    "no_chunk",                 # no audio for this sentence yet
    "longjob_missing",          # the long-job runner is not installed (build problem)
)
