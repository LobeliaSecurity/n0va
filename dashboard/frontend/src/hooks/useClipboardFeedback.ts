import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/lib/appToast";

/**
 * クリップボードへコピーし、結果を Toast で通知する。
 */
export function useClipboardFeedback() {
  const { t } = useTranslation();

  const copy = useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text);
        toast.success(t("common.copied"));
      } catch {
        toast.danger(t("common.copyFailed"));
      }
    },
    [t],
  );

  return { copy };
}
