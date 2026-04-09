import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { useTranslation } from "react-i18next";

import "@/i18n/config";

import { appRouter } from "@/appRouter";
import { DashboardErrorBoundary } from "@/components/DashboardErrorBoundary";
import { ThemeModeProvider } from "@/context/ThemeModeContext";
import { Toast } from "@heroui/react/toast";

import "./styles/globals.css";

function AppRoot() {
  const { t } = useTranslation();
  return (
    <DashboardErrorBoundary
      title={t("errorBoundary.title")}
      body={t("errorBoundary.body")}
      reloadLabel={t("errorBoundary.reload")}
      homeLabel={t("errorBoundary.home")}
    >
      <ThemeModeProvider>
        <RouterProvider router={appRouter} />
        <Toast.Provider placement="bottom end" />
      </ThemeModeProvider>
    </DashboardErrorBoundary>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppRoot />
  </React.StrictMode>,
);
