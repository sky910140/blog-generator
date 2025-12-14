export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

let inviteCache = "";
export function setInviteCodeCache(code: string) {
  inviteCache = code;
  if (typeof sessionStorage !== "undefined") {
    if (code) {
      sessionStorage.setItem("inviteCode", code);
    } else {
      sessionStorage.removeItem("inviteCode");
    }
  }
}

export type Project = {
  id: string;
  title: string;
  source_type: string;
  local_video_path: string;
  duration?: number | null;
  status: string;
  progress: number;
  error_msg?: string | null;
  created_at: string;
  updated_at: string;
};

export type Step = {
  step_index: number;
  timestamp: number;
  title: string;
  description: string;
  image_path?: string;
};

export type Content = {
  project_id: string;
  ai_raw_data?: {
    summary?: string;
    steps: Step[];
  } | null;
  markdown_content?: string | null;
  updated_at: string;
};

export function resolveAssetUrl(path?: string | null) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/static")) return `${API_BASE}${path}`;
  return path;
}

function getInviteHeaders() {
  if (typeof window === "undefined") return {};
  const code =
    inviteCache ||
    (typeof sessionStorage !== "undefined" && sessionStorage.getItem("inviteCode")) ||
    "";
  return code ? { "X-Invite-Code": code } : {};
}

export async function uploadProject(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/projects/upload`, {
    method: "POST",
    body: form,
    headers: getInviteHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/api/projects`, { headers: getInviteHeaders() });
  if (!res.ok) {
    let detail = "无法获取任务列表";
    try {
      const data = await res.json();
      detail = (data as any)?.detail || detail;
    } catch (e) {
      // ignore
    }
    const err: any = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchProject(id: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/api/projects/${id}`, { headers: getInviteHeaders() });
  if (!res.ok) throw new Error("任务不存在");
  return res.json();
}

export async function fetchContent(id: string): Promise<Content> {
  const res = await fetch(`${API_BASE}/api/contents/${id}`, { headers: getInviteHeaders() });
  if (!res.ok) throw new Error("内容不存在");
  return res.json();
}

export async function updateContent(id: string, markdown: string) {
  const res = await fetch(`${API_BASE}/api/contents/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getInviteHeaders() },
    body: JSON.stringify({ markdown }),
  });
  if (!res.ok) throw new Error("更新失败");
  return res.json();
}

export async function exportZip(id: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/export/${id}`, { headers: getInviteHeaders() });
  if (!res.ok) throw new Error("导出失败");
  return res.blob();
}

export async function pushWechatDraft(id: string) {
  const res = await fetch(`${API_BASE}/api/wechat/draft?project_id=${id}`, {
    method: "POST",
    headers: getInviteHeaders(),
  });
  if (!res.ok) {
    let detail = "推送失败";
    try {
      const data = await res.json();
      detail = data?.detail || detail;
    } catch (e) {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}
