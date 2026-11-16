// Error of an HTTP call. `message` is a Vietnamese sentence (see errmsg.js, the one place that turns an error into
// a message); `detail` is the raw text the server sent when it differs; `status` and `body` are the response itself.
import { describeHttp } from './errmsg.js';

export class ApiError extends Error {
  constructor(status, body, url) {
    const d = describeHttp(status, body);
    super(d.text);
    this.status = status; this.body = body; this.url = url; this.detail = d.detail;
  }
}
