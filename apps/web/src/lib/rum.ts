import type { MetricType } from "web-vitals";

import type { WebVitalBatchCreate, WebVitalSampleCreate } from "./generated";

const supportedMetricNames = new Set<WebVitalSampleCreate["metric_name"]>(["CLS", "INP", "LCP", "TTFB"]);
const navigationTypes = new Set<WebVitalSampleCreate["navigation_type"]>([
  "navigate",
  "reload",
  "back-forward",
  "back-forward-cache",
  "prerender",
  "restore",
  "soft-navigation",
]);
const researchRoutes = new Set<WebVitalSampleCreate["route"]>([
  "overview",
  "explorer",
  "chemistry",
  "pipeline",
  "trials",
  "patents",
  "deals",
  "regulatory",
  "epidemiology",
  "news",
  "target",
  "drug",
  "company",
  "disease",
  "entity",
  "evidence",
  "knowledge",
  "monitoring",
  "collections",
]);
const metricThresholds: Record<WebVitalSampleCreate["metric_name"], readonly [number, number]> = {
  CLS: [0.1, 0.25],
  INP: [200, 500],
  LCP: [2500, 4000],
  TTFB: [800, 1800],
};
const maximumSamplesPerPage = 32;
const maximumBatchSize = 8;
const maximumPayloadBytes = 8192;
const flushDelayMs = 1500;

type RumTransport = (batch: WebVitalBatchCreate, keepalive: boolean) => Promise<boolean>;

function csrfCookie(): string {
  const value = document.cookie
    .split("; ")
    .find((item) => item.startsWith("pharma_csrf="))
    ?.slice("pharma_csrf=".length);
  return value ? decodeURIComponent(value) : "";
}

function metricRating(metricName: WebVitalSampleCreate["metric_name"], value: number): WebVitalSampleCreate["rating"] {
  const [goodThreshold, poorThreshold] = metricThresholds[metricName];
  if (value <= goodThreshold) return "good";
  if (value <= poorThreshold) return "needs-improvement";
  return "poor";
}

export function researchRumRoute(rawUrl: string | undefined): WebVitalSampleCreate["route"] {
  try {
    const url = new URL(rawUrl ?? window.location.href, window.location.origin);
    if (url.origin !== window.location.origin) return "unknown";
    if (["/", "/index.html", "/research.html"].includes(url.pathname)) return "overview";
    if (url.pathname !== "/workspace/research") return "unknown";
    const view = url.searchParams.get("view") ?? "overview";
    return researchRoutes.has(view as WebVitalSampleCreate["route"])
      ? (view as WebVitalSampleCreate["route"])
      : "unknown";
  } catch {
    return "unknown";
  }
}

export function rumViewportClass(width: number): WebVitalSampleCreate["viewport_class"] {
  if (!Number.isFinite(width) || width <= 0) return "desktop";
  if (width <= 479) return "mobile";
  if (width <= 1199) return "tablet";
  return "desktop";
}

export function webVitalSample(
  metric: MetricType,
  rawUrl = metric.navigationURL,
  viewportWidth = window.innerWidth,
): WebVitalSampleCreate | null {
  if (!supportedMetricNames.has(metric.name as WebVitalSampleCreate["metric_name"])) return null;
  const metricName = metric.name as WebVitalSampleCreate["metric_name"];
  if (!Number.isFinite(metric.value) || metric.value < 0) return null;
  const value = metricName === "CLS" ? Math.round(metric.value * 10_000) / 10_000 : Math.round(metric.value);
  if ((metricName === "CLS" && value > 10) || (metricName !== "CLS" && value > 120_000)) return null;
  const navigationType = navigationTypes.has(metric.navigationType as WebVitalSampleCreate["navigation_type"])
    ? (metric.navigationType as WebVitalSampleCreate["navigation_type"])
    : "navigate";
  const navigationSequence =
    Number.isInteger(metric.navigationId) && metric.navigationId >= 0 ? Math.min(metric.navigationId, 10_000) : 0;
  return {
    metric_name: metricName,
    navigation_sequence: navigationSequence,
    navigation_type: navigationType,
    rating: metricRating(metricName, value),
    route: researchRumRoute(rawUrl),
    value,
    viewport_class: rumViewportClass(viewportWidth),
  };
}

