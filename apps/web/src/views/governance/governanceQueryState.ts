import { ApiError } from "../../lib/api";

/** An authorization denial invalidates the display authority of an older successful read. */
export function governanceReadDenied(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}
