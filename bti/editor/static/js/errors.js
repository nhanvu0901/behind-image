export class ApiError extends Error {
  constructor(status, body, url) {
    super(`HTTP ${status} ${url}`);
    this.status = status; this.body = body; this.url = url;
  }
}