export async function sendResearchRum(batch: WebVitalBatchCreate, keepalive: boolean): Promise<boolean> {
  const body = JSON.stringify(batch);
  if (new Blob([body]).size > maximumPayloadBytes) return false;
  const headers = new Headers({ "Content-Type": "application/json" });
  const csrf = csrfCookie();
  if (csrf) headers.set("X-CSRF-Token", csrf);
  try {
    const response = await fetch("/api/v1/workspace/web-vitals", {
      method: "POST",
      body,
      credentials: "same-origin",
      headers,
      keepalive,
    });
    if (response.status !== 202) return false;
    if (keepalive) return true;
    const payload = (await response.json().catch(() => null)) as {
      accepted_count?: unknown;
      schema_version?: unknown;
    } | null;
    return payload?.schema_version === 1 && payload.accepted_count === batch.samples.length;
  } catch {
    return false;
  }
}

export function createResearchRumReporter(transport: RumTransport = sendResearchRum) {
  const pending = new Map<string, WebVitalSampleCreate>();
  let acceptedSamples = 0;
  let consecutiveFailures = 0;
  let flushTimer: number | null = null;
  let flushing = false;

  function clearTimer() {
    if (flushTimer !== null) window.clearTimeout(flushTimer);
    flushTimer = null;
  }

  function schedule(delay = flushDelayMs) {
    if (flushTimer !== null || flushing || pending.size === 0) return;
    flushTimer = window.setTimeout(() => {
      flushTimer = null;
      void flush(false);
    }, delay);
  }

  function report(metric: MetricType) {
    if (acceptedSamples + pending.size >= maximumSamplesPerPage) return;
    const sample = webVitalSample(metric);
    if (!sample) return;
    pending.set(`${sample.navigation_sequence}:${sample.metric_name}`, sample);
    schedule();
  }

  async function flush(keepalive: boolean): Promise<boolean> {
    if (flushing || pending.size === 0) return false;
    clearTimer();
    const entries = Array.from(pending.entries()).slice(0, maximumBatchSize);
    const batch: WebVitalBatchCreate = {
      schema_version: 1,
      samples: entries.map(([, sample]) => sample),
    };
    flushing = true;
    const succeeded = await transport(batch, keepalive);
    flushing = false;
    if (succeeded) {
      for (const [key, sample] of entries) {
        if (pending.get(key) === sample) pending.delete(key);
      }
      acceptedSamples += entries.length;
      consecutiveFailures = 0;
      schedule();
      return true;
    }
    consecutiveFailures += 1;
    if (keepalive || consecutiveFailures >= 2) {
      for (const [key, sample] of entries) {
        if (pending.get(key) === sample) pending.delete(key);
      }
      consecutiveFailures = 0;
    } else {
      schedule(5000);
    }
    return false;
  }

  function dispose() {
    clearTimer();
    pending.clear();
  }

  return {
    dispose,
    flush,
    pendingCount: () => pending.size,
    report,
  };
}

let researchRumStarted = false;

export async function startResearchRum(): Promise<void> {
  if (researchRumStarted || typeof window === "undefined" || typeof PerformanceObserver === "undefined") return;
  researchRumStarted = true;
  const reporter = createResearchRumReporter();
  try {
    const { onCLS, onINP, onLCP, onTTFB } = await import("web-vitals");
    const options = { reportSoftNavs: true };
    onCLS(reporter.report, options);
    onINP(reporter.report, options);
    onLCP(reporter.report, options);
    onTTFB(reporter.report, options);
  } catch {
    reporter.dispose();
    researchRumStarted = false;
    return;
  }
  const flushWhenHidden = () => {
    if (document.visibilityState === "hidden") void reporter.flush(true);
  };
  document.addEventListener("visibilitychange", flushWhenHidden);
  window.addEventListener("pagehide", () => void reporter.flush(true));
}
