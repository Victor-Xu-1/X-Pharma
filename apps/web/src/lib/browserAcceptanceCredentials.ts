export const browserProjectNames = ["desktop-1440", "desktop-1920", "tablet-1024", "mobile-390"] as const;
const projectNames = new Set<string>(browserProjectNames);
const emailPrefixPattern = /^e2e-[a-z0-9-]{8,80}$/;

type BrowserEnvironment = Readonly<Record<string, string | undefined>>;

export type BrowserCredentials = {
  email: string;
  password: string;
};

export function resolveBrowserCredentials(
  projectName: string,
  environment: BrowserEnvironment,
): BrowserCredentials | null {
  const emailPrefix = environment.E2E_EMAIL_PREFIX;
  const password = environment.E2E_PASSWORD;
  if (!emailPrefix || !password) return null;
  if (!projectNames.has(projectName)) throw new Error(`Unsupported browser acceptance project: ${projectName}`);
  if (!emailPrefixPattern.test(emailPrefix)) throw new Error("Browser acceptance email prefix is invalid");
  return { email: `${emailPrefix}-${projectName}@example.test`, password };
}
