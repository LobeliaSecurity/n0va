import { useCallback, useEffect, useRef, useState } from "react";

import { useHref, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Alert } from "@heroui/react/alert";
import { Breadcrumbs } from "@heroui/react/breadcrumbs";
import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { Text } from "@heroui/react/text";

import { AppLink } from "@/components/AppLink";
import { CardRowSkeleton } from "@/components/DashboardSkeletons";
import { ConfirmAlertDialog } from "@/components/ConfirmAlertDialog";
import { PageHeader } from "@/components/PageHeader";
import { useClipboardFeedback } from "@/hooks/useClipboardFeedback";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { toast } from "@/lib/appToast";
import {
  deleteCa,
  deleteIssuedCert,
  getCa,
  issueCertForCa,
  listIssued,
  type CaDetailDto,
  type IssuedCertDto,
} from "@/api";

type Tab = "overview" | "issue" | "issued";

function PathLine({
  label,
  path,
  copyLabel,
  onCopy,
}: {
  label: string;
  path: string;
  copyLabel: string;
  onCopy: () => void;
}) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
      <Label.Root className="shrink-0 text-xs font-medium text-slate-500 dark:text-slate-400">{label}</Label.Root>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <code className="break-all rounded-md bg-slate-100 px-2 py-1 font-mono text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-200">
          {path}
        </code>
        <Button size="sm" variant="secondary" onPress={onCopy}>
          {copyLabel}
        </Button>
      </div>
    </div>
  );
}

