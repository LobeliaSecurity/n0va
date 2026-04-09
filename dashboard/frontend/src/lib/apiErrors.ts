import type { TFunction } from "i18next";

export function formatApiError(error: unknown, t: TFunction): string {
  if (error instanceof TypeError && /fetch|network|load failed/i.test(error.message)) {
    return t("errors.network");
  }
  if (error instanceof Error) {
    const m = error.message;
    if (m.startsWith("HTTP ")) {
      const code = m.slice(5).trim();
      if (code === "401" || code === "403") return t("errors.forbidden");
      if (code === "404") return t("errors.notFound");
      if (code === "500" || code === "502" || code === "503" || code === "504") return t("errors.server");
    }
    return m;
  }
  return t("errors.unknown");
}
