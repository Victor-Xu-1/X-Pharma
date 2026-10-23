import { useState } from "react";
import { t, useLocale } from "../lib/i18n";
import type { User } from "../lib/types";

const initialSegmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });

function AvatarImage({ imageUrl, initial }: { imageUrl: string; initial: string }) {
  const [failed, setFailed] = useState(false);
  return imageUrl && !failed ? (
    <img src={imageUrl} alt="" onError={() => setFailed(true)} referrerPolicy="no-referrer" />
  ) : (
    <span aria-hidden="true">{initial}</span>
  );
}

/** Image failure belongs to one URL, not to the account or an unsaved profile draft. */
export function UserAvatar({
  user,
  className,
}: {
  user: Pick<User, "display_name" | "email" | "avatar_url">;
  className: string;
}) {
  useLocale();
  const imageUrl = user.avatar_url?.trim() || "";
  const name = user.display_name.trim() || user.email.trim();
  const initial = initialSegmenter.segment(name)[Symbol.iterator]().next().value?.segment.toUpperCase() ?? "";
  return (
    <span className={className} role="img" aria-label={t("{name}的头像", { name: user.display_name })}>
      <AvatarImage key={imageUrl} imageUrl={imageUrl} initial={initial} />
    </span>
  );
}
