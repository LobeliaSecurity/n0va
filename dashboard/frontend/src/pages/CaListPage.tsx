import { useCallback, useEffect, useMemo, useState } from "react";

import { useTranslation } from "react-i18next";

import { Alert } from "@heroui/react/alert";
import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { EmptyState } from "@heroui/react/empty-state";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { SearchField } from "@heroui/react/search-field";
import { Text } from "@heroui/react/text";

import { AppLink } from "@/components/AppLink";
import { CardRowSkeleton } from "@/components/DashboardSkeletons";
import { PageHeader } from "@/components/PageHeader";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { toast } from "@/lib/appToast";
import { createCa, listCas, type CaDto } from "@/api";

export function CaListPage() {
  const { t } = useTranslation();
  usePageTitle(t("pageTitles.ca"));
  const [cas, setCas] = useState<CaDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");

  const [name, setName] = useState("Dev CA");
  const [commonName, setCommonName] = useState("n0va-dev-ca");
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listCas();
      setCas(r.cas);
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
    if (!q) return cas;
    return cas.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.common_name.toLowerCase().includes(q) ||
        String(c.id).includes(q),
    );
  }, [cas, query]);

  const onCreate = async () => {
    setCreating(true);
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
      toast.danger(formatApiError(e, t));
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <PageHeader title={t("ca.title")} description={t("ca.description")} />

      <Card.Root className="mb-8 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <Card.Header className="px-6 pt-6">
          <Card.Title className="text-lg text-slate-900 dark:text-slate-50">{t("ca.createTitle")}</Card.Title>
          <Card.Description className="text-slate-600 dark:text-slate-300">{t("ca.createDesc")}</Card.Description>
        </Card.Header>
        <Card.Content className="flex flex-col gap-4 px-6 pb-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label.Root className="text-slate-700 dark:text-slate-200">{t("ca.displayName")}</Label.Root>
              <Input.Root value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label.Root className="text-slate-700 dark:text-slate-200">{t("ca.commonName")}</Label.Root>
              <Input.Root value={commonName} onChange={(e) => setCommonName(e.target.value)} />
            </div>
          </div>
          <Button variant="primary" onPress={() => void onCreate()} isDisabled={creating}>
            {creating ? t("common.working") : t("ca.createCa")}
          </Button>
        </Card.Content>
      </Card.Root>

      <div className="mb-4 flex flex-col gap-2 sm:max-w-md">
        <SearchField.Root variant="primary">
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
      </div>

      <Text className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t("ca.listHeading")}
      </Text>

      {loading && (
        <div aria-live="polite">
          <CardRowSkeleton rows={2} />
        </div>
      )}

      {!loading && cas.length > 0 && filtered.length === 0 && (
        <Alert.Root status="warning" className="mb-4">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{t("listFilter.noResults")}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      )}

      {!loading && cas.length === 0 && (
        <EmptyState.Root className="rounded-xl border border-dashed border-slate-300 bg-slate-50/80 px-6 py-10 text-center dark:border-slate-600 dark:bg-slate-900/50">
          <Text className="text-sm text-slate-600 dark:text-slate-300">{t("ca.empty")}</Text>
        </EmptyState.Root>
      )}

      {!loading && filtered.length > 0 && (
        <ul className="space-y-2">
          {filtered.map((c) => (
            <li key={c.id}>
              <AppLink
                to={`/ca/${c.id}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm no-underline transition hover:border-indigo-200 hover:shadow-md dark:border-slate-700 dark:bg-slate-900 dark:hover:border-indigo-500/50"
              >
                <span className="font-medium text-slate-900 dark:text-slate-50">{c.name}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">{c.common_name}</span>
              </AppLink>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
