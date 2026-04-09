import { useCallback, useEffect, useState } from "react";

import { motion, useReducedMotion } from "framer-motion";
import { useTranslation } from "react-i18next";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { Skeleton } from "@heroui/react/skeleton";
import { Switch } from "@heroui/react/switch";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PageHeader } from "@/components/PageHeader";
import { useThemeModeContext } from "@/context/ThemeModeContext";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { staggerContainer, staggerItemSubtle } from "@/lib/motion";
import { toast } from "@/lib/appToast";
import { listCas, setDataDir } from "@/api";

export function SettingsPage() {
  const { t } = useTranslation();
  usePageTitle(t("pageTitles.settings"));
  const reduceMotion = useReducedMotion();
  const { mode, setMode } = useThemeModeContext();
  const [dataDir, setDataDirState] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listCas();
      setDataDirState(r.data_dir);
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onSaveDir = async () => {
    try {
      const r = await setDataDir(dataDir);
      toast.success(t("ca.msgDirSaved", { path: r.data_dir }));
      await refresh();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    }
  };

  return (
    <>
      <PageHeader title={t("settings.title")} description={t("settings.description")} />

      <motion.div
        className="flex flex-col gap-6"
        variants={staggerContainer}
        initial={reduceMotion ? "show" : "hidden"}
        animate="show"
      >
        <motion.div variants={staggerItemSubtle}>
          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <Card.Header className="px-6 pt-6">
              <Card.Title className="text-lg text-slate-900 dark:text-slate-50">{t("settings.themeTitle")}</Card.Title>
              <Card.Description className="text-slate-600 dark:text-slate-300">{t("settings.themeDesc")}</Card.Description>
            </Card.Header>
            <Card.Content className="px-6 pb-6">
              <Switch.Root
                className="flex max-w-md items-center justify-between gap-4"
                isSelected={mode === "dark"}
                onChange={(v) => setMode(v ? "dark" : "light")}
              >
                <Switch.Content className="text-sm font-medium text-slate-800 dark:text-slate-100">
                  {mode === "dark" ? t("settings.themeDark") : t("settings.themeLight")}
                </Switch.Content>
                <Switch.Control>
                  <Switch.Thumb />
                </Switch.Control>
              </Switch.Root>
            </Card.Content>
          </Card.Root>
        </motion.div>

        <motion.div variants={staggerItemSubtle}>
          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <Card.Header className="px-6 pt-6">
              <Card.Title className="text-lg text-slate-900 dark:text-slate-50">{t("settings.languageTitle")}</Card.Title>
              <Card.Description className="text-slate-600 dark:text-slate-300">{t("settings.languageDesc")}</Card.Description>
            </Card.Header>
            <Card.Content className="px-6 pb-6">
              <LanguageSwitcher className="max-w-md" />
            </Card.Content>
          </Card.Root>
        </motion.div>

        <motion.div variants={staggerItemSubtle}>
          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <Card.Header className="px-6 pt-6">
              <Card.Title className="text-lg text-slate-900 dark:text-slate-50">{t("ca.dataDirTitle")}</Card.Title>
              <Card.Description className="text-slate-600 dark:text-slate-300">
                {t("ca.dataDirDesc", { pattern: t("ca.dataDirPattern") })}
              </Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4 px-6 pb-6">
              {loading ? (
                <Skeleton.Root className="h-10 w-full max-w-3xl rounded-lg" />
              ) : (
                <>
                  <div className="flex flex-col gap-2">
                    <Label.Root className="text-slate-700 dark:text-slate-200">{t("common.path")}</Label.Root>
                    <Input.Root
                      value={dataDir}
                      onChange={(e) => setDataDirState(e.target.value)}
                      className="max-w-3xl"
                    />
                  </div>
                  <Button variant="primary" onPress={onSaveDir}>
                    {t("ca.saveDir")}
                  </Button>
                </>
              )}
            </Card.Content>
          </Card.Root>
        </motion.div>
      </motion.div>
    </>
  );
}
