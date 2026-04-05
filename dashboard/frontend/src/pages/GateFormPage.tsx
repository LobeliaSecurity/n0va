import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";

import { Link, useNavigate, useParams } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Checkbox } from "@heroui/react/checkbox";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { ListBox } from "@heroui/react/list-box";
import { Select } from "@heroui/react/select";
import { Text } from "@heroui/react/text";

import { ConfirmAlertDialog } from "@/components/ConfirmAlertDialog";
import { GateFormFlowOverview } from "@/components/GateFormFlowOverview";
import { PageHeader } from "@/components/PageHeader";
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
  return <h2 className="text-base font-semibold text-slate-900">{children}</h2>;
}

function StepSectionTitle({ step, children }: { step: number; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <span
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-800"
        aria-hidden
      >
        {step}
      </span>
      <h2 className="min-w-0 flex-1 text-base font-semibold leading-snug text-slate-900">{children}</h2>
    </div>
  );
}

function normalizePath(p: string): string {
  return p.trim().replace(/\\/g, "/");
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
      setGate(g);
      setName(g.name);
      setModel(gateConfigToForm(g.config));
    } catch (e) {
      toast.danger((e as Error).message);
      setGate(null);
    } finally {
      setLoading(false);
    }
  }, [id, invalidId, isNew]);

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
          routes = m.routes.map((r) => (r.routeKey === oldHost ? { ...r, routeKey: newHost } : r));
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
    try {
      if (isNew) {
        const created = await createGate({ name: name.trim() || "gate", config: cfg });
        toast.success(t("gateForm.msgCreated"));
        navigate(`/gates/${created.id}`, { replace: true });
      } else {
        await updateGate(id, { name: name.trim() || "gate", config: cfg });
        toast.success(t("gateForm.msgSaved"));
        await load();
      }
    } catch (e) {
      toast.danger((e as Error).message);
    }
  };

  const performDeleteGate = async () => {
    if (isNew) return;
    try {
      await deleteGate(id);
      navigate("/gates");
    } catch (e) {
      toast.danger((e as Error).message);
      throw e;
    }
  };

  const onStart = async () => {
    if (isNew) return;
    try {
      await startGate(id);
      await load();
    } catch (e) {
      toast.danger((e as Error).message);
    }
  };

  const onStop = async () => {
    if (isNew) return;
    try {
      await stopGate(id);
      await load();
    } catch (e) {
      toast.danger((e as Error).message);
    }
  };

  if (invalidId) {
    return (
      <>
        <PageHeader title={t("gateForm.invalidIdTitle")} description={t("gateForm.invalidIdDesc")} />
        <Link to="/gates" className="text-sm font-medium text-slate-700 underline">
          {t("gateForm.backToGates")}
        </Link>
      </>
    );
  }

  const formDisabled = running;

  return (
    <>
      <PageHeader
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
                  <Button variant="primary" onPress={onStart}>
                    {t("common.start")}
                  </Button>
                ) : (
                  <Button variant="secondary" onPress={onStop}>
                    {t("common.stop")}
                  </Button>
                )}
              </>
            )}
          </div>
        }
      />

      {!isNew && running && (
        <div
          className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
          role="status"
        >
          <Trans i18nKey="gateForm.runningBanner" components={RUNNING_BANNER_COMPONENTS} />
        </div>
      )}

      {loading && (
        <p className="mb-6 text-sm text-slate-500" aria-live="polite">
          {t("common.loading")}
        </p>
      )}

      {!loading && (
        <div className="flex flex-col gap-6">
          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <Card.Header className="px-6 pt-6">
              <SectionTitle>{t("gateForm.sections.identity")}</SectionTitle>
              <Card.Description className="text-slate-600">{t("gateForm.sections.identityDesc")}</Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4 px-6 pb-6">
              <div className="flex max-w-md flex-col gap-2">
                <Label.Root className="text-slate-700" htmlFor="gate-form-name">
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

          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <Card.Header className="px-6 pt-6">
              <StepSectionTitle step={1}>{t("gateForm.sections.listen")}</StepSectionTitle>
              <Card.Description className="mt-3 pl-11 text-slate-600">{t("gateForm.sections.listenDesc")}</Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4 px-6 pb-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label.Root className="text-slate-700" htmlFor="gate-form-listen-host">
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
                  <Label.Root className="text-slate-700" htmlFor="gate-form-listen-port">
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
              <details
                className="rounded-lg border border-slate-100 bg-slate-50/80 px-4 py-3"
                open={showAdvancedListen}
                onToggle={(e) => setShowAdvancedListen((e.target as HTMLDetailsElement).open)}
              >
                <summary className="cursor-pointer text-sm font-medium text-slate-800">
                  {t("gateForm.sections.advancedListen")}
                </summary>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-2">
                    <Label.Root className="text-slate-700" htmlFor="gate-form-listen-backlog">
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
                    <Label.Root className="text-slate-700" htmlFor="gate-form-listen-read-limit">
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
                </div>
              </details>
            </Card.Content>
          </Card.Root>

          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <Card.Header className="px-6 pt-6">
              <StepSectionTitle step={2}>{t("gateForm.sections.entrance")}</StepSectionTitle>
              <Card.Description className="mt-3 pl-11 text-slate-600">
                <p>
                  {t("gateForm.sections.entranceDescTlsOnlyBefore")}{" "}
                  <Link to="/ca" className="font-medium text-slate-900 underline">
                    {t("nav.ca")}
                  </Link>
                  {t("gateForm.sections.entranceDescTlsOnlyAfter")}
                </p>
              </Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-6 px-6 pb-6">
              <div className="flex flex-col gap-4">
                <p className="rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-xs leading-relaxed text-indigo-950">
                  {t("gateForm.flow.sniBlockExplain")}
                </p>
                <div className="flex items-center justify-between gap-2">
                  <Text className="text-sm font-medium text-slate-800">{t("gateForm.sections.tlsHostnames")}</Text>
                  <Button size="sm" variant="secondary" onPress={addSniRow} isDisabled={formDisabled}>
                    {t("gateForm.sections.addHostname")}
                  </Button>
                </div>
                {issuedCertsLoading && (
                  <p className="text-xs text-slate-500" aria-live="polite">
                    {t("gateForm.sections.loadingIssued")}
                  </p>
                )}
                {!issuedCertsLoading && issuedCerts.length === 0 && (
                  <p className="text-xs text-slate-600">
                    {t("gateForm.sections.noCertsHintBefore")}{" "}
                    <Link to="/ca" className="font-medium text-slate-900 underline">
                      {t("nav.ca")}
                    </Link>{" "}
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
                        className="rounded-lg border border-slate-200 bg-slate-50/50 p-4"
                      >
                        <div className="mb-3 flex flex-col gap-3">
                          <div className="flex flex-col gap-1.5">
                            <span className="text-xs font-medium text-slate-600">
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
                              <span className="text-xs text-emerald-800">
                                {t("gateForm.sections.pathsMatch", { id: matched.id })}
                              </span>
                            )}
                          </div>
                          <div className="flex flex-wrap items-end justify-between gap-2">
                            <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-3">
                              <div className="flex flex-col gap-1.5">
                                <span className="text-xs font-medium text-slate-600">
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
                                <span className="text-xs font-medium text-slate-600">
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
                                <span className="text-xs font-medium text-slate-600">
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

          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <Card.Header className="px-6 pt-6">
              <StepSectionTitle step={3}>{t("gateForm.sections.routes")}</StepSectionTitle>
              <Card.Description className="mt-3 pl-11 text-slate-600">{t("gateForm.sections.routesDesc")}</Card.Description>
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
                  className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm ring-1 ring-slate-100/80"
                >
                  <div className="border-b border-slate-100 bg-gradient-to-r from-indigo-50/70 to-white px-4 py-3 sm:px-5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-900">
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
                    <p className="mt-2 text-xs leading-relaxed text-slate-600">{t("gateForm.flow.routeCardExplain")}</p>
                  </div>

                  <div className="space-y-5 p-4 sm:p-5">
                    <div>
                      <Text className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("gateForm.flow.routeCardMatch")}
                      </Text>
                      <div className="grid min-w-0 gap-3 sm:grid-cols-2">
                        <div className="flex flex-col gap-1.5">
                          <Label.Root className="text-slate-700" htmlFor={`gate-route-key-${ri}`}>
                            {t("gateForm.sections.routeKey")}
                          </Label.Root>
                          {(() => {
                            const opts = routeKeySelectOptions(route.routeKey, sniHostOptions);
                            const rk = route.routeKey.trim();
                            const selectedKey =
                              opts.length === 0 ? null : opts.includes(rk) ? rk : opts[0];
                            return (
                              <Select.Root
                                id={`gate-route-key-${ri}`}
                                fullWidth
                                selectedKey={selectedKey ?? undefined}
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
                          <Text className="text-xs text-slate-500">{t("gateForm.sections.routeKeySelectHint")}</Text>
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <Label.Root className="text-slate-700" htmlFor={`gate-route-lb-${ri}`}>
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

                    <div className="border-t border-dashed border-slate-200 pt-4">
                      <Text className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("gateForm.flow.routeCardForward")}
                      </Text>
                      <div className="flex flex-col gap-3">
                        {route.upstreams.map((up, ui) => (
                          <div
                            key={`up-${ri}-${ui}`}
                            className="rounded-lg border border-indigo-100/80 bg-slate-50/90 p-3 ring-1 ring-slate-100/60"
                          >
                            <div className="grid gap-3 lg:grid-cols-12 lg:items-end">
                              <div className="lg:col-span-3">
                                <span className="mb-1 block text-xs font-medium text-slate-600">{t("common.host")}</span>
                                <Input.Root
                                  value={up.host}
                                  onChange={(e) => updateUpstream(ri, ui, { host: e.target.value })}
                                  disabled={formDisabled}
                                />
                              </div>
                              <div className="lg:col-span-2">
                                <span className="mb-1 block text-xs font-medium text-slate-600">{t("common.port")}</span>
                                <Input.Root
                                  value={up.port}
                                  onChange={(e) => updateUpstream(ri, ui, { port: e.target.value })}
                                  disabled={formDisabled}
                                  inputMode="numeric"
                                />
                              </div>
                              <div className="lg:col-span-4">
                                <span className="mb-1 block text-xs font-medium text-slate-600">
                                  {t("gateForm.sections.upstreamTlsSni")}
                                </span>
                                <Input.Root
                                  value={up.tlsServerHostname}
                                  onChange={(e) => updateUpstream(ri, ui, { tlsServerHostname: e.target.value })}
                                  disabled={formDisabled}
                                  placeholder={t("gateForm.sections.upstreamTlsPlaceholder")}
                                />
                              </div>
                              <div className="lg:col-span-2">
                                <span className="mb-1 block text-xs font-medium text-slate-600">
                                  {t("gateForm.sections.alpn")}
                                </span>
                                <Input.Root
                                  value={up.tlsAlpn}
                                  onChange={(e) => updateUpstream(ri, ui, { tlsAlpn: e.target.value })}
                                  disabled={formDisabled}
                                  placeholder="h2, http/1.1"
                                />
                              </div>
                              <div className="flex justify-end lg:col-span-1">
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

                    <details className="rounded-xl border border-slate-200 bg-slate-50/50 [&_summary::-webkit-details-marker]:hidden">
                      <summary className="cursor-pointer list-none px-3 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-100/80">
                        {t("gateForm.httpDispatch.title")}
                        <span className="ml-2 font-normal text-slate-500">{t("gateForm.httpDispatch.optional")}</span>
                      </summary>
                      <div className="space-y-4 border-t border-slate-200 px-3 pb-4 pt-3">
                        <p className="text-xs leading-relaxed text-slate-600">{t("gateForm.httpDispatch.summary")}</p>
                        <Checkbox.Root
                          className="flex max-w-full items-start gap-2 text-sm text-slate-800"
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
                            <p className="text-xs leading-relaxed text-slate-500">{t("gateForm.httpDispatch.help")}</p>
                            <div className="flex max-w-md flex-col gap-1.5">
                              <Label.Root className="text-slate-700" htmlFor={`gate-http-default-${ri}`}>
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
                              <Text className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                                {t("gateForm.httpDispatch.rulesHeading")}
                              </Text>
                              <div className="flex flex-col gap-3">
                                {route.httpDispatch.rules.map((rule, rj) => (
                                  <div
                                    key={`http-rule-${ri}-${rj}`}
                                    className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                                  >
                                    <div className="mb-2 flex items-center justify-between gap-2">
                                      <span className="text-xs font-medium text-slate-600">
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
                                        <span className="text-xs font-medium text-slate-600">
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
                                        <span className="text-xs font-medium text-slate-600">
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
                                          <span className="text-xs font-medium text-slate-600">
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
                                        <span className="text-xs font-medium text-slate-600">
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
                      </div>
                    </details>
                  </div>
                </div>
              ))}

              {validationError && (
                <p className="text-sm text-amber-800" role="status">
                  {validationError}
                </p>
              )}
            </Card.Content>
          </Card.Root>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" onPress={onSave} isDisabled={formDisabled || !!validationError}>
              {isNew ? t("gateForm.sections.createGate") : t("gateForm.sections.saveChanges")}
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
                  <Button variant="secondary" className="border-red-200 text-red-800 hover:bg-red-50">
                    {t("gateForm.sections.deleteGate")}
                  </Button>
                }
              />
            )}
          </div>

          <details
            className="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3"
            open={showJsonPreview}
            onToggle={(e) => setShowJsonPreview((e.target as HTMLDetailsElement).open)}
          >
            <summary className="cursor-pointer text-sm font-medium text-slate-800">
              {t("gateForm.sections.previewJson")}
            </summary>
            <pre className="mt-3 max-h-64 overflow-auto rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs text-slate-800">
              {previewJson || t("gateForm.sections.previewInvalid")}
            </pre>
          </details>
        </div>
      )}
    </>
  );
}