export function CaDetailPage() {
  const { t } = useTranslation();
  const { caId } = useParams<{ caId: string }>();
  const navigate = useNavigate();
  const hrefCaList = useHref("/ca");
  const hrefSelf = useHref(`/ca/${caId ?? ""}`);
  const id = Number(caId);
  const invalid = Number.isNaN(id);

  const [tab, setTab] = useState<Tab>("overview");
  const [detail, setDetail] = useState<CaDetailDto | null>(null);
  const [issued, setIssued] = useState<IssuedCertDto[]>([]);
  const [loading, setLoading] = useState(true);

  const [issueCn, setIssueCn] = useState("localhost");
  const [issueOrg, setIssueOrg] = useState("");
  const { copy: copyToClipboard } = useClipboardFeedback();
  const invalidToastShown = useRef(false);

  const loadDetail = useCallback(async () => {
    if (invalid) return;
    setLoading(true);
    try {
      const d = await getCa(id);
      setDetail(d);
    } catch (e) {
      toast.danger(formatApiError(e, t));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [id, invalid, t]);

  const loadIssued = useCallback(async () => {
    if (invalid) return;
    try {
      const r = await listIssued(id);
      setIssued(r.certificates);
    } catch (e) {
      toast.danger(formatApiError(e, t));
    }
  }, [id, invalid, t]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    if (tab === "issued") void loadIssued();
  }, [tab, loadIssued]);

  const onIssue = async () => {
    try {
      await issueCertForCa(id, {
        common_name: issueCn.trim(),
        organization: issueOrg,
        state: "",
        locality: "",
        country: "",
      });
      toast.success(t("caDetail.msgIssued"));
      await loadIssued();
      setTab("issued");
    } catch (e) {
      toast.danger(formatApiError(e, t));
    }
  };

  const performDeleteCa = async () => {
    try {
      await deleteCa(id);
      navigate("/ca");
    } catch (e) {
      toast.danger(formatApiError(e, t));
      throw e;
    }
  };

  useEffect(() => {
    if (invalid && !invalidToastShown.current) {
      invalidToastShown.current = true;
      toast.danger(t("caDetail.invalid"));
    }
  }, [invalid, t]);

  usePageTitle(detail ? `${detail.name} — ${t("pageTitles.caDetail")}` : t("pageTitles.caDetail"));

  if (invalid) {
    return (
      <div className="mb-6">
        <AppLink
          to="/ca"
          className="text-sm font-medium text-indigo-700 underline decoration-indigo-200 underline-offset-2 dark:text-indigo-300 dark:decoration-indigo-700"
        >
          {t("caDetail.backAll")}
        </AppLink>
      </div>
    );
  }

  const tabs: { k: Tab; labelKey: string }[] = [
    { k: "overview", labelKey: "caDetail.tabOverview" },
    { k: "issue", labelKey: "caDetail.tabIssue" },
    { k: "issued", labelKey: "caDetail.tabIssued" },
  ];

  return (
    <>
      <PageHeader
        breadcrumbs={
          <Breadcrumbs.Root className="text-sm" separator="/">
            <Breadcrumbs.Item href={hrefCaList}>{t("ca.breadcrumbList")}</Breadcrumbs.Item>
            <Breadcrumbs.Item href={hrefSelf}>
              {detail?.name ?? `#${id}`}
            </Breadcrumbs.Item>
          </Breadcrumbs.Root>
        }
        title={detail ? detail.name : t("caDetail.loadingTitle")}
        description={
          detail
            ? t("caDetail.descWithDetail", { cn: detail.common_name, count: detail.issued_count })
            : t("caDetail.loadingDesc")
        }
      />

      <div className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-4 dark:border-slate-700">
        {tabs.map(({ k, labelKey }) => (
          <Button key={k} size="sm" variant={tab === k ? "primary" : "secondary"} onPress={() => setTab(k)}>
            {t(labelKey)}
          </Button>
        ))}
      </div>

      {loading && !detail && (
        <div aria-live="polite">
          <CardRowSkeleton rows={2} />
        </div>
      )}

      {detail && tab === "overview" && (
        <div className="flex flex-col gap-6">
          <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <Card.Header className="px-6 pt-6">
              <Card.Title className="text-base text-slate-900 dark:text-slate-50">{t("caDetail.pathsTitle")}</Card.Title>
              <Card.Description className="text-slate-600 dark:text-slate-300">
                {t("caDetail.pathsDataDir")}{" "}
                <code className="font-mono text-xs text-slate-800 dark:text-slate-200">{detail.data_dir ?? "—"}</code>
              </Card.Description>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4 px-6 pb-6">
              <PathLine
                label={t("caDetail.caCert")}
                path={detail.ca_cert_path}
                copyLabel={t("common.copy")}
                onCopy={() => void copyToClipboard(detail.ca_cert_path)}
              />
              <PathLine
                label={t("caDetail.caKey")}
                path={detail.ca_key_path}
                copyLabel={t("common.copy")}
                onCopy={() => void copyToClipboard(detail.ca_key_path)}
              />
              <Text className="text-xs text-slate-600 dark:text-slate-300">{t("caDetail.keysNote")}</Text>
              {detail.ca_passphrase != null && detail.ca_passphrase !== "" && (
                <Alert.Root status="warning">
                  <Alert.Indicator />
                  <Alert.Content>
                    <Alert.Description className="text-xs">{t("caDetail.legacyPassphrase")}</Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}
            </Card.Content>
          </Card.Root>

          <Alert.Root status="danger" className="rounded-xl border border-red-200 dark:border-red-900/50">
            <Alert.Indicator />
            <Alert.Content>
              <Alert.Title>{t("caDetail.dangerTitle")}</Alert.Title>
              <Alert.Description className="text-xs">{t("caDetail.dangerDesc")}</Alert.Description>
            </Alert.Content>
          </Alert.Root>
          <ConfirmAlertDialog
            title={t("common.confirmDeleteTitle")}
            body={t("caDetail.confirmDelete")}
            cancelLabel={t("common.cancel")}
            confirmLabel={t("common.deleteConfirm")}
            onConfirm={performDeleteCa}
            trigger={<Button variant="secondary">{t("caDetail.deleteCa")}</Button>}
          />
        </div>
      )}

      {detail && tab === "issue" && (
        <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <Card.Header className="px-6 pt-6">
            <Card.Title className="text-base text-slate-900 dark:text-slate-50">{t("caDetail.issueTitle")}</Card.Title>
            <Card.Description className="text-slate-600 dark:text-slate-300">{t("caDetail.issueDesc", { id })}</Card.Description>
          </Card.Header>
          <Card.Content className="flex flex-col gap-4 px-6 pb-6">
            <div className="flex flex-col gap-2">
              <Label.Root className="text-slate-700 dark:text-slate-200">{t("caDetail.cn")}</Label.Root>
              <Input.Root
                value={issueCn}
                onChange={(e) => setIssueCn(e.target.value)}
                placeholder={t("caDetail.cnPlaceholder")}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label.Root className="text-slate-700 dark:text-slate-200">{t("caDetail.orgOptional")}</Label.Root>
              <Input.Root value={issueOrg} onChange={(e) => setIssueOrg(e.target.value)} />
            </div>
            <Button variant="primary" onPress={onIssue}>
              {t("caDetail.issue")}
            </Button>
          </Card.Content>
        </Card.Root>
      )}

      {detail && tab === "issued" && (
        <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <Card.Header className="flex flex-row flex-wrap items-center justify-between gap-2 px-6 pt-6">
            <Card.Title className="text-base text-slate-900 dark:text-slate-50">{t("caDetail.issuedTitle")}</Card.Title>
            <Button size="sm" variant="secondary" onPress={() => void loadIssued()}>
              {t("common.refresh")}
            </Button>
          </Card.Header>
          <Card.Content className="px-6 pb-6">
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-600">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="bg-slate-50 text-xs font-medium uppercase tracking-wide text-slate-600 dark:bg-slate-800/80 dark:text-slate-300">
                  <tr>
                    <th className="px-3 py-2">{t("caDetail.thCn")}</th>
                    <th className="px-3 py-2">{t("caDetail.thSerial")}</th>
                    <th className="px-3 py-2">{t("caDetail.thCreated")}</th>
                    <th className="px-3 py-2">{t("caDetail.thCertificate")}</th>
                    <th className="px-3 py-2 w-32">{t("caDetail.thActions")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {issued.map((row) => (
                    <tr key={row.id} className="text-slate-800 dark:text-slate-200">
                      <td className="px-3 py-2 font-medium">{row.common_name}</td>
                      <td className="px-3 py-2 font-mono text-xs">{row.serial_number}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-600 dark:text-slate-400">{row.created_at}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          <Button
                            size="sm"
                            variant="secondary"
                            onPress={() => void copyToClipboard(row.cert_path)}
                          >
                            {t("caDetail.copyCertPath")}
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onPress={() => void copyToClipboard(row.key_path)}
                          >
                            {t("caDetail.copyKeyPath")}
                          </Button>
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top">
                        <ConfirmAlertDialog
                          title={t("common.confirmDeleteTitle")}
                          body={t("caDetail.confirmDeleteIssued", {
                            cn: row.common_name,
                            serial: row.serial_number,
                          })}
                          cancelLabel={t("common.cancel")}
                          confirmLabel={t("common.deleteConfirm")}
                          onConfirm={async () => {
                            try {
                              await deleteIssuedCert(id, row.id);
                              toast.success(t("caDetail.msgIssuedDeleted"));
                              await loadIssued();
                              await loadDetail();
                            } catch (e) {
                              toast.danger(formatApiError(e, t));
                              throw e;
                            }
                          }}
                          trigger={
                            <Button
                              size="sm"
                              variant="secondary"
                              className="text-red-800 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-950/40"
                            >
                              {t("caDetail.deleteIssued")}
                            </Button>
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {issued.length === 0 && (
              <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">{t("caDetail.noIssued")}</p>
            )}
          </Card.Content>
        </Card.Root>
      )}
    </>
  );
}
