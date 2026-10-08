import { identityMessages } from "./identity";
import { navigationMessages } from "./navigation";
import { sharedMessages } from "./shared";

export const messages = { ...navigationMessages, ...identityMessages, ...sharedMessages } as const;
export type MessageKey = keyof typeof messages;
export type MessageParameters = Readonly<Record<string, string | number>>;

export function isMessageKey(value: string): value is MessageKey {
  return Object.hasOwn(messages, value);
}
