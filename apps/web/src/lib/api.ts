import { notifySessionContext, organizationHeaders, trackSessionWrite } from "./organizationSession";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function cookie(name: string): string {
  const value = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`))
    ?.split("=")
    .slice(1)
    .join("=");
  return value ? decodeURIComponent(value) : "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  for (const [name, value] of Object.entries(organizationHeaders(path, method))) headers.set(name, value);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = cookie("pharma_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const release = trackSessionWrite(method);
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  } finally {
    release();
  }
  notifySessionContext(response);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(
      body.detail ?? `请求失败 (${response.status})`,
      response.status,
      response.headers.get("X-Request-ID"),
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  async download(path: string, filename: string): Promise<void> {
    const response = await fetch(path, { credentials: "same-origin", headers: organizationHeaders(path) });
    notifySessionContext(response);
    if (!response.ok)
      throw new ApiError(`下载失败 (${response.status})`, response.status, response.headers.get("X-Request-ID"));
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },
  async downloadPost(path: string, body: unknown, fallbackFilename: string): Promise<void> {
    const headers = new Headers({ "Content-Type": "application/json" });
    for (const [name, value] of Object.entries(organizationHeaders(path, "POST"))) headers.set(name, value);
    const csrf = cookie("pharma_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
    const release = trackSessionWrite("POST");
    let response: Response;
    try {
      response = await fetch(path, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        credentials: "same-origin",
      });
    } finally {
      release();
    }
    notifySessionContext(response);
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new ApiError(
        payload.detail ?? `下载失败 (${response.status})`,
        response.status,
        response.headers.get("X-Request-ID"),
      );
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = /filename="([^"\\/]+)"/i.exec(disposition);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = match?.[1] ?? fallbackFilename;
    link.click();
    URL.revokeObjectURL(url);
  },
};
