import { governanceReviewText as t } from "../../lib/i18n/governanceReview";

export function ReviewNotes({
  label = t("审核意见"),
  notes,
  onNotes,
  busy,
  error,
}: {
  label?: string;
  notes: string;
  onNotes: (value: string) => void;
  busy: boolean;
  error: string;
}) {
  return (
    <>
      <label className="review-notes">
        <span>{label}</span>
        <textarea
          aria-label={label}
          rows={4}
          value={notes}
          onChange={(event) => onNotes(event.target.value)}
          disabled={busy}
          maxLength={4000}
        />
      </label>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </>
  );
}
