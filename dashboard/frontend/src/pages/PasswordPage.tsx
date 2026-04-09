import { useState } from "react";

import { clsx } from "clsx";
import { useTranslation } from "react-i18next";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { Checkbox } from "@heroui/react/checkbox";
import { Input } from "@heroui/react/input";
import { Label } from "@heroui/react/label";
import { Text } from "@heroui/react/text";

import { PageHeader } from "@/components/PageHeader";
import { useClipboardFeedback } from "@/hooks/useClipboardFeedback";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatApiError } from "@/lib/apiErrors";
import { toast } from "@/lib/appToast";
import { generatePassword, type PasswordPreset } from "@/api";

function IconEye({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconEyeOff({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.06M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

export function PasswordPage() {
  const { t } = useTranslation();
  usePageTitle(t("pageTitles.password"));
  const [pwd, setPwd] = useState("");
  const [pwdVisible, setPwdVisible] = useState(false);
  const [len, setLen] = useState(24);
  const [uppercase, setUppercase] = useState(true);
  const [lowercase, setLowercase] = useState(true);
  const [digits, setDigits] = useState(true);
  const [symbols, setSymbols] = useState(true);
  const { copy: copyToClipboard } = useClipboardFeedback();

  const run = async (fn: () => Promise<{ password: string }>) => {
    try {
      const r = await fn();
      setPwd(r.password);
      setPwdVisible(false);
    } catch (e) {
      toast.danger(formatApiError(e, t));
    }
  };

  const genPreset = (preset: PasswordPreset) =>
    run(() => generatePassword({ kind: "preset", preset }));

  const genCustom = () =>
    run(() =>
      generatePassword({
        kind: "custom",
        length: len,
        uppercase,
        lowercase,
        digits,
        symbols,
      }),
    );

  const genSafari = () => run(() => generatePassword({ kind: "safari" }));
  const genFirefox = () => run(() => generatePassword({ kind: "firefox" }));

  const onCopyPassword = () => {
    if (!pwd) return;
    void copyToClipboard(pwd);
  };

  const classesActive = uppercase || lowercase || digits || symbols;

  return (
    <>
      <PageHeader title={t("password.title")} description={t("password.description")} />

      <Card.Root className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <Card.Content className="flex flex-col gap-8 px-6 py-6">
          <section aria-labelledby="pwd-strength-heading">
            <Text id="pwd-strength-heading" className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">
              {t("password.strengthSection")}
            </Text>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">{t("password.strengthSectionDesc")}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onPress={() => genPreset("low")}>
                {t("password.strengthLow")}
              </Button>
              <Button variant="primary" onPress={() => genPreset("medium")}>
                {t("password.strengthMedium")}
              </Button>
              <Button variant="primary" onPress={() => genPreset("high")}>
                {t("password.strengthHigh")}
              </Button>
            </div>
            <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-slate-500 dark:text-slate-400">
              <li>{t("password.strengthLowDesc")}</li>
              <li>{t("password.strengthMediumDesc")}</li>
              <li>{t("password.strengthHighDesc")}</li>
            </ul>
          </section>

          <section aria-labelledby="pwd-custom-heading">
            <Text id="pwd-custom-heading" className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">
              {t("password.customSection")}
            </Text>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">{t("password.customSectionDesc")}</p>

            <div className="mb-4 flex flex-wrap items-center gap-3">
              <Label.Root className="text-slate-700 dark:text-slate-200">{t("password.customLength")}</Label.Root>
              <Input.Root
                className="max-w-[8rem]"
                type="number"
                min={4}
                max={512}
                value={String(len)}
                onChange={(e) => setLen(Math.min(512, Math.max(4, Number(e.target.value) || 24)))}
                aria-label={t("password.ariaLength")}
              />
            </div>

            <fieldset
              className="rounded-lg border border-slate-200 bg-slate-50/80 px-4 py-3 dark:border-slate-600 dark:bg-slate-800/50"
              aria-describedby={!classesActive ? "pwd-need-class" : undefined}
            >
              <legend className="px-1 text-xs font-medium text-slate-700 dark:text-slate-300">{t("password.charClasses")}</legend>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <Checkbox.Root
                  className="flex max-w-full items-start gap-2 text-sm text-slate-800 dark:text-slate-200"
                  isSelected={uppercase}
                  onChange={setUppercase}
                >
                  <Checkbox.Control>
                    <Checkbox.Indicator />
                  </Checkbox.Control>
                  <Checkbox.Content>{t("password.includeUppercase")}</Checkbox.Content>
                </Checkbox.Root>
                <Checkbox.Root
                  className="flex max-w-full items-start gap-2 text-sm text-slate-800 dark:text-slate-200"
                  isSelected={lowercase}
                  onChange={setLowercase}
                >
                  <Checkbox.Control>
                    <Checkbox.Indicator />
                  </Checkbox.Control>
                  <Checkbox.Content>{t("password.includeLowercase")}</Checkbox.Content>
                </Checkbox.Root>
                <Checkbox.Root
                  className="flex max-w-full items-start gap-2 text-sm text-slate-800 dark:text-slate-200"
                  isSelected={digits}
                  onChange={setDigits}
                >
                  <Checkbox.Control>
                    <Checkbox.Indicator />
                  </Checkbox.Control>
                  <Checkbox.Content>{t("password.includeDigits")}</Checkbox.Content>
                </Checkbox.Root>
                <Checkbox.Root
                  className="flex max-w-full items-start gap-2 text-sm text-slate-800 dark:text-slate-200"
                  isSelected={symbols}
                  onChange={setSymbols}
                >
                  <Checkbox.Control>
                    <Checkbox.Indicator />
                  </Checkbox.Control>
                  <Checkbox.Content>{t("password.includeSymbols")}</Checkbox.Content>
                </Checkbox.Root>
              </div>
            </fieldset>
            <span id="pwd-need-class" className="sr-only">
              {t("password.needOneClass")}
            </span>

            <Button
              className="mt-4"
              variant="secondary"
              onPress={genCustom}
              isDisabled={!classesActive}
            >
              {t("password.generateCustom")}
            </Button>
          </section>

          <section aria-labelledby="pwd-browser-heading">
            <Text id="pwd-browser-heading" className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">
              {t("password.browserSection")}
            </Text>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">{t("password.browserSectionDesc")}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onPress={genSafari}>
                {t("password.safari")}
              </Button>
              <Button variant="secondary" onPress={genFirefox}>
                {t("password.firefox")}
              </Button>
            </div>
          </section>

          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <Label.Root className="text-slate-700 dark:text-slate-200">{t("password.output")}</Label.Root>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="secondary"
                  isIconOnly
                  isDisabled={!pwd}
                  aria-pressed={pwdVisible}
                  aria-label={pwdVisible ? t("password.ariaHidePassword") : t("password.ariaShowPassword")}
                  onPress={() => setPwdVisible((v) => !v)}
                >
                  {pwdVisible ? <IconEyeOff /> : <IconEye />}
                </Button>
                <Button size="sm" variant="secondary" onPress={onCopyPassword} isDisabled={!pwd}>
                  {t("common.copy")}
                </Button>
              </div>
            </div>
            <div
              className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-600 dark:bg-slate-800/80"
              aria-live="polite"
              aria-label={
                !pwd ? t("password.ariaOutput") : !pwdVisible ? t("password.ariaMasked") : undefined
              }
            >
              <code
                className={clsx(
                  "block whitespace-pre-wrap break-all font-mono text-sm leading-relaxed [word-break:break-word] selection:bg-slate-200 dark:selection:bg-slate-600",
                  pwd ? "text-slate-900 dark:text-slate-100" : "text-slate-400 dark:text-slate-500",
                )}
              >
                {!pwd ? (
                  t("password.emptyDash")
                ) : !pwdVisible ? (
                  <span className="inline-block select-none tracking-widest" aria-hidden>
                    {Array.from(pwd)
                      .map(() => "•")
                      .join("")}
                  </span>
                ) : (
                  pwd
                )}
              </code>
            </div>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{t("password.hint")}</p>
          </div>
        </Card.Content>
      </Card.Root>
    </>
  );
}
