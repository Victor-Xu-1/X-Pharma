import { describe, expect, it } from "vitest";

import { ApiError } from "../lib/api";
import { CancelError } from "../lib/generated";
import { shouldRetryQuery } from "../lib/queryClient";

describe("query retry policy", () => {
  it("never retries client validation, authorization or cancellation failures", () => {
    expect(shouldRetryQuery(0, new ApiError("Invalid", 422, null))).toBe(false);
    expect(shouldRetryQuery(0, new ApiError("Forbidden", 403, null))).toBe(false);
    expect(shouldRetryQuery(0, new CancelError("Request aborted"))).toBe(false);
    expect(shouldRetryQuery(0, new DOMException("Aborted", "AbortError"))).toBe(false);
  });

  it("bounds retries for transient server and rate-limit failures", () => {
    expect(shouldRetryQuery(0, new ApiError("Unavailable", 503, null))).toBe(true);
    expect(shouldRetryQuery(1, new ApiError("Rate limited", 429, null))).toBe(true);
    expect(shouldRetryQuery(2, new ApiError("Unavailable", 503, null))).toBe(false);
    expect(shouldRetryQuery(1, new Error("Unknown transport failure"))).toBe(false);
  });
});
