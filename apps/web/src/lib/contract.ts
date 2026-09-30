import { type CancelablePromise, OpenAPI } from "./generated";

OpenAPI.BASE = "";
OpenAPI.WITH_CREDENTIALS = true;
OpenAPI.CREDENTIALS = "same-origin";

export async function contractRequest<T>(request: CancelablePromise<T>, signal?: AbortSignal): Promise<T> {
  const cancel = () => request.cancel();
  if (signal?.aborted) cancel();
  else signal?.addEventListener("abort", cancel, { once: true });
  try {
    return await request;
  } finally {
    signal?.removeEventListener("abort", cancel);
  }
}
