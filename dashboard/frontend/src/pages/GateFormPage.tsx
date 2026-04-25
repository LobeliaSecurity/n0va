import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import { useBlocker, useHref, useNavigate, useParams } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";

import { Alert } from "@heroui/react/alert";
import { Breadcrumbs } from "@heroui/react/breadcrumbs";
import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Checkbox } from "@heroui/react/checkbox";
import { Disclosure } from "@heroui/react/disclosure";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { ListBox } from "@heroui/react/list-box";
import { Select } from "@heroui/react/select";
import { Spinner } from "@heroui/react/spinner";
import { Text } from "@heroui/react/text";

import { AppLink } from "@/components/AppLink";
import { ConfirmAlertDialog } from "@/components/ConfirmAlertDialog";
import { CardRowSkeleton } from "@/components/DashboardSkeletons";
import { GateFormFlowOverview } from "@/components/GateFormFlowOverview";
import { PageHeader } from "@/components/PageHeader";
import { UnsavedLeaveModal } from "@/components/UnsavedLeaveModal";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { toast } from "@/lib/appToast";
import {
  createGate,
  deleteGate,
  getGate,
  listAllIssuedCertificates,
  startGate,
  stopGate,
  updateGate,
  type GateDto,
  type IssuedCertRef,
} from "@/api";
import {
  clampHttpDispatchIndices,
  defaultGateFormModel,
  formToGateConfig,
  gateConfigToForm,
  validateForm,
  type GateFormModel,
  type HttpDispatchRuleForm,
  type HttpPathMatchMode,
  type RouteForm,
  type SniRow,
  type UpstreamForm,
} from "@/gate/gateConfig";

/** Trans の components を毎レンダーで新配列にしない（子の不要な再マウントを避ける） */
const RUNNING_BANNER_COMPONENTS = [<strong key="0" />];

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">{children}</h2>;
}

function StepSectionTitle({ step, children }: { step: number; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <span
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200"
        aria-hidden
      >
        {step}
      </span>
      <h2 className="min-w-0 flex-1 text-base font-semibold leading-snug text-slate-900 dark:text-slate-50">{children}</h2>
    </div>
  );
}

function normalizePath(p: string): string {
  return p.trim().replace(/\\/g, "/");
}

