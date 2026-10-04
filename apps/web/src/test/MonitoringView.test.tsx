import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import {
  createMonitoringTopic,
  loadMonitoring,
  loadMonitoringAlertReplay,
  loadMonitoringTopicReplay,
  markMonitoringAlertRead,
  setMonitoringTopicActive,
  setMonitoringTopicQueryVersion,
  setSavedSearchVisibility,
  updateSavedSearchMetadata,
} from "../lib/contracts/monitoring";
import type { MonitoringAlert, MonitoringTopic, SavedSearch } from "../lib/types";
import { MonitoringView } from "../views/MonitoringView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/monitoring", () => ({
  monitoringKeys: { all: (unreadOnly: boolean) => ["monitoring", { unreadOnly }] },
  loadMonitoring: vi.fn(),
  loadMonitoringAlertReplay: vi.fn(),
  loadMonitoringTopicReplay: vi.fn(),
  createMonitoringTopic: vi.fn(),
  setMonitoringTopicActive: vi.fn(),
  setMonitoringTopicQueryVersion: vi.fn(),
  markMonitoringAlertRead: vi.fn(),
  setSavedSearchVisibility: vi.fn(),
  updateSavedSearchMetadata: vi.fn(),
}));

const saved: SavedSearch = {
  id: "saved-1",
  owner_user_id: "user-1",
  name: "EGFR competitors",
  description: "",
  query_type: "entity_search",
  query_version: 2,
  query_json: { q: "EGFR", entity_type: "target" },
  visibility: "tenant",
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};
const topic: MonitoringTopic = {
  id: "topic-1",
  owner_user_id: "user-1",
  saved_search_id: saved.id,
  query_version: 1,
  name: "EGFR changes",
  active: true,
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};
const alert: MonitoringAlert = {
  id: "alert-1",
  topic_id: topic.id,
  topic_name: topic.name,
  entity_id: "entity-1",
  entity_name: "EGFR",
  event_type: "canonical.entity.upserted",
  title: "EGFR changed",
  summary: "target 实体 EGFR 匹配监控条件。",
  payload_json: {},
  occurred_at: "2026-07-18T11:00:00Z",
  read_at: null,
};
const user = {
  id: "user-1",
  tenant_id: "tenant-1",
  email: "analyst@example.test",
  display_name: "Analyst",
  role: "analyst" as const,
};

beforeEach(() => {
  vi.mocked(loadMonitoringTopicReplay).mockResolvedValue({
    ...saved,
    query_version: 1,
    query_json: { q: "IFNA2", entity_type: "target" },
  });
  vi.mocked(loadMonitoringAlertReplay).mockResolvedValue({
    ...saved,
    query_version: 1,
    query_json: { q: "IFNA2", entity_type: "target" },
  });
  vi.mocked(loadMonitoring).mockResolvedValue({ searches: [saved], topics: [topic], alerts: [alert] });
  vi.mocked(markMonitoringAlertRead).mockResolvedValue(undefined);
  vi.mocked(createMonitoringTopic).mockResolvedValue(topic);
  vi.mocked(setMonitoringTopicActive).mockResolvedValue({ ...topic, active: false });
  vi.mocked(setMonitoringTopicQueryVersion).mockResolvedValue({ ...topic, query_version: 2 });
  vi.mocked(setSavedSearchVisibility).mockResolvedValue({ ...saved, visibility: "private" });
  vi.mocked(updateSavedSearchMetadata).mockResolvedValue({
    ...saved,
    name: "EGFR competitive landscape",
    description: "Quarterly competitor review",
  });
});

it("never substitutes the latest query when fixed replay is unavailable", async () => {
  vi.mocked(loadMonitoringTopicReplay).mockRejectedValue(new Error("Fixed version unavailable"));
  const openSearch = vi.fn();
  renderWithQueryClient(
    <MonitoringView user={user} activeTab="topics" onOpenEntity={vi.fn()} onOpenSearch={openSearch} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "运行 EGFR changes 固定检索" }));
  await screen.findByText("Fixed version unavailable");
  expect(openSearch).not.toHaveBeenCalled();
});

