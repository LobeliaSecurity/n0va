import { useEffect } from "react";

import clsx from "clsx";
import { useTranslation } from "react-i18next";

import { Label } from "@heroui/react/label";
import { ListBox } from "@heroui/react/list-box";
import { Select } from "@heroui/react/select";

type LanguageSwitcherProps = {
  className?: string;
};

export function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const { i18n, t } = useTranslation();

  useEffect(() => {
    document.documentElement.lang = i18n.language === "ja" ? "ja" : "en-GB";
  }, [i18n.language]);

  const langKey = i18n.language === "ja" ? "ja" : "en-GB";

  return (
    <div className={clsx("flex flex-col gap-1.5", className)}>
      <Label.Root className="text-xs font-medium text-slate-600" id="language-switcher-label">
        {t("language.label")}
      </Label.Root>
      <Select.Root
        fullWidth
        aria-labelledby="language-switcher-label"
        selectedKey={langKey}
        onSelectionChange={(key) => {
          if (key) void i18n.changeLanguage(String(key));
        }}
      >
        <Select.Trigger className="w-full justify-between">
          <Select.Value />
          <Select.Indicator />
        </Select.Trigger>
        <Select.Popover>
          <ListBox.Root>
            <ListBox.Item id="en-GB" textValue={t("language.enGB")}>
              {t("language.enGB")}
            </ListBox.Item>
            <ListBox.Item id="ja" textValue={t("language.ja")}>
              {t("language.ja")}
            </ListBox.Item>
          </ListBox.Root>
        </Select.Popover>
      </Select.Root>
    </div>
  );
}
