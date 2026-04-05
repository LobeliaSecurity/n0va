import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { CaDetailPage } from "@/pages/CaDetailPage";
import { CaListPage } from "@/pages/CaListPage";
import { GateFormPage } from "@/pages/GateFormPage";
import { GatesPage } from "@/pages/GatesPage";
import { HomePage } from "@/pages/HomePage";
import { HostsPage } from "@/pages/HostsPage";
import { PasswordPage } from "@/pages/PasswordPage";
import { SettingsPage } from "@/pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/gates" element={<GatesPage />} />
        <Route path="/gates/:gateId" element={<GateFormPage />} />
        <Route path="/hosts" element={<HostsPage />} />
        <Route path="/ca" element={<CaListPage />} />
        <Route path="/ca/:caId" element={<CaDetailPage />} />
        <Route path="/password" element={<PasswordPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