it("does not let a delayed fixed replay navigate after changing monitoring tabs", async () => {
  let finish!: (saved: SavedSearch) => void;
  vi.mocked(loadMonitoringTopicReplay).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const openSearch = vi.fn();
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);
  await screen.findByText("EGFR changes");
  fireEvent.click(screen.getByRole("tab", { name: "监控主题" }));
  const run = await screen.findByRole("button", { name: "运行 EGFR changes 固定检索" });
  fireEvent.click(run);
  fireEvent.click(run);
  await waitFor(() => expect(loadMonitoringTopicReplay).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole("tab", { name: "已保存检索" }));
  await act(async () => finish({ ...saved, query_version: 1 }));
  expect(openSearch).not.toHaveBeenCalled();
});

it("shows durable alerts, opens the matching entity and records a read receipt", async () => {
  const openEntity = vi.fn();
  const openSearch = vi.fn();
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={openEntity} onOpenSearch={openSearch} />);

  expect(await screen.findByText("EGFR changes")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "打开 EGFR" }));
  expect(openEntity).toHaveBeenCalledWith("entity-1");
  fireEvent.click(screen.getByRole("button", { name: "重放 EGFR changes 监控检索" }));
  await waitFor(() =>
    expect(openSearch).toHaveBeenCalledWith(
      expect.objectContaining({ query_version: 1, query_json: { q: "IFNA2", entity_type: "target" } }),
    ),
  );
  expect(loadMonitoringAlertReplay).toHaveBeenCalledWith("alert-1");
  fireEvent.click(screen.getByRole("button", { name: "将 EGFR 提醒标记已读" }));

  await waitFor(() => expect(markMonitoringAlertRead).toHaveBeenCalledWith("alert-1"));
  expect(screen.queryByRole("button", { name: "将 EGFR 提醒标记已读" })).not.toBeInTheDocument();
});

it("honors a routed monitoring tab and reports tab changes", async () => {
  const onTabChange = vi.fn();
  renderWithQueryClient(
    <MonitoringView
      user={user}
      activeTab="searches"
      onOpenEntity={vi.fn()}
      onOpenSearch={vi.fn()}
      onTabChange={onTabChange}
    />,
  );

  await screen.findByRole("button", { name: "运行 EGFR competitors" });
  expect(screen.getByRole("tab", { name: "已保存检索" })).toHaveAttribute("aria-selected", "true");
  fireEvent.click(screen.getByRole("tab", { name: "监控主题" }));
  expect(onTabChange).toHaveBeenCalledWith("topics");
});

it("creates and pauses monitoring topics from saved enterprise searches", async () => {
  const openSearch = vi.fn();
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);
  await screen.findByText("EGFR changes");
  fireEvent.click(screen.getByRole("tab", { name: "监控主题" }));
  fireEvent.change(await screen.findByLabelText("监控主题名称"), { target: { value: "EGFR daily" } });
  fireEvent.click(screen.getByRole("button", { name: "创建主题" }));
  await waitFor(() =>
    expect(createMonitoringTopic).toHaveBeenCalledWith({
      name: "EGFR daily",
      saved_search_id: "saved-1",
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "暂停 EGFR changes" }));
  await waitFor(() => expect(setMonitoringTopicActive).toHaveBeenCalledWith("topic-1", false));
  fireEvent.click(screen.getByRole("tab", { name: "监控主题" }));
  expect(screen.getByText("已保存检索有新版本；本主题仍按固定版本运行")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "运行 EGFR changes 固定检索" }));
  await waitFor(() =>
    expect(openSearch).toHaveBeenCalledWith(
      expect.objectContaining({ query_version: 1, query_json: { q: "IFNA2", entity_type: "target" } }),
    ),
  );
  expect(loadMonitoringTopicReplay).toHaveBeenCalledWith("topic-1");
  fireEvent.click(screen.getByRole("button", { name: "同步 EGFR changes 到检索 v2" }));
  await waitFor(() => expect(setMonitoringTopicQueryVersion).toHaveBeenCalledWith("topic-1", 2));
});