/** HashRouter では `href="#id"` が `#/route` を壊すため、スクロールのみ行う */
function scrollToGateTocSection(elementId: string) {
  document.getElementById(elementId)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function findIssuedMatch(
  row: { cert_file: string; key_file: string },
  issued: IssuedCertRef[],
): IssuedCertRef | null {
  const cf = normalizePath(row.cert_file);
  const kf = normalizePath(row.key_file);
  if (!cf || !kf) return null;
  return (
    issued.find(
      (c) => normalizePath(c.cert_path) === cf && normalizePath(c.key_path) === kf,
    ) ?? null
  );
}

/** ルートキー用 select: 入口 SNI 一覧に、現在値があれば含める */
function routeKeySelectOptions(routeKey: string, sniHosts: string[]): string[] {
  const rk = routeKey.trim();
  const base = [...sniHosts];
  if (rk && !base.includes(rk)) base.push(rk);
  return base.sort();
}

export function GateFormPage() {
  const { t } = useTranslation();
  const { gateId } = useParams<{ gateId: string }>();
  const navigate = useNavigate();
  const isNew = gateId === "new";
  const id = isNew ? NaN : Number(gateId);
  const invalidId = !isNew && Number.isNaN(id);

  const [loading, setLoading] = useState(!isNew);
  const [gate, setGate] = useState<GateDto | null>(null);

  const [name, setName] = useState("new-gate");
  const [model, setModel] = useState<GateFormModel>(() => defaultGateFormModel());
  const [showAdvancedListen, setShowAdvancedListen] = useState(false);
  const [showJsonPreview, setShowJsonPreview] = useState(false);
  const [issuedCerts, setIssuedCerts] = useState<IssuedCertRef[]>([]);
  const [issuedCertsLoading, setIssuedCertsLoading] = useState(true);
  const [baseline, setBaseline] = useState("");
  const [saving, setSaving] = useState(false);
  const [gateActionPending, setGateActionPending] = useState(false);
  const bypassUnsavedBlockRef = useRef(false);

  const defaultNewBaseline = useMemo(
    () => JSON.stringify({ name: "new-gate", model: defaultGateFormModel() }),
    [],
  );

  useEffect(() => {
    if (isNew && !invalidId) {
      setBaseline(defaultNewBaseline);
    }
  }, [isNew, invalidId, defaultNewBaseline]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await listAllIssuedCertificates();
        if (!cancelled) setIssuedCerts(r.certificates);
      } catch {
        if (!cancelled) setIssuedCerts([]);
      } finally {
        if (!cancelled) setIssuedCertsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async () => {
    if (isNew || invalidId) return;
    setLoading(true);
    try {
      const g = await getGate(id);
      const m = gateConfigToForm(g.config);
      setGate(g);
      setName(g.name);
      setModel(m);
      setBaseline(JSON.stringify({ name: g.name.trim(), model: m }));
    } catch (e) {
      toast.danger(formatApiError(e, t));
      setGate(null);
    } finally {
      setLoading(false);
    }
  }, [id, invalidId, isNew, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const running = gate?.running ?? false;

  const previewJson = useMemo(() => {
    try {
      return JSON.stringify(formToGateConfig(model), null, 2);
    } catch {
      return "";
    }
  }, [model]);

  const validationError = useMemo(() => validateForm(model), [model]);

  const formSnapshot = useMemo(
    () => JSON.stringify({ name: name.trim(), model }),
    [name, model],
  );
  const isDirty = !loading && baseline !== "" && formSnapshot !== baseline;
  const blocker = useBlocker(() => isDirty && !bypassUnsavedBlockRef.current);

  useEffect(() => {
    // 作成完了後の画面遷移で一時的に解除したブロッカーを通常状態へ戻す
    bypassUnsavedBlockRef.current = false;
  }, [gateId]);

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty]);

  usePageTitle(
    invalidId
      ? t("gateForm.invalidIdTitle")
      : isNew
        ? t("pageTitles.gateNew")
        : gate
          ? `${gate.name} — ${t("pageTitles.gateEdit")}`
          : t("pageTitles.gateEdit"),
  );

  const hrefGates = useHref("/gates");
  const hrefSelf = useHref(isNew ? "/gates/new" : `/gates/${gateId}`);

  /** SNI 行の「発行済み証明書」一致表示だけ遅延させ、select の value 更新でフォーカスが奪われるのを防ぐ */
  const deferredSniRows = useDeferredValue(model.sniRows);

  const setListen = (patch: Partial<GateFormModel["listen"]>) => {
    setModel((m) => ({ ...m, listen: { ...m.listen, ...patch } }));
  };

  const updateSniRow = (index: number, patch: Partial<SniRow>) => {
    setModel((m) => {
      const oldHost = m.sniRows[index]?.hostname?.trim() ?? "";
      const sniRows = m.sniRows.map((row, i) => (i === index ? { ...row, ...patch } : row));
      let routes = m.routes;
      if (patch.hostname !== undefined) {
        const newHost = patch.hostname.trim();
        if (oldHost && oldHost !== newHost) {
          routes = m.routes.map((r) =>
            r.routeKey.trim() === oldHost ? { ...r, routeKey: newHost } : r,
          );
        } else if (!oldHost && newHost) {
          // 空にしたあと oldHost が "" のまま再入力すると、上の分岐に入らず routeKey が "" のまま残る
          const emptyRoutes = m.routes.filter((r) => !r.routeKey.trim());
          if (emptyRoutes.length === 1) {
            routes = m.routes.map((r) => (!r.routeKey.trim() ? { ...r, routeKey: newHost } : r));
          } else if (
            emptyRoutes.length > 1 &&
            index < m.routes.length &&
            !m.routes[index].routeKey.trim()
          ) {
            // 複数 SNI を順に空にしたとき空ルートが複数になる。行ごとに route[index] を埋める
            routes = m.routes.map((r, i) => (i === index ? { ...r, routeKey: newHost } : r));
          }
        }
      }
      return { ...m, sniRows, routes };
    });
  };

  const addSniRow = () => {
    setModel((m) => ({
      ...m,
      sniRows: [...m.sniRows, { hostname: "", cert_file: "", key_file: "" }],
    }));
  };

  const removeSniRow = (index: number) => {
    setModel((m) => {
      if (m.sniRows.length <= 1) return m;
      const removed = m.sniRows[index]?.hostname?.trim() ?? "";
      const sniRows = m.sniRows.filter((_, i) => i !== index);
      let routes = m.routes.filter((r) => r.routeKey !== removed);
      if (routes.length === 0) {
        const fallback = sniRows[0]?.hostname.trim() || "localhost";
        routes = [
          {
            routeKey: fallback,
            strategy: "least_conn",
            upstreams: [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }],
            httpDispatch: null,
          },
        ];
      }
      return { ...m, sniRows, routes };
    });
  };

  const updateRoute = (index: number, patch: Partial<RouteForm>) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((r, i) => (i === index ? { ...r, ...patch } : r)),
    }));
  };

  const updateUpstream = (routeIndex: number, upstreamIndex: number, patch: Partial<UpstreamForm>) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) => {
        if (ri !== routeIndex) return route;
        const upstreams = route.upstreams.map((u, ui) =>
          ui === upstreamIndex ? { ...u, ...patch } : u,
        );
        return { ...route, upstreams };
      }),
    }));
  };

  const sniHostOptions = useMemo(
    () => [...new Set(model.sniRows.map((r) => r.hostname.trim()).filter(Boolean))].sort(),
    [model.sniRows],
  );

  const usedRouteKeys = useMemo(() => new Set(model.routes.map((r) => r.routeKey.trim())), [model.routes]);

  const canAddRoute = useMemo(
    () => sniHostOptions.some((h) => !usedRouteKeys.has(h)),
    [sniHostOptions, usedRouteKeys],
  );

  const addRoute = () => {
    setModel((m) => {
      const hosts = [...new Set(m.sniRows.map((r) => r.hostname.trim()).filter(Boolean))];
      const used = new Set(m.routes.map((r) => r.routeKey.trim()));
      const next = hosts.find((h) => !used.has(h));
      if (!next) return m;
      return {
        ...m,
        routes: [
          ...m.routes,
          {
            routeKey: next,
            strategy: "least_conn",
            upstreams: [{ host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" }],
            httpDispatch: null,
          },
        ],
      };
    });
  };

  const removeRoute = (index: number) => {
    setModel((m) => {
      if (m.routes.length <= 1) return m;
      return { ...m, routes: m.routes.filter((_, i) => i !== index) };
    });
  };

  const addUpstream = (routeIndex: number) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) =>
        ri === routeIndex
          ? clampHttpDispatchIndices({
              ...route,
              upstreams: [
                ...route.upstreams,
                { host: "127.0.0.1", port: "8080", tlsServerHostname: "", tlsAlpn: "" },
              ],
            })
          : route,
      ),
    }));
  };

  const removeUpstream = (routeIndex: number, upstreamIndex: number) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) => {
        if (ri !== routeIndex) return route;
        if (route.upstreams.length <= 1) return route;
        return clampHttpDispatchIndices({
          ...route,
          upstreams: route.upstreams.filter((_, ui) => ui !== upstreamIndex),
        });
      }),
    }));
  };

  const setHttpDispatchEnabled = (routeIndex: number, enabled: boolean) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) => {
        if (ri !== routeIndex) return route;
        if (!enabled) return { ...route, httpDispatch: null };
        return clampHttpDispatchIndices({
          ...route,
          httpDispatch: {
            enabled: true,
            defaultUpstreamIndex: 0,
            rules: [],
          },
        });
      }),
    }));
  };

  const patchHttpDispatch = (routeIndex: number, patch: Partial<NonNullable<RouteForm["httpDispatch"]>>) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) => {
        if (ri !== routeIndex) return route;
        const cur = route.httpDispatch ?? {
          enabled: true,
          defaultUpstreamIndex: 0,
          rules: [],
        };
        return clampHttpDispatchIndices({
          ...route,
          httpDispatch: { ...cur, ...patch },
        });
      }),
    }));
  };

  const updateHttpRule = (
    routeIndex: number,
    ruleIndex: number,
    patch: Partial<HttpDispatchRuleForm>,
  ) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) => {
        if (ri !== routeIndex || !route.httpDispatch?.enabled) return route;
        const rules = route.httpDispatch.rules.map((r, j) => (j === ruleIndex ? { ...r, ...patch } : r));
        return clampHttpDispatchIndices({ ...route, httpDispatch: { ...route.httpDispatch, rules } });
      }),
    }));
  };

  const addHttpRule = (routeIndex: number) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) => {
        if (ri !== routeIndex) return route;
        const hd = route.httpDispatch;
        if (!hd?.enabled) return route;
        const rules: HttpDispatchRuleForm[] = [
          ...hd.rules,
          { upstreamIndex: 0, pathMode: "prefix", path: "/api", methods: "" },
        ];
        return clampHttpDispatchIndices({ ...route, httpDispatch: { ...hd, rules } });
      }),
    }));
  };

  const removeHttpRule = (routeIndex: number, ruleIndex: number) => {
    setModel((m) => ({
      ...m,
      routes: m.routes.map((route, ri) => {
        if (ri !== routeIndex || !route.httpDispatch?.enabled) return route;
        const rules = route.httpDispatch.rules.filter((_, j) => j !== ruleIndex);
        return { ...route, httpDispatch: { ...route.httpDispatch, rules } };
      }),
    }));
  };

  const onSave = async () => {
    const v = validateForm(model);
    if (v) {
      toast.warning(v);
      return;
    }
    let cfg: Record<string, unknown>;
    try {
      cfg = formToGateConfig(model);
    } catch (e) {
      toast.danger(e instanceof Error ? e.message : String(e));
      return;
    }
    setSaving(true);
    try {
      if (isNew) {
        const created = await createGate({ name: name.trim() || "gate", config: cfg });
        toast.success(t("gateForm.msgCreated"));
        bypassUnsavedBlockRef.current = true;
        navigate(`/gates/${created.id}`, { replace: true });
      } else {
        await updateGate(id, { name: name.trim() || "gate", config: cfg });
        toast.success(t("gateForm.msgSaved"));
        await load();
      }
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setSaving(false);
    }
  };

  const performDeleteGate = async () => {
    if (isNew) return;
    try {
      await deleteGate(id);
      navigate("/gates");
    } catch (e) {
      toast.danger(formatApiError(e, t));
      throw e;
    }
  };

  const onStart = async () => {
    if (isNew) return;
    setGateActionPending(true);
    try {
      await startGate(id);
      await load();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setGateActionPending(false);
    }
  };

  const onStop = async () => {
    if (isNew) return;
    setGateActionPending(true);
    try {
      await stopGate(id);
      await load();
    } catch (e) {
      toast.danger(formatApiError(e, t));
    } finally {
      setGateActionPending(false);
    }
  };

  if (invalidId) {
    return (
      <>
        <PageHeader title={t("gateForm.invalidIdTitle")} description={t("gateForm.invalidIdDesc")} />
        <AppLink to="/gates" className="text-sm font-medium text-indigo-700 underline decoration-indigo-200 underline-offset-2">
          {t("gateForm.backToGates")}
        </AppLink>
      </>
    );
  }

  const formDisabled = running;

  return (
    <>
      <UnsavedLeaveModal
        blocker={blocker}
        title={t("gateForm.leaveUnsavedTitle")}
        body={t("gateForm.leaveUnsavedBody")}
        stayLabel={t("gateForm.stayEditing")}
        leaveLabel={t("gateForm.leavePage")}
      />
      <PageHeader
        breadcrumbs={
          <Breadcrumbs.Root className="text-sm" separator="/">
            <Breadcrumbs.Item href={hrefGates}>{t("gateForm.breadcrumbGates")}</Breadcrumbs.Item>
            <Breadcrumbs.Item href={hrefSelf}>
              {isNew ? t("gateForm.breadcrumbNew") : name || `#${id}`}
            </Breadcrumbs.Item>
          </Breadcrumbs.Root>
        }
        title={isNew ? t("gateForm.newTitle") : t("gateForm.editTitle", { id })}
        description={t("gateForm.headerDesc")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onPress={() => navigate("/gates")}>
              {t("gateForm.backToList")}
            </Button>
            {!isNew && gate && (
              <>
                {!running ? (
                  <Button
                    variant="primary"
                    onPress={() => void onStart()}
                    isDisabled={gateActionPending}
                  >
                    {gateActionPending ? <Spinner.Root size="sm" color="current" /> : t("common.start")}
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    onPress={() => void onStop()}
                    isDisabled={gateActionPending}
                  >
                    {gateActionPending ? <Spinner.Root size="sm" color="current" /> : t("common.stop")}
                  </Button>
                )}
              </>
            )}
          </div>
        }
      />

      {!isNew && running && (
        <Alert.Root status="warning" className="mb-6">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title className="sr-only">{t("gateForm.runningBanner")}</Alert.Title>
            <Alert.Description>
              <Trans i18nKey="gateForm.runningBanner" components={RUNNING_BANNER_COMPONENTS} />
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
      )}

      {loading && (
        <div className="mb-6" aria-live="polite">
          <CardRowSkeleton rows={2} />
        </div>
      )}

      {!loading && (
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8">
          <aside className="hidden shrink-0 lg:sticky lg:top-24 lg:block lg:w-52">
            <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <Card.Header className="px-4 pt-4 pb-2">
                <Card.Title className="text-sm text-slate-900 dark:text-slate-50">{t("gateForm.tocHeading")}</Card.Title>
              </Card.Header>
              <Card.Content className="flex flex-col gap-1 px-4 pb-4">
                <button
                  type="button"
                  className="cursor-pointer text-left text-sm text-indigo-700 hover:underline dark:text-indigo-300"
                  onClick={() => scrollToGateTocSection("gate-step-identity")}
                >
                  {t("gateForm.tocIdentity")}
                </button>
                <button
                  type="button"
                  className="cursor-pointer text-left text-sm text-indigo-700 hover:underline dark:text-indigo-300"
                  onClick={() => scrollToGateTocSection("gate-step-listen")}
                >
                  {t("gateForm.sections.listen")}
                </button>
                <button
                  type="button"
                  className="cursor-pointer text-left text-sm text-indigo-700 hover:underline dark:text-indigo-300"
                  onClick={() => scrollToGateTocSection("gate-step-entrance")}
                >
                  {t("gateForm.sections.entrance")}
                </button>
                <button
                  type="button"
                  className="cursor-pointer text-left text-sm text-indigo-700 hover:underline dark:text-indigo-300"
                  onClick={() => scrollToGateTocSection("gate-step-routes")}
                >
                  {t("gateForm.sections.routes")}
                </button>
              </Card.Content>
            </Card.Root>
          </aside>
          <div className="flex min-w-0 flex-1 flex-col gap-6">
          <Card.Root id="gate-step-identity" className="scroll-mt-24 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <Card.Header className="px-6 pt-6">
              <SectionTitle>{t("gateForm.sections.identity")}</SectionTitle>
              <Card.Description className="text-slate-600 dark:text-slate-300">{t("gateForm.sections.identityDesc")}</Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4 px-6 pb-6">
              <div className="flex max-w-md flex-col gap-2">
                <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="gate-form-name">
                  {t("common.name")}
                </Label.Root>
                <Input.Root
                  id="gate-form-name"
                  className="max-w-md"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={formDisabled}
                  autoComplete="off"
                />
              </div>
            </Card.Content>
          </Card.Root>

          <GateFormFlowOverview model={model} />

          <Card.Root
            id="gate-step-listen"
            className="scroll-mt-24 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <Card.Header className="px-6 pt-6">
              <StepSectionTitle step={1}>{t("gateForm.sections.listen")}</StepSectionTitle>
              <Card.Description className="mt-3 pl-11 text-slate-600 dark:text-slate-300">{t("gateForm.sections.listenDesc")}</Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4 px-6 pb-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="gate-form-listen-host">
                    {t("gateForm.sections.bindAddress")}
                  </Label.Root>
                  <Input.Root
                    id="gate-form-listen-host"
                    value={model.listen.host}
                    onChange={(e) => setListen({ host: e.target.value })}
                    disabled={formDisabled}
                    placeholder="127.0.0.1"
                    autoComplete="off"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="gate-form-listen-port">
                    {t("common.port")}
                  </Label.Root>
                  <Input.Root
                    id="gate-form-listen-port"
                    value={model.listen.port}
                    onChange={(e) => setListen({ port: e.target.value })}
                    disabled={formDisabled}
                    inputMode="numeric"
                    autoComplete="off"
                  />
                </div>
              </div>
              <Disclosure.Root
                isExpanded={showAdvancedListen}
                onExpandedChange={setShowAdvancedListen}
                className="rounded-lg border border-slate-100 bg-slate-50/80 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/50"
              >
                <Disclosure.Trigger className="flex w-full items-center justify-between gap-2 text-left text-sm font-medium text-slate-800 dark:text-slate-100">
                  {t("gateForm.sections.advancedListen")}
                  <Disclosure.Indicator className="text-slate-500 dark:text-slate-400" />
                </Disclosure.Trigger>
                <Disclosure.Content>
                  <Disclosure.Body className="mt-4 grid gap-4 sm:grid-cols-2">
                    <div className="flex flex-col gap-2">
                      <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="gate-form-listen-backlog">
                        {t("gateForm.sections.backlog")}
                      </Label.Root>
                      <Input.Root
                        id="gate-form-listen-backlog"
                        value={model.listen.backlog}
                        onChange={(e) => setListen({ backlog: e.target.value })}
                        disabled={formDisabled}
                        autoComplete="off"
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor="gate-form-listen-read-limit">
                        {t("gateForm.sections.readLimit")}
                      </Label.Root>
                      <Input.Root
                        id="gate-form-listen-read-limit"
                        value={model.listen.read_limit}
                        onChange={(e) => setListen({ read_limit: e.target.value })}
                        disabled={formDisabled}
                        inputMode="numeric"
                        autoComplete="off"
                      />
                    </div>
                  </Disclosure.Body>
                </Disclosure.Content>
              </Disclosure.Root>
            </Card.Content>
          </Card.Root>

          <Card.Root
            id="gate-step-entrance"
            className="scroll-mt-24 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <Card.Header className="px-6 pt-6">
              <StepSectionTitle step={2}>{t("gateForm.sections.entrance")}</StepSectionTitle>
              <Card.Description className="mt-3 pl-11 text-slate-600 dark:text-slate-300">
                <p>
                  {t("gateForm.sections.entranceDescTlsOnlyBefore")}{" "}
                  <AppLink to="/ca" className="font-medium text-indigo-700 underline decoration-indigo-200 underline-offset-2 dark:text-indigo-300">
                    {t("nav.ca")}
                  </AppLink>
                  {t("gateForm.sections.entranceDescTlsOnlyAfter")}
                </p>
              </Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-6 px-6 pb-6">
              <div className="flex flex-col gap-4">
                <p className="rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-xs leading-relaxed text-indigo-950 dark:border-indigo-900/50 dark:bg-indigo-950/40 dark:text-indigo-100">
                  {t("gateForm.flow.sniBlockExplain")}
                </p>
                <div className="flex items-center justify-between gap-2">
                  <Text className="text-sm font-medium text-slate-800 dark:text-slate-200">{t("gateForm.sections.tlsHostnames")}</Text>
                  <Button size="sm" variant="secondary" onPress={addSniRow} isDisabled={formDisabled}>
                    {t("gateForm.sections.addHostname")}
                  </Button>
                </div>
                {issuedCertsLoading && (
                  <p className="text-xs text-slate-500 dark:text-slate-400" aria-live="polite">
                    {t("gateForm.sections.loadingIssued")}
                  </p>
                )}
                {!issuedCertsLoading && issuedCerts.length === 0 && (
                  <p className="text-xs text-slate-600 dark:text-slate-300">
                    {t("gateForm.sections.noCertsHintBefore")}{" "}
                    <AppLink to="/ca" className="font-medium text-indigo-700 underline decoration-indigo-200 underline-offset-2 dark:text-indigo-300">
                      {t("nav.ca")}
                    </AppLink>{" "}
                    {t("gateForm.sections.noCertsHintAfter")}
                  </p>
                )}
                <div className="flex flex-col gap-4">
                  {model.sniRows.map((row, i) => {
                    const rowForMatch = deferredSniRows[i] ?? row;
                    const matched = findIssuedMatch(rowForMatch, issuedCerts);
                    const selectValue = matched ? String(matched.id) : "";
                    return (
                      <div
                        key={`sni-${i}`}
                        className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-600 dark:bg-slate-800/50"
                      >
                        <div className="mb-3 flex flex-col gap-3">
                          <div className="flex flex-col gap-1.5">
                            <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                              {t("gateForm.sections.useFromDashboard")}
                            </span>
                            <Select.Root
                              fullWidth
                              aria-label={t("gateForm.sections.selectIssuedAria", { n: i + 1 })}
                              selectedKey={selectValue || undefined}
                              onSelectionChange={(key) => {
                                if (!key) return;
                                const cid = Number(key);
                                const c = issuedCerts.find((x) => x.id === cid);
                                if (!c) return;
                                updateSniRow(i, {
                                  cert_file: c.cert_path,
                                  key_file: c.key_path,
                                  hostname: row.hostname.trim() || c.common_name,
                                });
                              }}
                              isDisabled={formDisabled || issuedCerts.length === 0}
                              placeholder={
                                issuedCerts.length === 0
                                  ? t("gateForm.sections.optionNoCerts")
                                  : t("gateForm.sections.optionChoose")
                              }
                            >
                              <Select.Trigger className="w-full min-w-0 justify-between">
                                <Select.Value />
                                <Select.Indicator />
                              </Select.Trigger>
                              <Select.Popover className="min-w-[var(--trigger-width)]">
                                <ListBox.Root>
                                  {issuedCerts.map((c) => (
                                    <ListBox.Item
                                      key={c.id}
                                      id={String(c.id)}
                                      textValue={`${c.ca_name} · ${c.common_name} (#${c.id})`}
                                    >
                                      {c.ca_name} · {c.common_name} (#{c.id})
                                    </ListBox.Item>
                                  ))}
                                </ListBox.Root>
                              </Select.Popover>
                            </Select.Root>
                            {matched && (
                              <span className="text-xs text-emerald-800 dark:text-emerald-300">
                                {t("gateForm.sections.pathsMatch", { id: matched.id })}
                              </span>
                            )}
                          </div>
                          <div className="flex flex-wrap items-end justify-between gap-2">
                            <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-3">
                              <div className="flex flex-col gap-1.5">
                                <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                  {t("gateForm.sections.sniHostname")}
                                </span>
                                <Input.Root
                                  value={row.hostname}
                                  onChange={(e) => updateSniRow(i, { hostname: e.target.value })}
                                  disabled={formDisabled}
                                  placeholder="app.local"
                                />
                              </div>
                              <div className="flex flex-col gap-1.5">
                                <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                  {t("gateForm.sections.certPem")}
                                </span>
                                <Input.Root
                                  value={row.cert_file}
                                  onChange={(e) => updateSniRow(i, { cert_file: e.target.value })}
                                  disabled={formDisabled}
                                  placeholder="C:/path/fullchain.pem"
                                />
                              </div>
                              <div className="flex flex-col gap-1.5">
                                <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                  {t("gateForm.sections.keyPem")}
                                </span>
                                <Input.Root
                                  value={row.key_file}
                                  onChange={(e) => updateSniRow(i, { key_file: e.target.value })}
                                  disabled={formDisabled}
                                  placeholder="C:/path/privkey.pem"
                                />
                              </div>
                            </div>
                            <Button
                              size="sm"
                              variant="secondary"
                              onPress={() => removeSniRow(i)}
                              isDisabled={formDisabled || model.sniRows.length <= 1}
                            >
                              {t("gateForm.sections.remove")}
                            </Button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card.Content>
          </Card.Root>

          <Card.Root
            id="gate-step-routes"
            className="scroll-mt-24 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <Card.Header className="px-6 pt-6">
              <StepSectionTitle step={3}>{t("gateForm.sections.routes")}</StepSectionTitle>
              <Card.Description className="mt-3 pl-11 text-slate-600 dark:text-slate-300">{t("gateForm.sections.routesDesc")}</Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-6 px-6 pb-6">
              <div className="flex justify-end">
                <Button size="sm" variant="secondary" onPress={addRoute} isDisabled={formDisabled || !canAddRoute}>
                  {t("gateForm.sections.addRoute")}
                </Button>
              </div>

              {model.routes.map((route, ri) => (
                <div
                  key={`route-${ri}`}
                  className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm ring-1 ring-slate-100/80 dark:border-slate-600 dark:bg-slate-900 dark:ring-slate-700/80"
                >
                  <div className="border-b border-slate-100 bg-gradient-to-r from-indigo-50/70 to-white px-4 py-3 sm:px-5 dark:border-slate-700 dark:from-indigo-950/60 dark:to-slate-900">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-900 dark:bg-indigo-900/50 dark:text-indigo-100">
                        {t("gateForm.flow.routeCardTitle", { index: ri + 1 })}
                      </span>
                      <Button
                        size="sm"
                        variant="secondary"
                        onPress={() => removeRoute(ri)}
                        isDisabled={formDisabled || model.routes.length <= 1}
                      >
                        {t("gateForm.sections.removeRoute")}
                      </Button>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">{t("gateForm.flow.routeCardExplain")}</p>
                  </div>

                  <div className="space-y-5 p-4 sm:p-5">
                    <div>
                      <Text className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {t("gateForm.flow.routeCardMatch")}
                      </Text>
                      <div className="grid min-w-0 gap-3 sm:grid-cols-2">
                        <div className="flex flex-col gap-1.5">
                          <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor={`gate-route-key-${ri}`}>
                            {t("gateForm.sections.routeKey")}
                          </Label.Root>
                          {(() => {
                            const opts = routeKeySelectOptions(route.routeKey, sniHostOptions);
                            const rk = route.routeKey.trim();
                            // routeKey が空なのに opts[0] を仮選択すると見た目だけ選ばれ、onSelectionChange が
                            // 発火せず検証エラーが消えない。空のときはプレースホルダーのみにする。
                            const selectedKey = opts.length === 0 || !rk ? undefined : rk;
                            return (
                              <Select.Root
                                id={`gate-route-key-${ri}`}
                                fullWidth
                                selectedKey={selectedKey}
                                onSelectionChange={(key) => {
                                  if (key) updateRoute(ri, { routeKey: String(key) });
                                }}
                                isDisabled={formDisabled || opts.length === 0}
                                placeholder={t("gateForm.sections.routeKeySelectEmpty")}
                                aria-label={t("gateForm.sections.routeKey")}
                              >
                                <Select.Trigger className="w-full min-w-0 justify-between">
                                  <Select.Value />
                                  <Select.Indicator />
                                </Select.Trigger>
                                <Select.Popover className="min-w-[var(--trigger-width)]">
                                  <ListBox.Root>
                                    {opts.map((h) => (
                                      <ListBox.Item key={h} id={h} textValue={h}>
                                        {h}
                                      </ListBox.Item>
                                    ))}
                                  </ListBox.Root>
                                </Select.Popover>
                              </Select.Root>
                            );
                          })()}
                          <Text className="text-xs text-slate-500 dark:text-slate-400">{t("gateForm.sections.routeKeySelectHint")}</Text>
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor={`gate-route-lb-${ri}`}>
                            {t("gateForm.sections.loadBalance")}
                          </Label.Root>
                          <Select.Root
                            id={`gate-route-lb-${ri}`}
                            fullWidth
                            selectedKey={route.strategy}
                            onSelectionChange={(key) => {
                              if (key === "least_conn" || key === "round_robin") {
                                updateRoute(ri, { strategy: key });
                              }
                            }}
                            isDisabled={formDisabled}
                          >
                            <Select.Trigger className="w-full min-w-0 justify-between">
                              <Select.Value />
                              <Select.Indicator />
                            </Select.Trigger>
                            <Select.Popover className="min-w-[var(--trigger-width)]">
                              <ListBox.Root>
                                <ListBox.Item id="least_conn" textValue={t("gateForm.sections.lbLeastConn")}>
                                  {t("gateForm.sections.lbLeastConn")}
                                </ListBox.Item>
                                <ListBox.Item id="round_robin" textValue={t("gateForm.sections.lbRoundRobin")}>
                                  {t("gateForm.sections.lbRoundRobin")}
                                </ListBox.Item>
                              </ListBox.Root>
                            </Select.Popover>
                          </Select.Root>
                        </div>
                      </div>
                    </div>

                    <div className="border-t border-dashed border-slate-200 pt-4 dark:border-slate-600">
                      <Text className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {t("gateForm.flow.routeCardForward")}
                      </Text>
                      <div className="flex flex-col gap-3">
                        {route.upstreams.map((up, ui) => (
                          <div
                            key={`up-${ri}-${ui}`}
                            className="rounded-lg border border-indigo-100/80 bg-slate-50/90 p-3 ring-1 ring-slate-100/60 dark:border-indigo-900/40 dark:bg-slate-800/80 dark:ring-slate-700/60"
                          >
                            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-12 lg:items-end">
                              <div className="min-w-0 sm:col-span-1 lg:col-span-3">
                                <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">{t("common.host")}</span>
                                <Input.Root
                                  className="w-full min-w-0"
                                  value={up.host}
                                  onChange={(e) => updateUpstream(ri, ui, { host: e.target.value })}
                                  disabled={formDisabled}
                                />
                              </div>
                              <div className="min-w-0 sm:col-span-1 lg:col-span-2">
                                <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">{t("common.port")}</span>
                                <Input.Root
                                  className="w-full min-w-0"
                                  value={up.port}
                                  onChange={(e) => updateUpstream(ri, ui, { port: e.target.value })}
                                  disabled={formDisabled}
                                  inputMode="numeric"
                                />
                              </div>
                              <div className="min-w-0 sm:col-span-2 lg:col-span-4">
                                <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">
                                  {t("gateForm.sections.upstreamTlsSni")}
                                </span>
                                <Input.Root
                                  className="w-full min-w-0"
                                  value={up.tlsServerHostname}
                                  onChange={(e) => updateUpstream(ri, ui, { tlsServerHostname: e.target.value })}
                                  disabled={formDisabled}
                                  placeholder={t("gateForm.sections.upstreamTlsPlaceholder")}
                                />
                              </div>
                              <div className="min-w-0 sm:col-span-2 lg:col-span-2">
                                <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">
                                  {t("gateForm.sections.alpn")}
                                </span>
                                <Input.Root
                                  className="w-full min-w-0"
                                  value={up.tlsAlpn}
                                  onChange={(e) => updateUpstream(ri, ui, { tlsAlpn: e.target.value })}
                                  disabled={formDisabled}
                                  placeholder="h2, http/1.1"
                                />
                              </div>
                              <div className="flex min-w-0 justify-end sm:col-span-2 lg:col-span-1">
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onPress={() => removeUpstream(ri, ui)}
                                  isDisabled={formDisabled || route.upstreams.length <= 1}
                                >
                                  ×
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                        <Button size="sm" variant="secondary" onPress={() => addUpstream(ri)} isDisabled={formDisabled}>
                          {t("gateForm.sections.addUpstreamToRoute")}
                        </Button>
                      </div>
                    </div>

                    <Disclosure.Root className="rounded-xl border border-slate-200 bg-slate-50/50 dark:border-slate-700 dark:bg-slate-800/40">
                      <Disclosure.Trigger className="flex w-full list-none items-center justify-between gap-2 px-3 py-2.5 text-left text-sm font-medium text-slate-800 hover:bg-slate-100/80 dark:text-slate-100 dark:hover:bg-slate-800/80">
                        <span>
                          {t("gateForm.httpDispatch.title")}
                          <span className="ml-2 font-normal text-slate-500 dark:text-slate-400">
                            {t("gateForm.httpDispatch.optional")}
                          </span>
                        </span>
                        <Disclosure.Indicator className="shrink-0 text-slate-500 dark:text-slate-400" />
                      </Disclosure.Trigger>
                      <Disclosure.Content>
                        <Disclosure.Body className="space-y-4 border-t border-slate-200 px-3 pb-4 pt-3 dark:border-slate-600">
                        <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">{t("gateForm.httpDispatch.summary")}</p>
                        <Checkbox.Root
                          className="flex max-w-full items-start gap-2 text-sm text-slate-800 dark:text-slate-200"
                          isSelected={!!route.httpDispatch?.enabled}
                          onChange={(v) => setHttpDispatchEnabled(ri, v)}
                          isDisabled={formDisabled}
                        >
                          <Checkbox.Control>
                            <Checkbox.Indicator />
                          </Checkbox.Control>
                          <Checkbox.Content>{t("gateForm.httpDispatch.enable")}</Checkbox.Content>
                        </Checkbox.Root>
                        {route.httpDispatch?.enabled && (
                          <>
                            <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">{t("gateForm.httpDispatch.help")}</p>
                            <div className="flex max-w-md flex-col gap-1.5">
                              <Label.Root className="text-slate-700 dark:text-slate-200" htmlFor={`gate-http-default-${ri}`}>
                                {t("gateForm.httpDispatch.defaultUpstream")}
                              </Label.Root>
                              <Select.Root
                                id={`gate-http-default-${ri}`}
                                fullWidth
                                selectedKey={String(route.httpDispatch.defaultUpstreamIndex)}
                                onSelectionChange={(key) => {
                                  if (key == null) return;
                                  patchHttpDispatch(ri, { defaultUpstreamIndex: Number(key) });
                                }}
                                isDisabled={formDisabled}
                              >
                                <Select.Trigger className="w-full min-w-0 justify-between">
                                  <Select.Value />
                                  <Select.Indicator />
                                </Select.Trigger>
                                <Select.Popover className="min-w-[var(--trigger-width)]">
                                  <ListBox.Root>
                                    {route.upstreams.map((u, ui) => (
                                      <ListBox.Item
                                        key={`hd-def-${ri}-${ui}`}
                                        id={String(ui)}
                                        textValue={`${u.host}:${u.port}`}
                                      >
                                        {t("gateForm.httpDispatch.upstreamOption", {
                                          n: ui + 1,
                                          host: u.host.trim() || "?",
                                          port: u.port.trim() || "?",
                                        })}
                                      </ListBox.Item>
                                    ))}
                                  </ListBox.Root>
                                </Select.Popover>
                              </Select.Root>
                            </div>
                            <div>
                              <Text className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                                {t("gateForm.httpDispatch.rulesHeading")}
                              </Text>
                              <div className="flex flex-col gap-3">
                                {route.httpDispatch.rules.map((rule, rj) => (
                                  <div
                                    key={`http-rule-${ri}-${rj}`}
                                    className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-600 dark:bg-slate-900"
                                  >
                                    <div className="mb-2 flex items-center justify-between gap-2">
                                      <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                        {t("gateForm.httpDispatch.ruleLabel", { n: rj + 1 })}
                                      </span>
                                      <Button
                                        size="sm"
                                        variant="secondary"
                                        onPress={() => removeHttpRule(ri, rj)}
                                        isDisabled={formDisabled}
                                      >
                                        {t("gateForm.httpDispatch.removeRule")}
                                      </Button>
                                    </div>
                                    <div className="grid gap-3 sm:grid-cols-2">
                                      <div className="flex flex-col gap-1.5 sm:col-span-2">
                                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                          {t("gateForm.httpDispatch.targetUpstream")}
                                        </span>
                                        <Select.Root
                                          fullWidth
                                          selectedKey={String(rule.upstreamIndex)}
                                          onSelectionChange={(key) => {
                                            if (key == null) return;
                                            updateHttpRule(ri, rj, { upstreamIndex: Number(key) });
                                          }}
                                          isDisabled={formDisabled}
                                        >
                                          <Select.Trigger className="w-full min-w-0 justify-between">
                                            <Select.Value />
                                            <Select.Indicator />
                                          </Select.Trigger>
                                          <Select.Popover className="min-w-[var(--trigger-width)]">
                                            <ListBox.Root>
                                              {route.upstreams.map((u, ui) => (
                                                <ListBox.Item
                                                  key={`hd-r-${ri}-${rj}-${ui}`}
                                                  id={String(ui)}
                                                  textValue={`${u.host}:${u.port}`}
                                                >
                                                  {t("gateForm.httpDispatch.upstreamOption", {
                                                    n: ui + 1,
                                                    host: u.host.trim() || "?",
                                                    port: u.port.trim() || "?",
                                                  })}
                                                </ListBox.Item>
                                              ))}
                                            </ListBox.Root>
                                          </Select.Popover>
                                        </Select.Root>
                                      </div>
                                      <div className="flex flex-col gap-1.5">
                                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                          {t("gateForm.httpDispatch.pathMode")}
                                        </span>
                                        <Select.Root
                                          fullWidth
                                          selectedKey={rule.pathMode}
                                          onSelectionChange={(key) => {
                                            if (key === "any" || key === "exact" || key === "prefix") {
                                              updateHttpRule(ri, rj, {
                                                pathMode: key as HttpPathMatchMode,
                                                path: key === "any" ? "" : rule.path,
                                              });
                                            }
                                          }}
                                          isDisabled={formDisabled}
                                        >
                                          <Select.Trigger className="w-full min-w-0 justify-between">
                                            <Select.Value />
                                            <Select.Indicator />
                                          </Select.Trigger>
                                          <Select.Popover className="min-w-[var(--trigger-width)]">
                                            <ListBox.Root>
                                              <ListBox.Item id="any" textValue={t("gateForm.httpDispatch.pathModeAny")}>
                                                {t("gateForm.httpDispatch.pathModeAny")}
                                              </ListBox.Item>
                                              <ListBox.Item id="exact" textValue={t("gateForm.httpDispatch.pathModeExact")}>
                                                {t("gateForm.httpDispatch.pathModeExact")}
                                              </ListBox.Item>
                                              <ListBox.Item id="prefix" textValue={t("gateForm.httpDispatch.pathModePrefix")}>
                                                {t("gateForm.httpDispatch.pathModePrefix")}
                                              </ListBox.Item>
                                            </ListBox.Root>
                                          </Select.Popover>
                                        </Select.Root>
                                      </div>
                                      {(rule.pathMode === "exact" || rule.pathMode === "prefix") && (
                                        <div className="flex flex-col gap-1.5 sm:col-span-2">
                                          <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                            {t("gateForm.httpDispatch.path")}
                                          </span>
                                          <Input.Root
                                            value={rule.path}
                                            onChange={(e) => updateHttpRule(ri, rj, { path: e.target.value })}
                                            disabled={formDisabled}
                                            placeholder={t("gateForm.httpDispatch.pathPlaceholder")}
                                          />
                                        </div>
                                      )}
                                      <div className="flex flex-col gap-1.5 sm:col-span-2">
                                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                          {t("gateForm.httpDispatch.methods")}
                                        </span>
                                        <Input.Root
                                          value={rule.methods}
                                          onChange={(e) => updateHttpRule(ri, rj, { methods: e.target.value })}
                                          disabled={formDisabled}
                                          placeholder={t("gateForm.httpDispatch.methodsPlaceholder")}
                                        />
                                      </div>
                                    </div>
                                  </div>
                                ))}
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onPress={() => addHttpRule(ri)}
                                  isDisabled={formDisabled}
                                >
                                  {t("gateForm.httpDispatch.addRule")}
                                </Button>
                              </div>
                            </div>
                          </>
                        )}
                      </Disclosure.Body>
                      </Disclosure.Content>
                    </Disclosure.Root>
                  </div>
                </div>
              ))}

              {validationError && (
                <Alert.Root status="warning" role="status">
                  <Alert.Indicator />
                  <Alert.Content>
                    <Alert.Description>{validationError}</Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}
            </Card.Content>
          </Card.Root>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              onPress={() => void onSave()}
              isDisabled={formDisabled || !!validationError || saving}
            >
              {saving ? (
                <span className="inline-flex items-center gap-2">
                  <Spinner.Root size="sm" color="current" />
                  {t("common.working")}
                </span>
              ) : isNew ? (
                t("gateForm.sections.createGate")
              ) : (
                t("gateForm.sections.saveChanges")
              )}
            </Button>
            <Button variant="secondary" onPress={() => navigate("/gates")}>
              {t("common.cancel")}
            </Button>
            {!isNew && (
              <ConfirmAlertDialog
                title={t("common.confirmDeleteTitle")}
                body={t("gateForm.confirmDelete", { id })}
                cancelLabel={t("common.cancel")}
                confirmLabel={t("common.deleteConfirm")}
                onConfirm={performDeleteGate}
                trigger={
                  <Button
                    variant="secondary"
                    className="border-red-200 text-red-800 hover:bg-red-50 dark:border-red-900/60 dark:text-red-300 dark:hover:bg-red-950/40"
                  >
                    {t("gateForm.sections.deleteGate")}
                  </Button>
                }
              />
            )}
          </div>

          <Disclosure.Root
            isExpanded={showJsonPreview}
            onExpandedChange={setShowJsonPreview}
            className="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/50"
          >
            <Disclosure.Trigger className="flex w-full items-center justify-between gap-2 text-left text-sm font-medium text-slate-800 dark:text-slate-100">
              {t("gateForm.sections.previewJson")}
              <Disclosure.Indicator className="text-slate-500 dark:text-slate-400" />
            </Disclosure.Trigger>
            <Disclosure.Content>
              <Disclosure.Body className="mt-3">
                <pre className="max-h-64 overflow-auto rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs text-slate-800 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100">
                  {previewJson || t("gateForm.sections.previewInvalid")}
                </pre>
              </Disclosure.Body>
            </Disclosure.Content>
          </Disclosure.Root>
          </div>
        </div>
      )}
    </>
  );
}
