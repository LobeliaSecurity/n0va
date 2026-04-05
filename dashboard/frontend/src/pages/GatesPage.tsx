import { useCallback, useEffect, useState } from "react";

import { motion, useReducedMotion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Chip } from "@heroui/react/chip";
import { Text } from "@heroui/react/text";

import { ConfirmAlertDialog } from "@/components/ConfirmAlertDialog";
import { PageHeader } from "@/components/PageHeader";
import { staggerContainer, staggerItem } from "@/lib/motion";
import { toast } from "@/lib/appToast";
import { summarizeGate } from "@/gate/summarizeGate";
import { deleteGate, listGates, startGate, stopGate, type GateDto } from "@/api";

export function GatesPage() {
  const { t } = useTranslation();
  const reduceMotion = useReducedMotion();
  const navigate = useNavigate();
  const [gates, setGates] = useState<GateDto[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listGates();
      setGates(r.gates);
    } catch (e) {
      toast.danger((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onStart = async (id: number) => {
    try {
      await startGate(id);
      await refresh();
    } catch (e) {
      toast.danger((e as Error).message);
    }
  };

  const onStop = async (id: number) => {
    try {
      await stopGate(id);
      await refresh();
    } catch (e) {
      toast.danger((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title={t("gates.title")}
        description={t("gates.description")}
        actions={
          <Button variant="primary" onPress={() => navigate("/gates/new")}>
            {t("gates.newGate")}
          </Button>
        }
      />

      {loading && (
        <p className="mb-6 text-sm text-slate-500" aria-live="polite">
          {t("common.loading")}
        </p>
      )}

      <motion.div
        className="flex flex-col gap-4"
        variants={staggerContainer}
        initial={reduceMotion ? "show" : "hidden"}
        animate="show"
      >
        {gates.map((g) => {
          const { listen, entrance } = summarizeGate(g, t);
          return (
            <motion.div key={g.id} variants={staggerItem}>
            <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <Card.Header className="flex flex-row flex-wrap items-start justify-between gap-4 px-6 pt-6">
                <div className="min-w-0 flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Card.Title className="text-base text-slate-900">{g.name}</Card.Title>
                    <span className="font-mono text-xs text-slate-400">#{g.id}</span>
                    <Chip color={g.running ? "success" : "default"} variant="secondary" size="sm">
                      {g.running ? t("common.running") : t("common.stopped")}
                    </Chip>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
                    <span>
                      <span className="text-slate-400">{t("common.listen")} </span>
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">
                        {listen}
                      </code>
                    </span>
                    <span>
                      <span className="text-slate-400">{t("common.entrance")} </span>
                      <span className="font-medium text-slate-800">{entrance}</span>
                    </span>
                  </div>
                  {g.updated_at && (
                    <Card.Description className="font-mono text-xs text-slate-400">
                      {t("common.updated", { when: g.updated_at })}
                    </Card.Description>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {!g.running ? (
                    <Button size="sm" variant="primary" onPress={() => onStart(g.id)}>
                      {t("common.start")}
                    </Button>
                  ) : (
                    <Button size="sm" variant="secondary" onPress={() => onStop(g.id)}>
                      {t("common.stop")}
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" onPress={() => navigate(`/gates/${g.id}`)}>
                    {t("common.configure")}
                  </Button>
                  <ConfirmAlertDialog
                    title={t("common.confirmDeleteTitle")}
                    body={t("gates.confirmDelete", { id: g.id })}
                    cancelLabel={t("common.cancel")}
                    confirmLabel={t("common.deleteConfirm")}
                    onConfirm={async () => {
                      try {
                        await deleteGate(g.id);
                        await refresh();
                      } catch (e) {
                        toast.danger((e as Error).message);
                        throw e;
                      }
                    }}
                    trigger={<Button size="sm" variant="secondary">{t("common.delete")}</Button>}
                  />
                </div>
              </Card.Header>
            </Card.Root>
            </motion.div>
          );
        })}
        {gates.length === 0 && !loading && (
          <motion.div variants={staggerItem} className="rounded-xl border border-dashed border-slate-300 bg-slate-50/80 px-6 py-14 text-center">
            <p className="text-sm font-medium text-slate-800">{t("gates.emptyTitle")}</p>
            <p className="mt-2 mx-auto max-w-md text-sm text-slate-600">{t("gates.emptyBody")}</p>
            <Button className="mt-6" variant="primary" onPress={() => navigate("/gates/new")}>
              {t("gates.emptyCta")}
            </Button>
          </motion.div>
        )}
      </motion.div>

      <motion.div
        initial={reduceMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: reduceMotion ? 0 : 0.12, duration: reduceMotion ? 0 : 0.25 }}
      >
        <Text className="mt-10 text-xs text-slate-500">{t("gates.tip")}</Text>
      </motion.div>
    </>
  );
}
