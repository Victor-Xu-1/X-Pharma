import { createTranslator } from "./translator";

export const comparisonMessages = {
  加入列表: "Add to list",
  "加入列表（{count}）": "Add to list ({count})",
  加入对比列表: "Add to comparison list",
  关闭: "Close",
  "已选择 {count} 个实体": "{count} entities selected",
  正在读取可编辑列表: "Loading editable lists",
  目标列表: "Destination list",
  "当前列表不可访问，请选择其他列表": "This list is unavailable. Choose another list.",
  "当前目录没有可选择的列表。可调整搜索，或创建新列表后加入已选实体。":
    "No selectable lists in this directory. Adjust the search or create a list for the selected entities.",
  新建列表: "New list",
  "例如：EGFR 竞品对比": "For example: EGFR competitor comparison",
  与团队共享: "Share with team",
  "其中 {existing} 个已在列表中，本次将新增 {added} 个": "{existing} already in this list; {added} will be added",
  "已选择的 {count} 个实体均已在列表中": "All {count} selected entities are already in this list",
  "完成后共 {count}/20 个实体": "After completion: {count}/20 entities",
  取消: "Cancel",
  处理中: "Processing",
  确认加入: "Confirm addition",
  完成: "Done",
  创建并加入: "Create and add",
  搜索列表名称或说明: "Search list names or descriptions",
  搜索列表: "Search lists",
  筛选列表: "Filter lists",
  列表目录分页: "List directory pagination",
  列表目录上一页: "Previous directory page",
  列表目录下一页: "Next directory page",
  "第 {page} / {pages} 页 · 共 {count} 条": "Page {page} / {pages} · {count} lists",
  "列表内容刚刚发生变化，请重新确认后再试": "This list just changed. Review it before trying again.",
  "该对比列表已达到 20 个实体上限": "This comparison list has reached its 20-entity limit",
  "列表内容已更新，请重新确认后再试": "This list has been updated. Review it before trying again.",
  "所选实体均已在 {name} 中，无需重复添加": "All selected entities are already in {name}; no duplicates were added",
  "该列表还可添加 {count} 个实体，请减少选择后重试":
    "This list has room for {count} more entities. Reduce the selection and retry.",
  "{count} 个实体已加入 {name}": "{count} entities added to {name}",
  "，已跳过 {count} 个已存在实体": "; skipped {count} existing entities",
  "加入对比列表失败，请稍后重试": "Could not add to the comparison list. Try again later.",
  "列表已创建，但成员尚未加入；已保留新列表，请重新确认加入。{reason}":
    "The list was created, but members were not added. The new list is retained; review and retry the addition. {reason}",
  成员写入失败: "Could not add members",
  "创建对比列表失败，请稍后重试": "Could not create the comparison list. Try again later.",
  "对比列表加载失败，请稍后重试": "Could not load comparison lists. Try again later.",
} as const;

export const comparisonText = createTranslator(comparisonMessages);
