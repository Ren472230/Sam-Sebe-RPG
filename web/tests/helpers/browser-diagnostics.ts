import { expect, type Page, type TestInfo } from "@playwright/test";

export type BrowserDiagnostics = {
  consoleErrors: string[];
  pageErrors: string[];
  attach(testInfo: TestInfo): Promise<void>;
  assertClean(): void;
};

export function installBrowserDiagnostics(page: Page): BrowserDiagnostics {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(`${error.name}: ${error.message}`);
  });

  return {
    consoleErrors,
    pageErrors,
    async attach(testInfo: TestInfo): Promise<void> {
      await testInfo.attach("browser-console-errors", {
        body: Buffer.from(consoleErrors.join("\n") || "none", "utf8"),
        contentType: "text/plain"
      });
      await testInfo.attach("page-errors", {
        body: Buffer.from(pageErrors.join("\n") || "none", "utf8"),
        contentType: "text/plain"
      });
    },
    assertClean(): void {
      expect(consoleErrors, "browser console errors").toEqual([]);
      expect(pageErrors, "unhandled page errors").toEqual([]);
    }
  };
}
