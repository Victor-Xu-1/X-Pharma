import type { MessageParameters } from "../../lib/i18n";
import type { factoryValidationMessages } from "../../lib/i18n/factoryValidation";

/** Typed application validation only. Provider/API messages must not use this class. */
export class SourceDraftValidationError extends Error {
  constructor(
    public readonly key: keyof typeof factoryValidationMessages,
    public readonly parameters: MessageParameters = {},
  ) {
    super(key);
  }
}
