import { useCallback, useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";

import { Alert } from "@heroui/react/alert";
import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Chip } from "@heroui/react/chip";
import { TextArea } from "@heroui/react/textarea";

import { ConfirmAlertDialog } from "@/components/ConfirmAlertDialog";
import { PageHeader } from "@/components/PageHeader";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { toast } from "@/lib/appToast";
import { getHosts, putHosts } from "@/api";

export function HostsPage() {
  const { t } = useTranslation();
  usePageTitle(t("pageTitles.hosts"));
  const [path, setPath] = useState("");
  const [text, setText] = useState("");
  const [baseline, setBaseline] = useState("");
  const [readable, setReadable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const isDirty = useMemo(() => text !== baseline, [text, baseline]);

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      setLoading(true);
      try {
        const r = await getHosts();
        setPath(r.path);
        setText(r.content);
        setBaseline(r.content);
        setReadable(r.readable);
        if (!opts?.silent) {
          if (!r.readable && r.read_error) {
            toast.warning(t("hosts.cannotRead", { err: r.read_error }));
          } else if (r.readable && r.elevation_required_for_write) {
            toast.info(t("hosts.elevNote"));
          }
        }
      } catch (e) {
        toast.danger(formatApiError(e, t));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      await putHosts(text);
      toast.success(t("hosts.msgSaved"));
      await load({ silent: true });
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader title={t("hosts.title")} description={t("hosts.description")} />

      {!readable && (
        <Alert.Root status="warning" className="mb-6">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{t("hosts.readOnlyAlert")}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      )}

      {loading && (
        <Alert.Root status="default" className="mb-6">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{t("common.working")}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      )}

      {readable && isDirty && !loading && (
        <div className="mb-4">
          <Chip size="sm" variant="secondary" color="warning">
            {t("hosts.unsavedHint")}
          </Chip>
        </div>
      )}

      <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <Card.Header className="px-6 pt-6">
          <Card.Title className="text-lg text-slate-900 dark:text-slate-50">{t("hosts.filePath")}</Card.Title>
          <Card.Description className="break-all font-mono text-xs text-slate-600 dark:text-slate-300">
            {path || "—"}
          </Card.Description>
        </Card.Header>
        <Card.Content className="flex flex-col gap-4 px-6 pb-6">
          <TextArea.Root
            className="min-h-[28rem] w-full font-mono text-xs"
            value={text}
            onChange={(e) => setText(e.target.value)}
            readOnly={!readable}
            spellCheck={false}
            aria-label={t("hosts.ariaContents")}
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onPress={() => void load()} isDisabled={loading}>
              {t("common.reload")}
            </Button>
            {readable && isDirty ? (
              <ConfirmAlertDialog
                title={t("hosts.confirmSaveTitle")}
                body={t("hosts.confirmSaveBody")}
                cancelLabel={t("common.cancel")}
                confirmLabel={t("common.save")}
                iconStatus="warning"
                onConfirm={save}
                trigger={
                  <Button variant="primary" isDisabled={loading || saving}>
                    {saving ? t("common.working") : t("hosts.saveElevated")}
                  </Button>
                }
              />
            ) : (
              <Button
                variant="primary"
                onPress={() => void save()}
                isDisabled={loading || saving || !readable}
              >
                {saving ? t("common.working") : t("hosts.saveElevated")}
              </Button>
            )}
          </div>
        </Card.Content>
      </Card.Root>
    </>
  );
}
