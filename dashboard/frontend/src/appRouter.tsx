import { createHashRouter } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { CaDetailPage } from "@/pages/CaDetailPage";
import { CaListPage } from "@/pages/CaListPage";
import { ContentServersPage } from "@/pages/ContentServersPage";
import { GateFormPage } from "@/pages/GateFormPage";
import { GatesPage } from "@/pages/GatesPage";
import { HomePage } from "@/pages/HomePage";
import { HostsPage } from "@/pages/HostsPage";
import { PasswordPage } from "@/pages/PasswordPage";
import { SettingsPage } from "@/pages/SettingsPage";

/** `useBlocker` などデータルーター API 用（`HashRouter` では未対応） */
export const appRouter = createHashRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "content", element: <ContentServersPage /> },
      { path: "gates", element: <GatesPage /> },
      { path: "gates/:gateId", element: <GateFormPage /> },
      { path: "hosts", element: <HostsPage /> },
      { path: "ca", element: <CaListPage /> },
      { path: "ca/:caId", element: <CaDetailPage /> },
      { path: "password", element: <PasswordPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);
