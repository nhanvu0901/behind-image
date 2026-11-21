from types import SimpleNamespace
import pytest
from bti.voice import assemble, run
from bti.voice.errors import VoiceError


def setup_norm(monkeypatch, peaks):
    commands = []
    def invoke(cmd):
        commands.append(cmd)
        return SimpleNamespace(returncode=0, stderr=b'')
    monkeypatch.setattr(assemble, '_run', invoke)
    monkeypatch.setattr(assemble, '_finish', lambda a, b: None)
    values = iter(peaks)
    monkeypatch.setattr(assemble, 'measure', lambda p: {'tp': next(values), 'i': -15, 'lra': 3})
    return commands


def test_normalise_retries_until_third_encode(tmp_path, monkeypatch):
    commands = setup_norm(monkeypatch, [-1.0, -1.3, -1.6])
    assert assemble.normalise(tmp_path/'in.wav', tmp_path/'out.m4a', {'i':-15,'tp':-1.5,'lra':11}, '192k')['tp'] == -1.6
    assert len(commands) == 4
    filters = [cmd[cmd.index('-af')+1] for cmd in commands[1:]]
    assert filters == [assemble._limiter_filter(-1.5, margin) for margin in (0.2,1.0,1.5)]


def test_normalise_reports_all_five_peaks(tmp_path, monkeypatch):
    commands = setup_norm(monkeypatch, [-1.0, -1.1, -1.2, -1.3, -1.4])
    with pytest.raises(VoiceError) as e:
        assemble.normalise(tmp_path/'in.wav', tmp_path/'out.m4a', {'i':-15,'tp':-1.5,'lra':11}, '192k')
    assert len(commands) == 6
    assert all(str(n) in str(e.value) for n in [-1.0,-1.1,-1.2,-1.3,-1.4])


def test_part_error_preserves_assembly_detail():
    err = run._partfail(VoiceError('voice_assemble_failed', 'true peak -1.26 exceeds -1.50'))
    assert 'true peak -1.26' in str(err)
    assert 'ffmpeg lỗi' not in str(err)


def test_job_record_keeps_assembly_reason(tmp_path):
    from bti.longjob import Part
    from bti.longjob.config import ServerConfig
    from bti.longjob.fakes import FakeProbes
    from bti.longjob.heavy import HeavySlot
    from bti.longjob.manager import LongJobManager
    from bti.cli.main import _job_fix
    d=tmp_path/'project'; d.mkdir()
    manager=LongJobManager(heavy=HeavySlot(ServerConfig(),probes=FakeProbes()))
    manager.configure(projects_root=tmp_path)
    def fail(ctx):
        raise VoiceError('voice_assemble_failed','true peak measurements -1.26, -1.24 dBTP exceed limit -1.50')
    job=manager.start('voice','project',d,[Part('assemble','Mix',run._guard(fail))])
    record=manager.wait(job,15)
    assert record['error_code']=='voice_assemble_failed'
    assert '-1.26' in record['error'] and '-1.24' in record['error']
    assert 'limiter' in _job_fix(record)


@pytest.mark.parametrize('detail, expected', [
    ('ffmpeg did not run: FileNotFoundError', 'installed'),
    ('ffmpeg did not run: TimeoutExpired', 'timed out'),
    ('ffmpeg could not read input.wav: bad input', 'input'),
    ('ffmpeg could not write the mix: access denied', 'output'),
    ('the file mix.m4a could not be finished: PermissionError', 'permissions'),
    ('true peak measurements -1.26 exceed limit -1.50', 'limiter'),
])
def test_cli_fix_fits_the_actual_assembly_failure(detail, expected):
    from bti.cli.main import _job_fix
    assert expected in _job_fix({'error_code':'voice_assemble_failed','error':detail})
