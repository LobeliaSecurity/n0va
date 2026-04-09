import { useTranslation } from "react-i18next";

import { Link } from "@heroui/react/link";

export function SkipToMainLink() {
  const { t } = useTranslation();
  return (
    <Link.Root
      href="#main-content"
      className="pointer-events-none fixed left-4 top-4 z-[100] -translate-y-24 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white opacity-0 shadow-lg outline-none ring-indigo-400 transition-all focus:pointer-events-auto focus:translate-y-0 focus:opacity-100 focus:ring-2"
    >
      {t("a11y.skipToContent")}
    </Link.Root>
  );
}
