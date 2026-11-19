"""Helpers of the `bti` command tests (worker c5cli), in a module of their own so that no test imports `conftest` by name: a transport that talks to the
app in the test process without a network, a scripted transport for the answers a real app does not give on demand, and `run_bti`."""
import io
import json

from bti.cli import main as cli_main
from bti.cli.transport import Reply, Transport


class AppTransport(Transport):
    """The app in the test process: the command's requests go to a TestClient, nothing touches a network. `after(suffix, fn)` runs `fn` once
    after the first answer to a path that ends with `suffix` (to make something change between two requests of one command)."""

    def __init__(self, client):
        self.client, self.log, self._hooks = client, [], []

    def after(self, suffix, fn):
        self._hooks.append([suffix, fn])

    def request(self, method, path, body=None, timeout=60.0):
        self.log.append((method, path, body))
        r = self.client.request(method, path, json=body) if body is not None else self.client.request(method, path)
        try:
            data, text = r.json(), ""
        except ValueError:
            data, text = None, r.text
        for h in list(self._hooks):
            if path.split("?")[0].endswith(h[0]):
                self._hooks.remove(h)
                h[1]()
        return Reply(r.status_code, data, text)


class Scripted(Transport):
    """Answers made up by the test: `routes` maps (method, path) to a Reply, a list of Replies (one per request, the last repeats), a callable
    (method, path, body) -> Reply, or an exception to raise."""

    def __init__(self, routes):
        self.routes, self.log = dict(routes), []

    def request(self, method, path, body=None, timeout=60.0):
        self.log.append((method, path, body))
        r = self.routes.get((method, path))
        if r is None:
            return Reply(404, {"detail": "no such route", "code": "route_not_found", "fix": "x", "retry": "no"})
        if isinstance(r, list):
            item = r.pop(0) if len(r) > 1 else r[0]
        else:
            item = r
        if isinstance(item, Exception):
            raise item
        return item(method, path, body) if callable(item) else item


class Result:
    def __init__(self, code, out, err):
        self.code, self.out, self.err = code, out, err

    @property
    def json(self):
        return json.loads(self.out)

    def __repr__(self):
        return "Result(code=%r, out=%r, err=%r)" % (self.code, self.out[:300], self.err[:300])


def run_bti(transport, *argv, env=None, sleep=None, clock=None):
    """Run one `bti` command against `transport`; -> Result(exit code, stdout, stderr). `--interval 0` keeps `--wait` instant."""
    out, err = io.StringIO(), io.StringIO()
    kw = {}
    if sleep is not None:
        kw["sleep"] = sleep
    else:
        kw["sleep"] = lambda s: None
    if clock is not None:
        kw["clock"] = clock
    code = cli_main.main(list(argv), transport=transport, stdout=out, stderr=err, env=env if env is not None else {}, **kw)
    return Result(code, out.getvalue(), err.getvalue())


