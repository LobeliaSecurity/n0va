import { useCallback, useEffect, useMemo, useState } from "react";

import { motion, useReducedMotion } from "framer-motion";
import { useTranslation } from "react-i18next";

import { Alert } from "@heroui/react/alert";
import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Checkbox } from "@heroui/react/checkbox";
import { Chip } from "@heroui/react/chip";
import { EmptyState } from "@heroui/react/empty-state";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { Link } from "@heroui/react/link";
import { ListBox } from "@heroui/react/list-box";
import { SearchField } from "@heroui/react/search-field";
import { Select } from "@heroui/react/select";
import { Spinner } from "@heroui/react/spinner";
import { Text } from "@heroui/react/text";

import { CardRowSkeleton } from "@/components/DashboardSkeletons";
import { ConfirmAlertDialog } from "@/components/ConfirmAlertDialog";
import { PageHeader } from "@/components/PageHeader";
import { useClipboardFeedback } from "@/hooks/useClipboardFeedback";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { staggerContainer, staggerItem } from "@/lib/motion";
import { toast } from "@/lib/appToast";
import {
  createContentServer,
  deleteContentServer,
  listContentServers,
  startContentServer,
  stopContentServer,
  updateContentServer,
  type ContentServerDto,
} from "@/api";

const DEFAULT_PORT = 8780;

type StatusFilter = "all" | "running" | "stopped";

