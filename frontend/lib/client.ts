/** Single transport boundary for both the unchanged demo and persisted API. */
const baseUrl = (
  process.env.NEXT_PUBLIC_RINGSENTINEL_API_BASE_URL ?? ''
).replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string,
  ) {
    super(`${message} [request ${requestId}]`);
    this.name = 'ApiError';
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const requestId = crypto.randomUUID();
  const headers = new Headers(init.headers);
  headers.set('X-Request-ID', requestId);
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api${path}`, {
      ...init,
      cache: 'no-store',
      credentials: 'same-origin',
      headers,
    });
  } catch (error: unknown) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(
      'Backend unavailable. Check the connection and retry.',
      0,
      'BACKEND_UNAVAILABLE',
      requestId,
    );
  }
  const returnedId = response.headers.get('X-Request-ID') ?? requestId;
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      body &&
      typeof body === 'object' &&
      'error' in body &&
      body.error &&
      typeof body.error === 'object'
        ? body.error
        : {};
    throw new ApiError(
      'message' in detail && typeof detail.message === 'string'
        ? detail.message
        : `Request failed (${response.status}).`,
      response.status,
      'code' in detail && typeof detail.code === 'string'
        ? detail.code
        : 'REQUEST_FAILED',
      returnedId,
    );
  }
  return response.json() as Promise<T>;
}
