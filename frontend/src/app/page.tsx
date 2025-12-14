"use client";

import React, { useCallback, useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { uploadProject, fetchProjects, Project, setInviteCodeCache } from "@/lib/api";

export default function DashboardPage() {
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [inviteCode, setInviteCode] = useState("");
  const [validated, setValidated] = useState(false);

  const fetcher = () => fetchProjects();
  const { data, error, mutate, isLoading } = useSWR(validated ? "projects" : null, fetcher, {
    refreshInterval: 4000,
  });

  const verifyInvite = useCallback(async (codeFromInput?: string) => {
    if (typeof window === "undefined") return false;
    const code = (codeFromInput ?? inviteCode).trim();
    if (!code) {
      setMessage("请输入邀请码");
      setValidated(false);
      return false;
    }
    setInviteCodeCache(code);
    setMessage("校验中...");
    try {
      await fetchProjects();
      setValidated(true);
      if (typeof sessionStorage !== "undefined") sessionStorage.setItem("inviteValidated", "1");
      setMessage("邀请码验证通过");
      return true;
    } catch (err: any) {
      const status = (err as any)?.status;
      if (status === 403) {
        setValidated(false);
        setInviteCodeCache("");
        if (typeof sessionStorage !== "undefined") sessionStorage.removeItem("inviteValidated");
        setMessage(err?.message || "邀请码无效或已用尽");
      } else {
        // 对于其他错误（网络/服务器），保留邀请码，提示稍后再试
        setMessage(err?.message || "服务暂不可用，请稍后再试");
      }
      return false;
    }
  }, [inviteCode]);

  const handleInviteSave = useCallback(() => {
    void verifyInvite();
  }, [verifyInvite]);

  // 读取本地邀请码并自动校验（仅初始化运行，避免输入时被重置）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = (typeof sessionStorage !== "undefined" && sessionStorage.getItem("inviteCode")) || "";
    const validatedFlag = (typeof sessionStorage !== "undefined" && sessionStorage.getItem("inviteValidated")) === "1";
    if (stored) {
      setInviteCode(stored);
      setInviteCodeCache(stored);
      if (validatedFlag) {
        setValidated(true);
      } else {
        void (async () => {
          await verifyInvite(stored);
        })();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUpload = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const storedCode = (typeof sessionStorage !== "undefined" && sessionStorage.getItem("inviteCode")) || "";
      const flag = (typeof sessionStorage !== "undefined" && sessionStorage.getItem("inviteValidated")) === "1";
      let validatedNow = validated;
      if (flag && storedCode) {
        setInviteCode(storedCode);
        setInviteCodeCache(storedCode);
        setValidated(true);
        validatedNow = true;
      }
      if (!validatedNow) {
        const ok = await verifyInvite();
        if (!ok) {
          setMessage("请先通过邀请码登录");
          event.target.value = "";
          return;
        } else {
          validatedNow = true;
        }
      }
      setUploading(true);
      setMessage(null);
      try {
        await uploadProject(file);
        await mutate();
        setMessage("上传成功，任务已创建");
      } catch (err: any) {
        setMessage(err.message || "上传失败");
      } finally {
        setUploading(false);
        event.target.value = "";
      }
    },
    [mutate]
  );

  if (!validated) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "48px 16px",
          background: "radial-gradient(circle at 20% 20%, rgba(96,165,250,0.2), transparent 35%), radial-gradient(circle at 80% 0%, rgba(52,211,153,0.2), transparent 25%), #0b1220",
          color: "#e2e8f0",
        }}
      >
        <div
          style={{
            maxWidth: 680,
            width: "100%",
            background: "rgba(15,23,42,0.85)",
            border: "1px solid rgba(148,163,184,0.2)",
            boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
            borderRadius: 18,
            padding: "32px 28px",
          }}
        >
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-0.02em", color: "#e5e7eb" }}>Video2Blog Local</div>
            <div style={{ marginTop: 8, fontSize: 16, color: "#cbd5e1" }}>
              把视频的关键步骤和截图，一键变成可编辑的教程草稿——专注清晰、快速、私密。
            </div>
          </div>
          <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
            <label style={{ fontSize: 14, color: "#cbd5e1" }}>输入邀请码进入</label>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <input
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                placeholder="请输入邀请码"
                style={{
                  flex: "1 1 220px",
                  padding: "12px 14px",
                  borderRadius: 10,
                  border: "1px solid #1e293b",
                  background: "#0f172a",
                  color: "#e2e8f0",
                  fontSize: 15,
                }}
              />
              <button
                className="btn"
                type="button"
                onClick={handleInviteSave}
                style={{ padding: "12px 18px", borderRadius: 10, fontWeight: 700 }}
              >
                进入
              </button>
            </div>
            {message && <div style={{ color: "#93c5fd", fontSize: 13 }}>{message}</div>}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 18 }}>任务列表</div>
          <div style={{ color: "#94a3b8", fontSize: 13 }}>视频仅支持本地上传，时长 &lt; 60 分钟</div>
        </div>
        <label className="btn" style={{ display: "inline-block" }}>
          {uploading ? "上传中..." : "上传视频"}
          <input type="file" accept=".mp4,.mov" style={{ display: "none" }} onChange={handleUpload} disabled={uploading} />
        </label>
      </div>
      {message && <div style={{ marginTop: 8, color: "#fcd34d", fontSize: 13 }}>{message}</div>}
      {error && <div style={{ color: "#f87171", marginTop: 8 }}>加载失败：{error.message}</div>}
      <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
        {isLoading && <div>加载中...</div>}
        {data?.map((project: Project) => (
          <div key={project.id} className="card" style={{ padding: 14 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{project.title}</div>
            <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 6 }}>{project.source_type}</div>
            <div style={{ height: 6, background: "#1f2937", borderRadius: 6, overflow: "hidden", marginBottom: 6 }}>
              <div
                style={{
                  width: `${project.progress}%`,
                  height: "100%",
                  background: project.status === "failed" ? "#f87171" : "#22c55e",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <div style={{ fontSize: 13, color: "#cbd5e1", marginBottom: 6 }}>
              状态：{project.status} · 进度：{project.progress}%
            </div>
            {project.error_msg && <div style={{ color: "#f87171", fontSize: 12 }}>{project.error_msg}</div>}
            <Link href={`/projects/${project.id}`} style={{ color: "#93c5fd", fontWeight: 600, fontSize: 14 }}>
              查看详情 →
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