it("keeps a monitoring action error recoverable without hiding existing data", async () => {
  vi.mocked(markMonitoringAlertRead).mockRejectedValueOnce(new Error("提醒写入失败"));
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />);

  await screen.findByText("EGFR changes");
  fireEvent.click(screen.getByRole("button", { name: "将 EGFR 提醒标记已读" }));
  const error = await screen.findByRole("alert");
  expect(error).toHaveTextContent("提醒写入失败");
  expect(screen.getByText("EGFR changes")).toBeVisible();
  fireEvent.click(within(error).getByRole("button", { name: "重试" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
});

it("replays a saved search with every governed filter", async () => {
  const openSearch = vi.fn();
  vi.mocked(loadMonitoring).mockResolvedValueOnce({
    searches: [{ ...saved, query_json: { q: "EGFR", entity_type: "target", review_status: "verified" } }],
    topics: [topic],
    alerts: [],
  });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);

  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  fireEvent.click(screen.getByRole("button", { name: "运行 EGFR competitors" }));
  expect(openSearch).toHaveBeenCalledWith({
    ...saved,
    query_json: { q: "EGFR", entity_type: "target", review_status: "verified" },
  });
});

it("labels global saved-search types and presentation state for quick scanning", async () => {
  const statisticsSaved: SavedSearch = {
    ...saved,
    id: "saved-statistics",
    name: "EGFR landscape",
    query_json: {
      q: "EGFR",
      entity_types: ["target", "organization"],
      review_status: "verified",
      display_mode: "landscape",
      analysis_view: "table",
    },
  };
  vi.mocked(loadMonitoring).mockResolvedValueOnce({ searches: [statisticsSaved], topics: [], alerts: [] });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />);

  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  expect(screen.getByText("基础查询 · 靶点、机构")).toBeVisible();
  expect(screen.getByText("统计表")).toBeVisible();
  expect(screen.getByTitle("实体类型=靶点、机构")).toBeVisible();
  expect(document.body).not.toHaveTextContent("治理=已设置");
});

it("identifies and replays a saved professional pipeline query", async () => {
  const openSearch = vi.fn();
  const pipelineSaved: SavedSearch = {
    ...saved,
    id: "saved-pipeline",
    name: "EGFR global pipelines",
    query_type: "pipeline_search",
    query_json: {
      q: "EGFR",
      global_phase: "phase_2",
      display_mode: "landscape",
      analysis_dimension: "targets",
      analysis_limit: 50,
      analysis_stage_scope: "global",
      target_aggregation: "primary",
    },
  };
  vi.mocked(loadMonitoring).mockResolvedValueOnce({ searches: [pipelineSaved], topics: [], alerts: [] });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);

  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  expect(screen.getByText("药物与管线")).toBeVisible();
  expect(screen.getByText("统计图")).toBeVisible();
  expect(screen.getByTitle(/全球阶段=已设置.*分析维度=已设置.*分析范围=已设置/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "运行 EGFR global pipelines" }));
  expect(openSearch).toHaveBeenCalledWith(pipelineSaved);
});

it("identifies and replays a complete saved clinical trial query", async () => {
  const openSearch = vi.fn();
  const trialSaved: SavedSearch = {
    ...saved,
    id: "saved-trials",
    name: "EGFR recruiting results",
    query_type: "clinical_trial_search",
    query_json: {
      q: "EGFR",
      registry: "ClinicalTrials.gov",
      status: "RECRUITING",
      phase: "PHASE2",
      has_results: true,
      result_evaluation: "positive",
      results_posted_from: "2026-07-01",
      results_posted_to: "2026-07-31",
      sort_by: "result_evaluation",
      sort_direction: "asc",
    },
  };
  vi.mocked(loadMonitoring).mockResolvedValueOnce({ searches: [trialSaved], topics: [], alerts: [] });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);

  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  expect(screen.getByText("临床试验")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "运行 EGFR recruiting results" }));
  expect(openSearch).toHaveBeenCalledWith(trialSaved);
});

