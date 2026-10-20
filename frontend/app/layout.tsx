import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Scout / 选品调研 Agent",
  description: "可追溯的跨境商品机会研究工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
