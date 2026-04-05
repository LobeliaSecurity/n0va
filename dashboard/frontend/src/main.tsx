import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";

import "@/i18n/config";

import { Toast } from "@heroui/react/toast";

import App from "./App";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <App />
      <Toast.Provider placement="bottom end" />
    </HashRouter>
  </React.StrictMode>,
);
