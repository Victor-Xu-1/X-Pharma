import { createTranslator } from "./translator";

export const sourceMetadataMessages = {
  补充信息: "Supplementary source fields",
  完整补充信息: "Complete source metadata",
  完整原始补充信息: "Complete original source metadata",
  未披露: "Not provided",
} as const;

export const sourceMetadataText = createTranslator(sourceMetadataMessages);
