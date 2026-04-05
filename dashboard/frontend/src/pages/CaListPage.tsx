import { useCallback, useEffect, useState } from "react";

import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { Text } from "@heroui/react/text";

import { PageHeader } from "@/components/PageHeader";
import { toast } from "@/lib/appToast";
import { createCa, listCas, type CaDto } from "@/api";

export function CaListPage() {
  const { t } = useTranslation();
  const [cas, setCas] = useState<CaDto[]>([]);
  const [loading, setLoading] = useState(false);

  const [name, setName] = useState("Dev CA");
  const [commonName, setCommonName] = useState("n0va-dev-ca");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listCas();
      setCas(r.cas);
    } catch (e) {
      toast.danger((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onCreate = async () => {
    try {
      await createCa({
        name: name.trim(),
        common_name: commonName.trim(),
        organization: "",
        state: "",
        locality: "",
        country: "",
      });
      toast.success(t("ca.msgCreated"));
      await refresh();
    } catch (e) {
      toast.danger((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader title={t("ca.title")} description={t("ca.description")} />

      <Card.Root className="mb-8 rounded-xl border border-slate-200 bg-white shadow-sm">
        <Card.Header className="px-6 pt-6">
          <Card.Title className="text-lg text-slate-900">{t("ca.createTitle")}</Card.Title>
          <Card.Description className="text-slate-600">{t("ca.createDesc")}</Card.Description>
        </Card.Header>
        <Card.Content className="flex flex-col gap-4 px-6 pb-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label.Root className="text-slate-700">{t("ca.displayName")}</Label.Root>
              <Input.Root value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label.Root className="text-slate-700">{t("ca.commonName")}</Label.Root>
              <Input.Root value={commonName} onChange={(e) => setCommonName(e.target.value)} />
            </div>
          </div>
          <Button variant="primary" onPress={onCreate}>
            {t("ca.createCa")}
          </Button>
        </Card.Content>
      </Card.Root>

      <Text className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">{t("ca.listHeading")}</Text>

      {loading && <p className="text-sm text-slate-500">{t("common.loading")}</p>}

      {!loading && cas.length === 0 && (
        <p className="text-sm text-slate-600">{t("ca.empty")}</p>
      )}

      {!loading && cas.length > 0 && (
        <ul className="space-y-2">
          {cas.map((c) => (
            <li key={c.id}>
              <Link
                to={`/ca/${c.id}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm transition hover:border-indigo-200 hover:shadow"
              >
                <span className="font-medium text-slate-900">{c.name}</span>
                <span className="text-xs text-slate-500">{c.common_name}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
