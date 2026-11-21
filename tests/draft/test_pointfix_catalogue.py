from bti.draft.techniques_md import generate
from bti.engine.registry import load_bundle


def test_detail_pointer_guidance_reaches_the_draft():
    md = generate(load_bundle('gae'))
    assert 'EVERY time a detail sentence names a thing that is small on screen' in md
    assert 'never alone for a small thing' in md
    assert 'so close together that a pool of light would hold them all' in md