it("identifies and replays patent and deal saved queries", async () => {
  const openSearch = vi.fn();
  const patentSaved: SavedSearch = {
    ...saved,
    id: "saved-patents",
    name: "Active EGFR patents",
    query_type: "patent_search",
    query_json: { q: "EGFR", applicant: "Victor Therapeutics", legal_status: "ACTIVE" },
  };
  const dealSaved: SavedSearch = {
    ...saved,
    id: "saved-deals",
    name: "Outbound licenses",
    query_type: "deal_search",
    query_json: { status: "active", direction: "outbound", territory: "Greater China" },
  };
  vi.mocked(loadMonitoring).mockResolvedValueOnce({ searches: [patentSaved, dealSaved], topics: [], alerts: [] });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);

  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  expect(screen.getByText("专利情报")).toBeVisible();
  expect(screen.getByText("交易与公司")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "运行 Active EGFR patents" }));
  fireEvent.click(screen.getByRole("button", { name: "运行 Outbound licenses" }));
  expect(openSearch).toHaveBeenNthCalledWith(1, patentSaved);
  expect(openSearch).toHaveBeenNthCalledWith(2, dealSaved);
});

it("identifies and replays a complete regulatory safety query", async () => {
  const openSearch = vi.fn();
  const regulatorySaved: SavedSearch = {
    ...saved,
    id: "saved-regulatory",
    name: "FDA pulmonary signals",
    query_type: "regulatory_search",
    query_json: {
      q: "VX-101",
      agency: "FDA",
      jurisdiction: "US",
      event_type: "safety_signal",
      has_boxed_warning: false,
      safety_signal_type: "adverse_event",
      safety_severity: "serious",
      safety_status: "confirmed",
      decision_from: "2026-02-01",
      decision_to: "2026-02-28",
      sort_by: "source_updated_at",
      sort_direction: "asc",
    },
  };
  vi.mocked(loadMonitoring).mockResolvedValueOnce({ searches: [regulatorySaved], topics: [], alerts: [] });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);

  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  expect(screen.getByText("监管与安全")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "运行 FDA pulmonary signals" }));
  expect(openSearch).toHaveBeenCalledWith(regulatorySaved);
});

it("identifies and replays epidemiology and research-news queries", async () => {
  const openSearch = vi.fn();
  const epidemiologySaved: SavedSearch = {
    ...saved,
    id: "saved-epidemiology",
    name: "China NSCLC burden",
    query_type: "epidemiology_search",
    query_json: {
      disease_entity_id: "550e8400-e29b-41d4-a716-446655440001",
      measure: "prevalence",
      geography: "China",
      period_start_from: "2025-01-01",
      period_end_to: "2025-12-31",
      sort_by: "value",
    },
  };
  const newsSaved: SavedSearch = {
    ...saved,
    id: "saved-news",
    name: "ASCO research watch",
    query_type: "news_search",
    query_json: {
      q: "VX-101",
      event_type: "poster",
      publisher: "ASCO",
      venue: "ASCO 2026",
      content_scope: "research",
      display_mode: "timeline",
    },
  };
  const chemistrySaved: SavedSearch = {
    ...saved,
    id: "saved-chemistry",
    name: "Aspirin similarity",
    query_type: "chemistry_search",
    query_json: {
      mode: "similarity",
      query: "CC(=O)Oc1ccccc1C(=O)O",
      threshold: 0.75,
      limit: 20,
    },
  };
  vi.mocked(loadMonitoring).mockResolvedValueOnce({
    searches: [epidemiologySaved, newsSaved, chemistrySaved],
    topics: [],
    alerts: [],
  });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={openSearch} />);

  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  expect(screen.getByText("流行病学")).toBeVisible();
  expect(screen.getByText("新闻与会议")).toBeVisible();
  expect(screen.getByText("结构检索")).toBeVisible();
  expect(screen.getByText(/结构原文受控保存/)).toBeVisible();
  expect(screen.queryByText("CC(=O)Oc1ccccc1C(=O)O")).not.toBeInTheDocument();
  expect(screen.getByText("时间线")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "运行 China NSCLC burden" }));
  fireEvent.click(screen.getByRole("button", { name: "运行 ASCO research watch" }));
  fireEvent.click(screen.getByRole("button", { name: "运行 Aspirin similarity" }));
  expect(openSearch).toHaveBeenNthCalledWith(1, epidemiologySaved);
  expect(openSearch).toHaveBeenNthCalledWith(2, newsSaved);
  expect(openSearch).toHaveBeenNthCalledWith(3, chemistrySaved);
});

