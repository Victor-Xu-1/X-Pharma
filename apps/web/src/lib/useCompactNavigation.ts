import { useEffect, useState } from "react";

/** The shell keeps its 760px default; directory consumers use their own layout boundary. */
export function useCompactNavigation(maxWidth = 760) {
  const mediaQuery = `(max-width: ${maxWidth}px)`;
  const [compact, setCompact] = useState(() => window.matchMedia?.(mediaQuery).matches ?? false);
  useEffect(() => {
    const query = window.matchMedia?.(mediaQuery);
    if (!query) return;
    const update = () => setCompact(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, [mediaQuery]);
  return compact;
}
