import { CircleAlert } from "lucide-react";
import "./FormStatus.css";

/** Presents the caller's operation state; owns no mutation or retry lifecycle. */
export function FormStatus({
  pending,
  error,
  pendingLabel = "正在提交操作",
}: {
  pending: boolean;
  error?: string;
  pendingLabel?: string;
}) {
  if (pending) {
    return (
      <div className="form-status" role="status" aria-live="polite" aria-atomic="true">
        <span className="spinner" aria-hidden="true" />
        <span>{pendingLabel}</span>
      </div>
    );
  }
  return error ? (
    <div className="form-status form-status-error" role="alert">
      <CircleAlert size={18} aria-hidden="true" />
      <span>{error}</span>
    </div>
  ) : null;
}
