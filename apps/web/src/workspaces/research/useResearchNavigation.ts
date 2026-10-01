import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState, useTransition } from "react";
import type { SavedSearch } from "../../lib/contracts/monitoring";
import { loadSavedSearch, monitoringKeys } from "../../lib/contracts/monitoring";
import { getSessionEntity, sessionKeys } from "../../lib/contracts/session";
import { startResearchRum } from "../../lib/rum";
import type { Entity } from "../../lib/types";
import {
  parseWorkbenchLocation,
  researchReturnLocation,
  type ViewKey,
  type WorkspaceLocation,
  workbenchForView,
  workspaceUrl,
} from "../../lib/workspaceRouting";
import { specializedSectionByEntitySection } from "./locationModel";
import { savedSearchLocation } from "./savedSearchLocation";

export function useResearchNavigation() {
  const [location, setLocation] = useState<WorkspaceLocation>(() =>
    parseWorkbenchLocation("research", window.location.search),
  );

  const [, startNavigationTransition] = useTransition();

  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);

  const [pendingNavigationView, setPendingNavigationView] = useState<ViewKey | null>(null);

  const activeReturnLocation = researchReturnLocation(location.returnTo);

  const routeEntity = useQuery({
    queryKey: sessionKeys.entity(location.entityId ?? ""),
    queryFn: ({ signal }) => getSessionEntity(location.entityId ?? "", signal),
    enabled: Boolean(
      (location.view === "explorer" ||
        location.view === "target" ||
        location.view === "drug" ||
        location.view === "company" ||
        location.view === "disease" ||
        location.view === "entity") &&
        !location.invalidEntityId &&
        location.entityId &&
        selectedEntity?.id !== location.entityId,
    ),
  });

  const routeChemistrySavedSearch = useQuery({
    queryKey: monitoringKeys.saved(location.chemistrySavedSearchId ?? ""),
    queryFn: ({ signal }) => loadSavedSearch(location.chemistrySavedSearchId ?? "", signal),
    enabled:
      location.view === "chemistry" &&
      Boolean(location.chemistrySavedSearchId) &&
      !location.invalidChemistrySavedSearchId,
  });

  useEffect(() => {
    void startResearchRum();
  }, []);

  useEffect(() => {
    const canonicalUrl = workspaceUrl(location);
    if (`${window.location.pathname}${window.location.search}` !== canonicalUrl) {
      window.history.replaceState(null, "", canonicalUrl);
    }
  }, [location]);

  useEffect(() => {
    const popState = () => {
      setPendingNavigationView(null);
      setLocation(parseWorkbenchLocation("research", window.location.search));
    };
    window.addEventListener("popstate", popState);
    return () => window.removeEventListener("popstate", popState);
  }, []);

  const navigate = useCallback(
    (next: WorkspaceLocation, replace = false, urgent = false) => {
      // Applying filters/display within a view keeps its source. Sidebar resets
      // and explicit returnTo overrides are deliberate context changes.
      const destination =
        !urgent && next.view === location.view && !Object.hasOwn(next, "returnTo") && location.returnTo
          ? { ...next, returnTo: location.returnTo }
          : next;
      const method = replace ? "replaceState" : "pushState";
      window.history[method](null, "", workspaceUrl(destination));
      const commitLocation = () => {
        setLocation(destination);
        setPendingNavigationView((current) => (current === next.view ? null : current));
        if (
          (next.view !== "explorer" &&
            next.view !== "target" &&
            next.view !== "drug" &&
            next.view !== "company" &&
            next.view !== "disease" &&
            next.view !== "entity") ||
          !next.entityId
        ) {
          setSelectedEntity(null);
        }
      };
      // Query, sort, pagination and display-state changes stay in the same view but can
      // still rerender a dense result surface. Keep the URL synchronous for sharing and
      // history, while scheduling the non-urgent React tree update as a transition.
      if (urgent) {
        setPendingNavigationView(null);
        commitLocation();
        return;
      }
      setPendingNavigationView(next.view === location.view ? null : next.view);
      startNavigationTransition(commitLocation);
    },
    [location.returnTo, location.view],
  );

  useEffect(() => {
    if (location.view !== "entity" || !routeEntity.data || routeEntity.data.id !== location.entityId) return;
    const specializedView =
      routeEntity.data.entity_type === "target"
        ? "target"
        : routeEntity.data.entity_type === "drug"
          ? "drug"
          : routeEntity.data.entity_type === "organization"
            ? "company"
            : routeEntity.data.entity_type === "disease"
              ? "disease"
              : null;
    if (!specializedView) return;
    setSelectedEntity(routeEntity.data);
    const mappedSection = specializedSectionByEntitySection[location.entitySection ?? "overview"];
    navigate(
      {
        ...location,
        view: specializedView,
        ...(specializedView === "target"
          ? { targetSection: mappedSection.target }
          : specializedView === "drug"
            ? { drugSection: mappedSection.drug }
            : specializedView === "company"
              ? { companySection: mappedSection.company }
              : { diseaseSection: mappedSection.disease }),
      },
      true,
    );
  }, [location, navigate, routeEntity.data]);

  const navigateToView = useCallback(
    (view: ViewKey) => {
      if (workbenchForView(view) !== "research") return;
      // Sidebar commands reset the draft query for the selected view. Commit this
      // command synchronously so a slow view transition cannot overwrite new input.
      navigate(
        {
          workbench: "research",
          view,
          query: "",
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
        },
        false,
        true,
      );
    },
    [navigate],
  );

  function openSavedSearch(saved: SavedSearch) {
    navigate(savedSearchLocation(saved));
  }

  function openEntity(entity: Entity) {
    const view =
      entity.entity_type === "target"
        ? "target"
        : entity.entity_type === "drug"
          ? "drug"
          : entity.entity_type === "organization"
            ? "company"
            : entity.entity_type === "disease"
              ? "disease"
              : "entity";
    setSelectedEntity(entity);
    navigate({
      workbench: "research",
      view,
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId: entity.id,
      invalidEntityId: false,
      returnTo: workspaceUrl(location),
      ...(view === "target"
        ? { targetSection: "overview" as const }
        : view === "drug"
          ? { drugSection: "overview" as const }
          : view === "company"
            ? { companySection: "overview" as const }
            : view === "disease"
              ? { diseaseSection: "overview" as const }
              : { entitySection: "overview" as const }),
    });
  }

  function openDrugById(entityId: string, returnTo?: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "drug",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      drugSection: "overview",
      returnTo: returnTo ?? workspaceUrl(location),
    });
  }

  function openEntityById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "entity",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      entitySection: "overview",
      returnTo: workspaceUrl(location),
    });
  }

  function openTargetById(entityId: string, returnTo?: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "target",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      targetSection: "overview",
      returnTo: returnTo ?? workspaceUrl(location),
    });
  }

  function openTargetPipelineById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "target",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      targetSection: "pipeline",
      returnTo: workspaceUrl(location),
    });
  }

  function openDiseaseById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "disease",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      diseaseSection: "overview",
      returnTo: workspaceUrl(location),
    });
  }

  function openOrganizationById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "company",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      companySection: "overview",
      returnTo: workspaceUrl(location),
    });
  }

  function openEpidemiologyForDisease(diseaseId: string) {
    navigate({
      workbench: "research",
      view: "epidemiology",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      epidemiologyDiseaseEntityId: diseaseId,
      offset: 0,
    });
  }

  function openTrialById(trialId: string, returnTo?: string) {
    navigate({
      workbench: "research",
      view: "trials",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      trialId,
      invalidTrialId: false,
      trialSection: "overview",
      offset: 0,
      returnTo: returnTo ?? workspaceUrl(location),
    });
  }

  function openDealById(dealId: string) {
    navigate({
      workbench: "research",
      view: "deals",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      dealId,
      invalidDealId: false,
      dealSection: "overview",
      offset: 0,
      returnTo: workspaceUrl(location),
    });
  }

  function openPatentFamilyById(patentId: string) {
    navigate({
      workbench: "research",
      view: "patents",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      patentId,
      invalidPatentId: false,
      offset: 0,
      returnTo: workspaceUrl(location),
    });
  }

  function openRegulatoryEventById(regulatoryEventId: string) {
    navigate({
      workbench: "research",
      view: "regulatory",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      regulatoryEventId,
      invalidRegulatoryEventId: false,
      regulatoryCompareIds: [],
      offset: 0,
      returnTo: workspaceUrl(location),
    });
  }

  function openNewsEventById(newsEventId: string) {
    navigate({
      workbench: "research",
      view: "news",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      newsEventId,
      invalidNewsEventId: false,
      offset: 0,
      returnTo: workspaceUrl(location),
    });
  }

  return {
    location,
    selectedEntity,
    setSelectedEntity,
    pendingNavigationView,
    activeReturnLocation,
    routeEntity,
    routeChemistrySavedSearch,
    navigate,
    navigateToView,
    openEntity,
    openDrugById,
    openEntityById,
    openTargetById,
    openTargetPipelineById,
    openDiseaseById,
    openOrganizationById,
    openEpidemiologyForDisease,
    openTrialById,
    openDealById,
    openPatentFamilyById,
    openRegulatoryEventById,
    openNewsEventById,
    openSavedSearch,
  };
}
