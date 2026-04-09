import { useCallback, useEffect, useMemo, useState } from "react";

import { motion, useReducedMotion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Alert } from "@heroui/react/alert";
import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Chip } from "@heroui/react/chip";
import { EmptyState } from "@heroui/react/empty-state";
import { Label } from "@heroui/react/label";
import { ListBox } from "@heroui/react/list-box";
import { SearchField } from "@heroui/react/search-field";
import { Select } from "@heroui/react/select";
import { Spinner } from "@heroui/react/spinner";
import { Text } from "@heroui/react/text";

import { CardRowSkeleton } from "@/components/DashboardSkeletons";
import { ConfirmAlertDialog } from "@/components/ConfirmAlertDialog";
import { PageHeader } from "@/components/PageHeader";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { staggerContainer, staggerItem } from "@/lib/motion";
import { toast } from "@/lib/appToast";
import { summarizeGate } from "@/gate/summarizeGate";
import { deleteGate, listGates, startGate, stopGate, type GateDto } from "@/api";

type StatusFilter = "all" | "running" | "stopped";

export function GatesPage() {
  const { t } = useTranslation();
  const reduceMotion = useReducedMotion();
  const navigate = useNavigate();
  usePageTitle(t("pageTitles.gates"));
  const [gates, setGates] = useState<GateDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [actionGateId, setActionGateId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listGates();
      setGates(r.gates);
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return gates.filter((g) => {
      const nameMatch =
        !q || g.name.toLowerCase().includes(q) || String(g.id).includes(q);
      const runMatch =
        statusFilter === "all" ||
        (statusFilter === "running" && g.running) ||
        (statusFilter === "stopped" && !g.running);
      return nameMatch && runMatch;
    });
  }, [gates, query, statusFilter]);

  const onStart = async (id: number) => {
    setActionGateId(id);
    try {
      await startGate(id);
      await refresh();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setActionGateId(null);
    }
  };

  const onStop = async (id: number) => {
    setActionGateId(id);
    try {
      await stopGate(id);
      await refresh();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setActionGateId(null);
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

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
        <SearchField.Root className="min-w-0 flex-1 sm:max-w-md" variant="primary">
          <SearchField.Group>
            <SearchField.SearchIcon />
            <SearchField.Input
              placeholder={t("listFilter.searchPlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={t("listFilter.searchPlaceholder")}
            />
            {query ? <SearchField.ClearButton onPress={() => setQuery("")} /> : null}
          </SearchField.Group>
        </SearchField.Root>
        <div className="flex w-full min-w-[10rem] flex-col gap-1.5 sm:w-auto">
          <Label.Root className="text-xs font-medium text-slate-600 dark:text-slate-400" id="gates-status-filter">
            {t("listFilter.statusLabel")}
          </Label.Root>
          <Select.Root
            aria-labelledby="gates-status-filter"
            selectedKey={statusFilter}
            onSelectionChange={(key) => {
              if (key === "all" || key === "running" || key === "stopped") setStatusFilter(key);
            }}
          >
            <Select.Trigger className="w-full min-w-[10rem] justify-between">
              <Select.Value />
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox.Root>
                <ListBox.Item id="all" textValue={t("listFilter.statusAll")}>
                  {t("listFilter.statusAll")}
                </ListBox.Item>
                <ListBox.Item id="running" textValue={t("listFilter.statusRunning")}>
                  {t("listFilter.statusRunning")}
                </ListBox.Item>
                <ListBox.Item id="stopped" textValue={t("listFilter.statusStopped")}>
                  {t("listFilter.statusStopped")}
                </ListBox.Item>
              </ListBox.Root>
            </Select.Popover>
          </Select.Root>
        </div>
      </div>

      {loading && (
        <div className="mb-6" aria-live="polite">
          <CardRowSkeleton rows={3} />
        </div>
      )}

      {!loading && gates.length > 0 && filtered.length === 0 && (
        <Alert.Root status="warning" className="mb-6">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{t("listFilter.noResults")}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      )}

      <motion.div
        className="flex flex-col gap-4"
        variants={staggerContainer}
        initial={reduceMotion ? "show" : "hidden"}
        animate="show"
      >
        {filtered.map((g) => {
          const { listen, entrance } = summarizeGate(g, t);
          const busy = actionGateId === g.id;
          return (
            <motion.div key={g.id} variants={staggerItem}>
              <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
                <Card.Header className="flex flex-row flex-wrap items-start justify-between gap-4 px-6 pt-6">
                  <div className="min-w-0 flex flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Card.Title className="text-base text-slate-900 dark:text-slate-50">{g.name}</Card.Title>
                      <span className="font-mono text-xs text-slate-400">#{g.id}</span>
                      <Chip color={g.running ? "success" : "default"} variant="secondary" size="sm">
                        {g.running ? t("common.running") : t("common.stopped")}
                      </Chip>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
                      <span>
                        <span className="text-slate-400">{t("common.listen")} </span>
                        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-100">
                          {listen}
                        </code>
                      </span>
                      <span>
                        <span className="text-slate-400">{t("common.entrance")} </span>
                        <span className="font-medium text-slate-800 dark:text-slate-100">{entrance}</span>
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
                      <Button
                        size="sm"
                        variant="primary"
                        onPress={() => void onStart(g.id)}
                        isDisabled={busy}
                      >
                        {busy ? <Spinner.Root size="sm" color="current" /> : t("common.start")}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="secondary"
                        onPress={() => void onStop(g.id)}
                        isDisabled={busy}
                      >
                        {busy ? <Spinner.Root size="sm" color="current" /> : t("common.stop")}
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
                          toast.danger(formatApiError(e, t));
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
          <motion.div variants={staggerItem}>
            <EmptyState.Root className="rounded-xl border border-dashed border-slate-300 bg-slate-50/80 px-6 py-14 text-center dark:border-slate-600 dark:bg-slate-900/50">
              <Text className="text-sm font-medium text-slate-800 dark:text-slate-100">{t("gates.emptyTitle")}</Text>
              <Text className="mx-auto mt-2 block max-w-md text-sm text-slate-600 dark:text-slate-300">
                {t("gates.emptyBody")}
              </Text>
              <Button className="mt-6" variant="primary" onPress={() => navigate("/gates/new")}>
                {t("gates.emptyCta")}
              </Button>
            </EmptyState.Root>
          </motion.div>
        )}
      </motion.div>

      <motion.div
        initial={reduceMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: reduceMotion ? 0 : 0.12, duration: reduceMotion ? 0 : 0.25 }}
      >
        <Text className="mt-10 text-xs text-slate-500 dark:text-slate-400">{t("gates.tip")}</Text>
      </motion.div>
    </>
  );
}