export function ContentServersPage() {
  const { t } = useTranslation();
  const reduceMotion = useReducedMotion();
  usePageTitle(t("pageTitles.content"));
  const { copy } = useClipboardFeedback();
  const [servers, setServers] = useState<ContentServerDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [actionServerId, setActionServerId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState(String(DEFAULT_PORT));
  const [rootPath, setRootPath] = useState("");
  const [autoStart, setAutoStart] = useState(false);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listContentServers();
      setServers(r.content_servers);
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
    return servers.filter((s) => {
      const nameMatch =
        !q ||
        s.name.toLowerCase().includes(q) ||
        String(s.id).includes(q) ||
        s.root_path.toLowerCase().includes(q) ||
        `${s.host}:${s.port}`.includes(q);
      const runMatch =
        statusFilter === "all" ||
        (statusFilter === "running" && s.running) ||
        (statusFilter === "stopped" && !s.running);
      return nameMatch && runMatch;
    });
  }, [servers, query, statusFilter]);

  const openCreate = () => {
    setEditingId(null);
    setName(t("contentServers.defaultName"));
    setHost("127.0.0.1");
    setPort(String(DEFAULT_PORT));
    setRootPath("");
    setAutoStart(false);
    setFormOpen(true);
  };

  const openEdit = (s: ContentServerDto) => {
    setEditingId(s.id);
    setName(s.name);
    setHost(s.host);
    setPort(String(s.port));
    setRootPath(s.root_path);
    setAutoStart(s.auto_start);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingId(null);
  };

  const onSave = async () => {
    const n = name.trim();
    if (!n) {
      toast.danger(t("contentServers.errName"));
      return;
    }
    let p: number;
    try {
      p = Number.parseInt(port, 10);
      if (!Number.isFinite(p) || p < 1 || p > 65535) throw new Error();
    } catch {
      toast.danger(t("contentServers.errPort"));
      return;
    }
    const rp = rootPath.trim();
    if (!rp) {
      toast.danger(t("contentServers.errRoot"));
      return;
    }
    setSaving(true);
    try {
      if (editingId == null) {
        await createContentServer({
          name: n,
          host: host.trim() || "127.0.0.1",
          port: p,
          root_path: rp,
          auto_start: autoStart,
        });
        toast.success(t("contentServers.msgCreated"));
      } else {
        await updateContentServer(editingId, {
          name: n,
          host: host.trim() || "127.0.0.1",
          port: p,
          root_path: rp,
          auto_start: autoStart,
        });
        toast.success(t("contentServers.msgSaved"));
      }
      closeForm();
      await refresh();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setSaving(false);
    }
  };

  const onStart = async (id: number) => {
    setActionServerId(id);
    try {
      await startContentServer(id);
      await refresh();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setActionServerId(null);
    }
  };

  const onStop = async (id: number) => {
    setActionServerId(id);
    try {
      await stopContentServer(id);
      await refresh();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setActionServerId(null);
    }
  };

  return (
    <>
      <PageHeader
        title={t("contentServers.title")}
        description={t("contentServers.description")}
        actions={
          <Button variant="primary" onPress={openCreate}>
            {t("contentServers.addServer")}
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
          <Label.Root className="text-xs font-medium text-slate-600 dark:text-slate-400" id="cs-status-filter">
            {t("listFilter.statusLabel")}
          </Label.Root>
          <Select.Root
            aria-labelledby="cs-status-filter"
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

      {formOpen && (
        <Card.Root className="mb-8 rounded-xl border border-indigo-200/80 bg-white shadow-sm ring-1 ring-indigo-100/60 dark:border-indigo-900/50 dark:bg-slate-900 dark:ring-indigo-900/40">
          <Card.Header className="flex flex-row flex-wrap items-start justify-between gap-3 px-6 pt-6">
            <div>
              <Card.Title className="text-base text-slate-900 dark:text-slate-50">
                {editingId == null ? t("contentServers.formCreateTitle") : t("contentServers.formEditTitle")}
              </Card.Title>
              <Card.Description className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {t("contentServers.formHint")}
              </Card.Description>
            </div>
            <Button size="sm" variant="secondary" onPress={closeForm}>
              {t("common.cancel")}
            </Button>
          </Card.Header>
          <Card.Content className="space-y-4 px-6 pb-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="cs-name">
                  {t("common.name")}
                </Label.Root>
                <Input
                  id="cs-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("contentServers.namePlaceholder")}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="cs-host">
                  {t("common.host")}
                </Label.Root>
                <Input
                  id="cs-host"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  placeholder="127.0.0.1"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="cs-port">
                  {t("common.port")}
                </Label.Root>
                <Input
                  id="cs-port"
                  inputMode="numeric"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="cs-root">
                  {t("contentServers.documentRoot")}
                </Label.Root>
                <Input
                  id="cs-root"
                  value={rootPath}
                  onChange={(e) => setRootPath(e.target.value)}
                  placeholder={t("contentServers.rootPlaceholder")}
                />
                <Text className="text-xs text-slate-500 dark:text-slate-400">{t("contentServers.rootHelp")}</Text>
              </div>
            </div>
            <Checkbox.Root
              className="flex max-w-full items-start gap-2 text-sm text-slate-800 dark:text-slate-200"
              isSelected={autoStart}
              onChange={(v) => setAutoStart(Boolean(v))}
            >
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              <Checkbox.Content>{t("contentServers.autoStart")}</Checkbox.Content>
            </Checkbox.Root>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button variant="primary" onPress={() => void onSave()} isDisabled={saving}>
                {saving ? (
                  <span className="inline-flex items-center gap-2">
                    <Spinner.Root size="sm" color="current" />
                    {t("common.working")}
                  </span>
                ) : (
                  t("common.save")
                )}
              </Button>
            </div>
          </Card.Content>
        </Card.Root>
      )}

      {loading && (
        <div className="mb-6" aria-live="polite">
          <CardRowSkeleton rows={3} />
        </div>
      )}

      {!loading && servers.length > 0 && filtered.length === 0 && (
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
        {filtered.map((s) => {
          const busy = actionServerId === s.id;
          return (
          <motion.div key={s.id} variants={staggerItem}>
            <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <Card.Header className="flex flex-row flex-wrap items-start justify-between gap-4 px-6 pt-6">
                <div className="min-w-0 flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Card.Title className="text-base text-slate-900 dark:text-slate-50">{s.name}</Card.Title>
                    <span className="font-mono text-xs text-slate-400 dark:text-slate-500">#{s.id}</span>
                    <Chip color={s.running ? "success" : "default"} variant="secondary" size="sm">
                      {s.running ? t("common.running") : t("common.stopped")}
                    </Chip>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
                    <span>
                      <span className="text-slate-400 dark:text-slate-500">{t("common.listen")} </span>
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                        {s.host}:{s.port}
                      </code>
                    </span>
                  </div>
                  <p className="break-all font-mono text-xs text-slate-500 dark:text-slate-400">
                    <span className="text-slate-400 dark:text-slate-500">{t("contentServers.documentRoot")}: </span>
                    {s.root_path}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="rounded bg-slate-100 px-2 py-1 font-mono text-xs text-indigo-900 dark:bg-indigo-950/60 dark:text-indigo-200">
                      {s.base_url}
                    </code>
                    <Button size="sm" variant="secondary" onPress={() => void copy(s.base_url)}>
                      {t("common.copy")}
                    </Button>
                    <Link.Root
                      href={s.base_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-indigo-700 underline decoration-indigo-200 underline-offset-2 hover:text-indigo-950 dark:text-indigo-300"
                    >
                      {t("common.open")}
                    </Link.Root>
                  </div>
                  {s.auto_start && (
                    <Text className="text-xs text-slate-500 dark:text-slate-400">{t("contentServers.autoStartBadge")}</Text>
                  )}
                  {s.updated_at && (
                    <Card.Description className="font-mono text-xs text-slate-400 dark:text-slate-400">
                      {t("common.updated", { when: s.updated_at })}
                    </Card.Description>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {!s.running ? (
                    <Button
                      size="sm"
                      variant="primary"
                      onPress={() => void onStart(s.id)}
                      isDisabled={busy}
                    >
                      {busy ? <Spinner.Root size="sm" color="current" /> : t("common.start")}
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      onPress={() => void onStop(s.id)}
                      isDisabled={busy}
                    >
                      {busy ? <Spinner.Root size="sm" color="current" /> : t("common.stop")}
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    onPress={() => openEdit(s)}
                    isDisabled={s.running}
                  >
                    {t("common.configure")}
                  </Button>
                  <ConfirmAlertDialog
                    title={t("common.confirmDeleteTitle")}
                    body={t("contentServers.confirmDelete", { id: s.id })}
                    cancelLabel={t("common.cancel")}
                    confirmLabel={t("common.deleteConfirm")}
                    onConfirm={async () => {
                      try {
                        await deleteContentServer(s.id);
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

        {servers.length === 0 && !loading && (
          <motion.div variants={staggerItem}>
            <EmptyState.Root className="rounded-xl border border-dashed border-slate-300 bg-slate-50/80 px-6 py-14 text-center dark:border-slate-600 dark:bg-slate-900/50">
              <Text className="text-sm font-medium text-slate-800 dark:text-slate-100">
                {t("contentServers.emptyTitle")}
              </Text>
              <Text className="mx-auto mt-2 block max-w-lg text-sm text-slate-600 dark:text-slate-300">
                {t("contentServers.emptyBody")}
              </Text>
              <Button className="mt-6" variant="primary" onPress={openCreate}>
                {t("contentServers.emptyCta")}
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
        <Text className="mt-10 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{t("contentServers.tip")}</Text>
      </motion.div>
    </>
  );
}
