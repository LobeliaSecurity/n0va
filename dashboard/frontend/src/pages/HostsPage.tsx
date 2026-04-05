import { useCallback, useEffect, useState } from "react";

import { useTranslation } from "react-i18next";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { TextArea } from "@heroui/react/textarea";

import { PageHeader } from "@/components/PageHeader";
import { toast } from "@/lib/appToast";
import { getHosts, putHosts } from "@/api";

export function HostsPage() {
  const { t } = useTranslation();
  const [path, setPath] = useState("");
  const [text, setText] = useState("");
  const [readable, setReadable] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    setLoading(true);
    try {
      const r = await getHosts();
      setPath(r.path);
      setText(r.content);
      setReadable(r.readable);
      if (!opts?.silent) {
        if (!r.readable && r.read_error) {
          toast.warning(t("hosts.cannotRead", { err: r.read_error }));
        } else if (r.readable && r.elevation_required_for_write) {
          toast.info(t("hosts.elevNote"));
        }
      }
    } catch (e) {
      toast.danger((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setLoading(true);
    try {
      await putHosts(text);
      toast.success(t("hosts.msgSaved"));
      await load({ silent: true });
    } catch (e) {
      toast.danger((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader title={t("hosts.title")} description={t("hosts.description")} />

      {loading && (
        <p className="mb-6 text-sm text-slate-500" aria-live="polite">
          {t("common.working")}
        </p>
      )}

      <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <Card.Header className="px-6 pt-6">
          <Card.Title className="text-lg text-slate-900">{t("hosts.filePath")}</Card.Title>
          <Card.Description className="break-all font-mono text-xs text-slate-600">{path || "—"}</Card.Description>
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
            <Button variant="primary" onPress={save} isDisabled={loading || !readable}>
              {t("hosts.saveElevated")}
            </Button>
          </div>
        </Card.Content>
      </Card.Root>
    </>
  );
}
