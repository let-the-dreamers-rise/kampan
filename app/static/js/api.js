// Calls the JSON API and unwraps { ok, data } / { ok: false, error }.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function api(path, body, retries = 1) {
  const opts = body === undefined ? { credentials: "same-origin" }
    : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new ApiError("Network problem: check your connection and try again.", 0);
  }
  let payload;
  try {
    payload = await res.json();
  } catch {
    // A cut-off body (seen behind some antivirus proxies) is retried once; writes are idempotent.
    if (res.ok && retries > 0) return api(path, body, retries - 1);
    throw new ApiError(`The server reply could not be read (HTTP ${res.status}).`, res.status);
  }
  if (!payload.ok) throw new ApiError(payload.error || `HTTP ${res.status}`, res.status);
  return payload.data;
}
