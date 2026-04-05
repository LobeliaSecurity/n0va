import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import enGB from "@/locales/en-GB.json";
import ja from "@/locales/ja.json";

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      "en-GB": { translation: enGB },
      ja: { translation: ja },
    },
    fallbackLng: "en-GB",
    supportedLngs: ["en-GB", "ja"],
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "i18nextLng",
    },
  });

export default i18n;