it("does not offer chemistry saved searches as unsupported monitoring topics", async () => {
  const chemistrySaved: SavedSearch = {
    ...saved,
    id: "saved-chemistry-topic",
    name: "Aspirin similarity",
    query_type: "chemistry_search",
    query_json: { mode: "similarity", query: "CC", threshold: 0.75, limit: 20 },
  };
  vi.mocked(loadMonitoring).mockResolvedValueOnce({ searches: [chemistrySaved], topics: [], alerts: [] });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />);

  fireEvent.click(await screen.findByRole("tab", { name: "监控主题" }));
  expect(screen.queryByRole("option", { name: chemistrySaved.name })).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: "暂无可订阅检索" })).toBeDisabled();
});

it("lets only the owner change a saved search sharing boundary", async () => {
  const { unmount } = renderWithQueryClient(
    <MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />,
  );
  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  fireEvent.click(screen.getByRole("button", { name: "将 EGFR competitors 设为私有" }));
  await waitFor(() => expect(setSavedSearchVisibility).toHaveBeenCalledWith("saved-1", "private"));

  unmount();
  vi.mocked(loadMonitoring).mockResolvedValueOnce({
    searches: [{ ...saved, owner_user_id: "another-user" }],
    topics: [],
    alerts: [],
  });
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />);
  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  expect(screen.getByText("共享给你的只读检索")).toBeVisible();
  expect(screen.queryByRole("button", { name: "将 EGFR competitors 设为私有" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "编辑 EGFR competitors" })).not.toBeInTheDocument();
});

it("lets the owner maintain saved-search metadata without changing its governed query", async () => {
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />);
  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  fireEvent.click(screen.getByRole("button", { name: "编辑 EGFR competitors" }));

  const dialog = screen.getByRole("dialog", { name: "编辑已保存检索" });
  fireEvent.change(within(dialog).getByLabelText("名称"), { target: { value: " EGFR competitive landscape " } });
  fireEvent.change(within(dialog).getByLabelText("业务说明"), { target: { value: " Quarterly competitor review " } });
  fireEvent.click(within(dialog).getByRole("button", { name: "保存修改" }));

  await waitFor(() =>
    expect(updateSavedSearchMetadata).toHaveBeenCalledWith("saved-1", {
      name: "EGFR competitive landscape",
      description: "Quarterly competitor review",
    }),
  );
  expect(updateSavedSearchMetadata).toHaveBeenCalledTimes(1);
});

it("keeps the saved-search editor recoverable when the update is rejected", async () => {
  vi.mocked(updateSavedSearchMetadata).mockRejectedValueOnce(new Error("已存在同名检索"));
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />);
  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  fireEvent.click(screen.getByRole("button", { name: "编辑 EGFR competitors" }));

  const dialog = screen.getByRole("dialog", { name: "编辑已保存检索" });
  fireEvent.click(within(dialog).getByRole("button", { name: "保存修改" }));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent("已存在同名检索");
  expect(dialog).toBeVisible();
  expect(within(dialog).getByRole("button", { name: "保存修改" })).toBeEnabled();
});
