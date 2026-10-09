import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { prepareEnvironmentPlan } from "../../lib/contracts/environment";
import type { EnvironmentInstallPlanRead, EnvironmentPlanCreate, EnvironmentRead } from "../../lib/generated";

/** One owner keeps install drafts/results across tabs; it only prepares plans, never executes them. */
export function useEnvironmentInstallation(environment: EnvironmentRead | undefined) {
  const [recipe, setRecipe] = useState<EnvironmentPlanCreate["recipe_id"]>("frontend-dependencies");
  const [offline, setOffline] = useState(true);
  const [plan, setPlan] = useState<EnvironmentInstallPlanRead | null>(null);
  const inFlight = useRef(false);
  const mutation = useMutation({
    mutationFn: (request: EnvironmentPlanCreate) => prepareEnvironmentPlan(request),
    retry: false,
  });
  const available = environment?.host_status === "current" && Boolean(environment.host?.clean_source);
  const selectedRecipe = environment?.recipes.find((item) => item.id === recipe);
  const supported = Boolean(selectedRecipe && (!offline || selectedRecipe.offline_supported));
  function selectRecipe(value: EnvironmentPlanCreate["recipe_id"]) {
    if (inFlight.current) return;
    setRecipe(value);
    setPlan(null);
    mutation.reset();
  }
  function selectOffline(value: boolean) {
    if (inFlight.current) return;
    setOffline(value);
    setPlan(null);
    mutation.reset();
  }
  async function prepare() {
    if (!available || !supported || inFlight.current) return;
    inFlight.current = true;
    setPlan(null);
    try {
      setPlan(await mutation.mutateAsync({ recipe_id: recipe, offline }));
    } catch {
      /* The mutation owns the explicit error; no retry, execution or fallback. */
    } finally {
      inFlight.current = false;
    }
  }
  return {
    recipe,
    offline,
    plan,
    mutation,
    available,
    selectedRecipe,
    supported,
    selectRecipe,
    selectOffline,
    prepare,
  };
}
