const api = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const headers = new Headers(init?.headers);
  if (init?.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, {
    ...init,
    headers,
  });
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = { raw: text };
    }
  }
  if (!res.ok) {
    const err = data as { error?: string };
    throw new Error(err?.error || `HTTP ${res.status}`);
  }
  return data as T;
};

export type GateDto = {
  id: number;
  name: string;
  config: Record<string, unknown>;
  running: boolean;
  created_at?: string;
  updated_at?: string;
};

export const listGates = () =>
  api<{ gates: GateDto[] }>("/api/v1/gates");

export const getGate = (id: number) => api<GateDto>(`/api/v1/gates/${id}`);

export const createGate = (body: { name: string; config?: Record<string, unknown> }) =>
  api<GateDto>("/api/v1/gates", { method: "POST", body: JSON.stringify(body) });

export const updateGate = (id: number, body: { name: string; config: Record<string, unknown> }) =>
  api<GateDto>(`/api/v1/gates/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });

export const deleteGate = (id: number) =>
  api<{ ok: boolean }>(`/api/v1/gates/${id}`, { method: "DELETE" });

export const startGate = (id: number) =>
  api<{ ok: boolean; running: boolean }>(`/api/v1/gates/${id}/start`, {
    method: "POST",
    body: "{}",
  });

export const stopGate = (id: number) =>
  api<{ ok: boolean; running: boolean }>(`/api/v1/gates/${id}/stop`, {
    method: "POST",
    body: "{}",
  });

export const health = () => api<{ ok: boolean; db: string }>("/api/v1/health");

export type CaDto = {
  id: number;
  name: string;
  common_name: string;
  organization: string;
  state: string;
  locality: string;
  country: string;
  ca_cert_path: string;
  ca_key_path: string;
  created_at: string;
  updated_at: string;
  issued_count: number;
};

export type CaDetailDto = CaDto & {
  ca_passphrase: string | null;
  data_dir?: string;
};

export type IssuedCertDto = {
  id: number;
  ca_id: number;
  common_name: string;
  cert_path: string;
  key_path: string;
  pfx_path: string;
  serial_number: number;
  created_at: string;
};

/** 全 CA 横断の発行済み一覧（Gate の TLS パス参照用）。 */
export type IssuedCertRef = {
  id: number;
  ca_id: number;
  ca_name: string;
  common_name: string;
  cert_path: string;
  key_path: string;
  created_at: string;
};

export const listCas = () =>
  api<{ data_dir: string; cas: CaDto[] }>("/api/v1/cas");

export const getCa = (id: number) => api<CaDetailDto>(`/api/v1/cas/${id}`);

export const createCa = (body: Record<string, unknown>) =>
  api<CaDetailDto>("/api/v1/cas", { method: "POST", body: JSON.stringify(body) });

export const deleteCa = (id: number) =>
  api<{ ok: boolean; id: number }>(`/api/v1/cas/${id}`, { method: "DELETE" });

export const listIssued = (caId: number) =>
  api<{ ca_id: number; certificates: IssuedCertDto[] }>(
    `/api/v1/cas/${caId}/certificates`,
  );

export const deleteIssuedCert = (caId: number, issuedId: number) =>
  api<{ ok: boolean; id: number }>(`/api/v1/cas/${caId}/certificates/${issuedId}`, {
    method: "DELETE",
  });

export const listAllIssuedCertificates = () =>
  api<{ certificates: IssuedCertRef[] }>("/api/v1/issued-certificates");

export const issueCertForCa = (caId: number, body: Record<string, unknown>) =>
  api<{
    ok: boolean;
    id: number;
    cert: string;
    key: string;
    pfx: string;
    serial_number: number;
  }>(`/api/v1/cas/${caId}/issue`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const setDataDir = (data_dir: string) =>
  api<{ ok: boolean; data_dir: string }>("/api/v1/settings/data-dir", {
    method: "POST",
    body: JSON.stringify({ data_dir }),
  });

export type PasswordPreset = "low" | "medium" | "high";

export type PasswordGenerateRequest =
  | { kind: "safari" }
  | { kind: "firefox" }
  | { kind: "preset"; preset: PasswordPreset }
  | {
      kind: "custom";
      length: number;
      uppercase: boolean;
      lowercase: boolean;
      digits: boolean;
      symbols: boolean;
    };

export const generatePassword = (req: PasswordGenerateRequest) => {
  const params = new URLSearchParams();
  if (req.kind === "safari") {
    params.set("style", "safari");
  } else if (req.kind === "firefox") {
    params.set("style", "firefox");
  } else if (req.kind === "preset") {
    params.set("style", "preset");
    params.set("preset", req.preset);
  } else {
    params.set("style", "custom");
    params.set("length", String(req.length));
    params.set("uppercase", req.uppercase ? "1" : "0");
    params.set("lowercase", req.lowercase ? "1" : "0");
    params.set("digits", req.digits ? "1" : "0");
    params.set("symbols", req.symbols ? "1" : "0");
  }
  return api<{ password: string; style: string }>(
    `/api/v1/password/generate?${params.toString()}`,
  );
};

export type HostsDto = {
  path: string;
  content: string;
  readable: boolean;
  read_error: string | null;
  elevation_required_for_write: boolean;
};

export const getHosts = () => api<HostsDto>("/api/v1/hosts");

export const putHosts = (content: string) =>
  api<{ ok: boolean; path?: string; error?: string }>("/api/v1/hosts", {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
