/** Error of an HTTP call. `message` is the server's `detail` (Vietnamese or English) when there is one. */
export class ApiError extends Error {
  constructor(status, body, url) {
    const d = body && typeof body === 'object' ? body.detail : typeof body === 'string' ? body : null;
    const msg = typeof d === 'string' && d ? d.slice(0, 300) : d ? JSON.stringify(d).slice(0, 300) : `HTTP ${status}`;
    super(msg);
    this.status = status; this.body = body; this.url = url;
  }
}
