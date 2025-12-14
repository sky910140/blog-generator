"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";
import ReactMarkdown from "react-markdown";
import { fetchProject, fetchContent, updateContent, exportZip, Project, Content, resolveAssetUrl, pushWechatDraft } from "@/lib/api";

const projectFetcher = (id: string) => fetchProject(id);
const contentFetcher = (id: string) => fetchContent(id);

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;
  const { data: project, error: projectError, mutate: mutateProject } = useSWR<Project>(
    projectId ? ["project", projectId] : null,
    () => projectFetcher(projectId),
    { refreshInterval: 4000 }
  );
  const { data: content, mutate: mutateContent } = useSWR<Content>(
    projectId ? ["content", projectId] : null,
    () => contentFetcher(projectId),
    { refreshInterval: 5000 }
  );
  const [markdown, setMarkdown] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const [pushing, setPushing] = useState(false);

  useEffect(() => {
    if (content?.markdown_content) {
      setMarkdown(content.markdown_content);
    }
  }, [content?.markdown_content]);

  const handleSave = async () => {
    if (!projectId) return;
    setSaving(true);
    setMessage(null);
    try {
      await updateContent(projectId, markdown);
      mutateContent();
      setMessage("已保存");
    } catch (err: any) {
      setMessage(err.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    if (!projectId) return;
    const blob = await exportZip(projectId);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${project?.title || "export"}.zip`;
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(markdown || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      setMessage("拷贝失败，请手动全选复制");
    }
  };

  const handleWechatDraft = async () => {
    if (!projectId) return;
    setPushing(true);
    setMessage(null);
    try {
      await pushWechatDraft(projectId);
      setMessage("已推送到公众号草稿");
    } catch (err: any) {
      setMessage(err.message || "推送失败");
    } finally {
      setPushing(false);
    }
  };

  if (!projectId) return <div>未找到项目</div>;
  if (projectError) return <div>加载失败</div>;

  return (
    <div className="card">
      <Link href="/" style={{ color: "#93c5fd", fontSize: 13 }}>
        ← 返回
      </Link>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{project?.title}</div>
          <div style={{ color: "#94a3b8", fontSize: 13 }}>
            状态：{project?.status} · 进度：{project?.progress}% {project?.error_msg ? `· 错误：${project.error_msg}` : ""}
          </div>
        </div>
        <button className="btn" onClick={handleExport} disabled={!content}>
          导出 ZIP
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Markdown 编辑</div>
          <textarea
            value={markdown}
            onChange={(e) => setMarkdown(e.target.value)}
            style={{
              width: "100%",
              minHeight: 400,
              borderRadius: 8,
              background: "#0b1224",
              border: "1px solid #1f2937",
              color: "#e5e7eb",
              padding: 10,
              fontFamily: "Menlo, Monaco, 'Courier New', monospace",
            }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            <button className="btn" onClick={handleSave} disabled={saving}>
              {saving ? "保存中..." : "保存"}
            </button>
            <button className="btn" onClick={handleWechatDraft} disabled={pushing}>
              {pushing ? "推送中..." : "推送到公众号草稿"}
            </button>
            <button className="btn" onClick={handleCopy}>
              {copied ? "已复制" : "复制到公众号草稿"}
            </button>
            {message && <div style={{ color: "#a5b4fc", fontSize: 13, alignSelf: "center" }}>{message}</div>}
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 8 }}>
            时间戳语法 `[mm:ss](timestamp)` 将驱动右侧播放器跳转。
          </div>
        </div>

        <div className="card" style={{ padding: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>视频 / 预览</div>
          {project?.local_video_path ? (
            <video
              id="player"
              style={{ width: "100%", borderRadius: 12, marginBottom: 12 }}
              src={resolveAssetUrl(project.local_video_path)}
              controls
            />
          ) : (
            <div>暂无视频路径</div>
          )}
          <div style={{ background: "#0b1224", borderRadius: 8, padding: 10, minHeight: 200, border: "1px solid #1f2937" }}>
            <ReactMarkdown
              components={{
                a: ({ href, children }) => {
                  const text = children?.toString() || "";
                  if (href === "timestamp") {
                    const ts = parseTimestamp(text);
                    return (
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          if (!isNaN(ts)) {
                            const player = document.getElementById("player") as HTMLVideoElement | null;
                            if (player) {
                              player.currentTime = ts;
                              player.play();
                            }
                          }
                        }}
                        style={{ color: "#93c5fd" }}
                      >
                        [{text}]
                      </a>
                    );
                  }
                  return (
                    <a href={href} style={{ color: "#93c5fd" }}>
                      {children}
                    </a>
                  );
                },
                img: ({ src, alt }) => {
                  const resolved = resolveAssetUrl(src?.toString() || "");
                  return (
                    <img
                      src={resolved}
                      alt={alt as string}
                      style={{ maxWidth: "100%", borderRadius: 8, margin: "8px 0", cursor: "zoom-in" }}
                      onClick={() => setPreviewSrc(resolved)}
                    />
                  );
                },
              }}
            >
              {markdown || "暂无内容"}
            </ReactMarkdown>
          </div>
        </div>
      </div>

      {previewSrc && (
        <div
          onClick={() => setPreviewSrc(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            cursor: "zoom-out",
          }}
        >
          <img src={previewSrc} alt="预览" style={{ maxWidth: "90vw", maxHeight: "90vh", borderRadius: 12 }} />
        </div>
      )}
    </div>
  );
}

function parseTimestamp(label: string): number {
  const parts = label.split(":");
  if (parts.length !== 2) return NaN;
  const [m, s] = parts;
  const mi = parseInt(m, 10);
  const se = parseInt(s, 10);
  if (isNaN(mi) || isNaN(se)) return NaN;
  return mi * 60 + se;
}
