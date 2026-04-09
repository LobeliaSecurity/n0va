import { useTranslation } from "react-i18next";

import type { GateFormModel } from "@/gate/gateConfig";

function FlowArrow() {
  return (
    <div
      className="flex shrink-0 items-center justify-center text-slate-300 dark:text-slate-600 md:min-h-[4.5rem] md:w-8 md:self-center"
      aria-hidden
    >
      <span className="rotate-90 text-xl font-light md:rotate-0">→</span>
    </div>
  );
}

type StepBoxProps = {
  kicker: string;
  title: string;
  detail: string;
  caption?: string;
};

function StepBox({ kicker, title, detail, caption }: StepBoxProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-100/80 dark:border-slate-600 dark:bg-slate-900 dark:ring-slate-700/80">
      <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">{kicker}</span>
      <p className="mt-1.5 break-words font-mono text-sm font-medium text-slate-900 dark:text-slate-50">{title}</p>
      <p className="mt-1 break-words text-xs leading-snug text-slate-600 dark:text-slate-300">{detail}</p>
      {caption ? <p className="mt-2 text-[0.7rem] leading-snug text-slate-500 dark:text-slate-400">{caption}</p> : null}
    </div>
  );
}

export function GateFormFlowOverview({ model }: { model: GateFormModel }) {
  const { t } = useTranslation();

  const host = model.listen.host.trim() || "0.0.0.0";
  const port = model.listen.port.trim() || "?";
  const listenTitle = `${host}:${port}`;

  const sniHosts = model.sniRows.map((r) => r.hostname.trim()).filter(Boolean);

  const entranceTitle = t("gateForm.flow.tlsEntrance");

  const entranceDetail =
    sniHosts.length === 0
      ? t("gateForm.flow.noHostnamesYet")
      : sniHosts.length <= 4
        ? sniHosts.join(", ")
        : `${sniHosts.slice(0, 4).join(", ")} ${t("gateForm.flow.hostsMore", { count: sniHosts.length - 4 })}`;

  const entranceCaption = t("gateForm.flow.tlsEntranceCaption");

  const routeSummaries = model.routes.map((route) => {
    const key = route.routeKey.trim() || "—";
    const targetParts = route.upstreams.map((u) => `${u.host.trim() || "?"}:${u.port.trim() || "?"}`);
    return {
      key,
      targetParts: targetParts.length > 0 ? targetParts : null,
      httpRules: route.httpDispatch?.enabled === true,
    };
  });

  return (
    <section
      className="rounded-2xl border border-indigo-100/80 bg-gradient-to-br from-indigo-50/50 via-white to-slate-50/80 p-5 shadow-sm ring-1 ring-indigo-100/60 dark:border-indigo-900/40 dark:from-indigo-950/35 dark:via-slate-900 dark:to-slate-900 dark:ring-indigo-900/40"
      aria-labelledby="gate-flow-heading"
    >
      <h2 id="gate-flow-heading" className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-50">
        {t("gateForm.flow.title")}
      </h2>
      <p className="mt-1.5 max-w-3xl text-xs leading-relaxed text-slate-600 dark:text-slate-300">{t("gateForm.flow.subtitle")}</p>

      <div className="mt-5 flex flex-col gap-4 md:flex-row md:items-stretch md:gap-0">
        <StepBox
          kicker={t("gateForm.flow.stepListen")}
          title={listenTitle}
          detail={t("gateForm.flow.listenDetail")}
          caption={t("gateForm.flow.listenCaption")}
        />
        <FlowArrow />
        <StepBox kicker={t("gateForm.flow.stepEntrance")} title={entranceTitle} detail={entranceDetail} caption={entranceCaption} />
        <FlowArrow />
        <div className="flex min-w-0 flex-1 flex-col rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-100/80 dark:border-slate-600 dark:bg-slate-900 dark:ring-slate-700/80">
          <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
            {t("gateForm.flow.stepRoutes")}
          </span>
          <p className="mt-1.5 text-xs leading-relaxed text-slate-600 dark:text-slate-300">{t("gateForm.flow.routesIntro")}</p>
          <ul className="mt-3 min-w-0 space-y-2.5">
            {routeSummaries.map((r, i) => (
              <li
                key={`flow-route-${i}`}
                className="min-w-0 rounded-lg border border-slate-100 bg-slate-50/90 px-3 py-2.5 text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800/80 dark:text-slate-200"
              >
                <div className="flex min-w-0 flex-wrap items-start gap-x-2 gap-y-1">
                  <div className="min-w-0 flex-1 basis-[min(100%,12rem)]">
                    <p className="text-[0.65rem] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {t("gateForm.flow.routeCardMatch")}
                    </p>
                    <p
                      className="mt-0.5 break-all font-mono text-[0.8125rem] font-semibold leading-snug text-indigo-900 dark:text-indigo-200"
                      title={r.key}
                    >
                      {r.key}
                    </p>
                  </div>
                  {r.httpRules ? (
                    <span className="shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
                      {t("gateForm.flow.httpBadge")}
                    </span>
                  ) : null}
                </div>
                <div className="mt-2.5 min-w-0 border-t border-slate-200/80 pt-2.5 dark:border-slate-600/80">
                  <p className="text-[0.65rem] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {t("gateForm.flow.routeCardForward")}
                  </p>
                  {r.targetParts ? (
                    <ul className="mt-1 min-w-0 list-none space-y-1 p-0">
                      {r.targetParts.map((part, j) => (
                        <li
                          key={`flow-route-${i}-up-${j}`}
                          className="flex min-w-0 items-start gap-2 font-mono text-[0.8125rem] leading-snug text-slate-700 dark:text-slate-300"
                        >
                          <span className="mt-0.5 shrink-0 text-slate-400 dark:text-slate-500" aria-hidden>
                            →
                          </span>
                          <span className="min-w-0 break-all">{part}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 break-words text-slate-500 italic dark:text-slate-400">{t("gateForm.flow.noUpstreams")}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
