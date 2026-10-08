import { createTranslator } from "./translator";
export const provenanceMessages = {
  "部分技术字段因来源许可限制未展示。": "Some technical fields are omitted under the source license.",
  "部分来源信息暂不可访问。": "Some source information is temporarily inaccessible.",
  "部分来源信息暂未展示。": "Some source information is not currently displayed.",
  来源署名未提供: "Source attribution not provided",
  用户提供的来源材料: "User-provided source material",
  关闭证据面板: "Close evidence panel",
  来源与证据: "Sources and evidence",
  原始证据: "Original evidence",
  关闭: "Close",
  关闭原始证据: "Close original evidence",
  正在读取授权证据: "Loading permitted evidence",
  暂无可展示证据: "No displayable evidence",
  "该记录可能尚未关联公开来源，或来源暂不可访问":
    "This record may not have a linked public source, or its source may be inaccessible.",
  来源记录: "Source record",
  文档名称未提供: "Document name not provided",
  "暂无可展示原文片段。": "No original text excerpt is available for display.",
  原文位置: "Location in source",
  未标注: "Not specified",
  证据状态: "Evidence status",
  已提供原文片段: "Original text excerpt provided",
  暂无可展示原文片段: "Original text excerpt unavailable",
  查看来源: "View source",
  查看原始证据: "View original evidence",
  "查看 {label} 的原始证据": "View original evidence for {label}",
} as const;
export const provenanceText = createTranslator(provenanceMessages);
