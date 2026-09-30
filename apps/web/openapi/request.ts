import { ApiError } from "../../api";
import type { ApiRequestOptions } from "./ApiRequestOptions";
import { CancelablePromise } from "./CancelablePromise";
import type { OpenAPIConfig } from "./OpenAPI";

type Resolver<T> = T | ((options: ApiRequestOptions) => Promise<T>);

function isDefined<T>(value: T | null | undefined): value is T {
  return value !== undefined && value !== null;
}

async function resolveValue<T>(options: ApiRequestOptions, value?: Resolver<T>): Promise<T | undefined> {
  return typeof value === "function" ? (value as (request: ApiRequestOptions) => Promise<T>)(options) : value;
}

function queryString(parameters: Record<string, unknown>): string {
  const values: string[] = [];
  const append = (key: string, value: unknown) => {
    if (!isDefined(value)) return;
    if (Array.isArray(value)) {
      for (const item of value) append(key, item);
    } else if (typeof value === "object") {
      for (const [childKey, childValue] of Object.entries(value as Record<string, unknown>)) {
        append(`${key}[${childKey}]`, childValue);
      }
    } else {
      values.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
    }
  };
  for (const [key, value] of Object.entries(parameters)) append(key, value);
  return values.length ? `?${values.join("&")}` : "";
}

function requestUrl(config: OpenAPIConfig, options: ApiRequestOptions): string {
  const encodePath = config.ENCODE_PATH ?? encodeURIComponent;
  const path = options.url
    .replace("{api-version}", config.VERSION)
    .replace(/{(.*?)}/g, (match, key: string) =>
      Object.hasOwn(options.path ?? {}, key) ? encodePath(String(options.path?.[key])) : match,
    );
  return `${config.BASE}${path}${options.query ? queryString(options.query) : ""}`;
}

function csrfCookie(): string {
  if (typeof document === "undefined") return "";
  const encoded = document.cookie
    .split("; ")
    .find((item) => item.startsWith("pharma_csrf="))
    ?.slice("pharma_csrf=".length);
  return encoded ? decodeURIComponent(encoded) : "";
}

function formBody(options: ApiRequestOptions): FormData | undefined {
  if (!options.formData) return undefined;
  const data = new FormData();
  const append = (key: string, value: unknown) => {
    if (!isDefined(value)) return;
    if (value instanceof Blob || typeof value === "string") data.append(key, value);
    else data.append(key, JSON.stringify(value));
  };
  for (const [key, value] of Object.entries(options.formData)) {
    if (Array.isArray(value)) for (const item of value) append(key, item);
    else append(key, value);
  }
  return data;
}

function requestBody(options: ApiRequestOptions): BodyInit | undefined {
  if (!isDefined(options.body)) return undefined;
  if (typeof options.body === "string" || options.body instanceof Blob || options.body instanceof FormData) {
    return options.body;
  }
  return JSON.stringify(options.body);
}

async function responseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const contentType = response.headers.get("Content-Type")?.toLowerCase() ?? "";
  if (contentType.startsWith("application/json") || contentType.startsWith("application/problem+json")) {
    return response.json().catch(() => undefined);
  }
  if (contentType.startsWith("text/")) return response.text().catch(() => undefined);
  return response.blob().catch(() => undefined);
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail !== undefined) return JSON.stringify(detail);
  }
  return `请求失败 (${status})`;
}

export const request = <T>(config: OpenAPIConfig, options: ApiRequestOptions): CancelablePromise<T> =>
  new CancelablePromise<T>(async (resolve, reject, onCancel) => {
    const controller = new AbortController();
    onCancel(() => controller.abort());
    try {
      const [configuredHeaders, token, username, password] = await Promise.all([
        resolveValue(options, config.HEADERS),
        resolveValue(options, config.TOKEN),
        resolveValue(options, config.USERNAME),
        resolveValue(options, config.PASSWORD),
      ]);
      const headers = new Headers({ Accept: "application/json", ...configuredHeaders, ...options.headers });
      if (token) headers.set("Authorization", `Bearer ${token}`);
      if (username && password) headers.set("Authorization", `Basic ${btoa(`${username}:${password}`)}`);
      if (isDefined(options.body) && options.mediaType) headers.set("Content-Type", options.mediaType);
      if (!["GET", "HEAD", "OPTIONS"].includes(options.method)) {
        const csrf = csrfCookie();
        if (csrf) headers.set("X-CSRF-Token", csrf);
      }
      if (onCancel.isCancelled) return;

      const multipart = formBody(options);
      const response = await fetch(requestUrl(config, options), {
        method: options.method,
        headers,
        body: requestBody(options) ?? multipart,
        credentials: config.WITH_CREDENTIALS ? config.CREDENTIALS : "same-origin",
        signal: controller.signal,
      });
      if (onCancel.isCancelled) return;
      if (response.status === 401 && typeof window !== "undefined") {
        window.dispatchEvent(new Event("pharma:unauthorized"));
      }
      const body = options.responseHeader
        ? (response.headers.get(options.responseHeader) ?? undefined)
        : await responseBody(response);
      if (!response.ok) {
        throw new ApiError(errorMessage(body, response.status), response.status, response.headers.get("X-Request-ID"));
      }
      resolve(body as T);
    } catch (error) {
      reject(error);
    }
  });
