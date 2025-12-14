import type { Metadata } from "next";
import "../app/globals.css";

export const metadata: Metadata = {
  title: "Video2Blog Local",
  description: "本地视频转图文生成器",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <main style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 16px" }}>
          <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>Video2Blog Local</div>
              <div style={{ color: "#94a3b8", fontSize: 14 }}>视频转图文生成器 (MVP)</div>
            </div>
            <div style={{ color: "#cbd5e1", fontSize: 13 }}>状态实时轮询 · 本地上传</div>
          </header>
          {children}
        </main>
      </body>
    </html>
  );
}
