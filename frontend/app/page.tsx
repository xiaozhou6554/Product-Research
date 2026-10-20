"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  IconAlertCircle,
  IconChartBar,
  IconCheck,
  IconChevronDown,
  IconClipboardList,
  IconCopy,
  IconFileText,
  IconBulb,
  IconMessageCircle,
  IconPackage,
  IconRefresh,
  IconSend,
  IconShieldCheck,
  IconSparkles,
  IconTag,
  IconTruck,
} from "@tabler/icons-react";

type Node = { status: string };
type Run = { id: string; status: string; nodes: Record<string, Node> };
type Report = {
  scope?: { data_notice: string };
  overview: { grade: string; recommendation: string };
  trend: { values: number[]; growth: number; peak_month: number };
  products: { name: string; price: number; rating: number; reviews: number; themes: string[]; url?: string | null }[];
  comments: { text: string; sentiment: string; theme: string }[];
  risks: { type: string; level: string; description: string }[];
  profit: { sale_price: number; gross_margin: number; gross_profit_cny: number; break_even_price: number };
  score: { total_score: number };
  traceability: { evidence_count: number; source_version: string; data_source?: string };
};
type ChatMessage = { role: "user" | "assistant"; text: string; citations?: string[]; mode?: string };

const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const labels: Record<string, string> = { trend: "市场概览", products: "类目穿透", comments: "评论分析", keywords: "关键词研究", suppliers: "供应商寻源", risks: "风险识别", profit: "利润测算", score: "综合评分", evidence: "证据校验", report: "报告生成" };
const nodeIcons: Record<string, typeof IconChartBar> = { trend: IconChartBar, products: IconPackage, comments: IconMessageCircle, keywords: IconTag, suppliers: IconTruck, risks: IconShieldCheck, profit: IconClipboardList, score: IconSparkles, evidence: IconFileText, report: IconBulb };

function isResearchQuestion(prompt: string) {
  return /(市场调研|市场分析|选品|市场机会|趋势|竞品|竞争格局|利润|毛利|成本|售价|盈亏平衡|供应商寻源|供应链风险|合规风险|市场规模|需求验证|关键词研究|亚马逊选品|amazon选品|帮我研究|帮我调研)/i.test(prompt);
}

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [form, setForm] = useState({ keyword: "travel organizer", market: "US", price_max: "32", depth: "standard" });
  const initialAnswerRun = useRef<string | null>(null);

  async function login() {
    const response = await fetch(`${api}/api/v1/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "researcher@example.com", password: "Research123!" }) });
    if (!response.ok) throw new Error("后端未连接，请先启动 API");
    setToken((await response.json()).access_token);
  }

  useEffect(() => { login().catch((error: Error) => setMessage(error.message)); }, []);

  useEffect(() => {
    if (!token || !run || ["SUCCEEDED", "FAILED", "CANCELLED"].includes(run.status)) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`${api}/api/v1/research-runs/${run.id}`, { headers: { Authorization: `Bearer ${token}` } });
      if (response.ok) setRun(await response.json());
    }, 700);
    return () => window.clearInterval(timer);
  }, [token, run]);

  useEffect(() => {
    if (!token || run?.status !== "SUCCEEDED") return;
    const runId = run.id;
    fetch(`${api}/api/v1/research-runs/${runId}/report`, { headers: { Authorization: `Bearer ${token}` } }).then((response) => response.json()).then(async (data) => {
      setReport(data.report);
      const initialQuestion = messages[0]?.role === "user" ? messages[0].text : "";
      if (!initialQuestion || initialAnswerRun.current === runId) return;
      initialAnswerRun.current = runId;
      setChatBusy(true);
      try {
        const answerResponse = await fetch(`${api}/api/v1/research-runs/${runId}/chat`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify({ question: initialQuestion }) });
        const answerData = await answerResponse.json();
        if (!answerResponse.ok) throw new Error(answerData.detail?.message ?? "首条问题暂时无法回答");
        setMessages((current) => current.some((item) => item.role === "assistant") ? current : [...current, { role: "assistant", text: answerData.answer, citations: answerData.citations, mode: answerData.mode }]);
      } catch (error) {
        setMessages((current) => current.some((item) => item.role === "assistant") ? current : [...current, { role: "assistant", text: (error as Error).message }]);
      } finally {
        setChatBusy(false);
      }
    });
  }, [token, run?.status, run?.id, messages[0]?.text]);

  function inferKeyword(prompt: string) {
    const match = prompt.match(/(?:研究|调研|分析|看看|了解)\s*(?:一下|关于)?\s*([^，。！？?!]+)/i);
    const candidate = match?.[1]?.trim();
    return candidate && candidate.length <= 48 ? candidate : form.keyword;
  }

  async function startResearch(prompt: string) {
    if (!token) return setMessage("后端未连接，请先启动 API");
    const keyword = inferKeyword(prompt);
    setBusy(true); setMessage(null); setReport(null);
    try {
      const response = await fetch(`${api}/api/v1/research-runs`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ ...form, keyword, price_max: Number(form.price_max) }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message ?? "创建任务失败，请检查输入");
      const detail = await fetch(`${api}/api/v1/research-runs/${data.run_id}`, { headers: { Authorization: `Bearer ${token}` } });
      setForm((current) => ({ ...current, keyword }));
      setRun(await detail.json()); setMessage("Agent 已启动调研，正在整理公开数据");
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function askQuestion(event?: FormEvent) {
    event?.preventDefault();
    if (!question.trim() || !token || (run && run.status !== "SUCCEEDED")) return;
    const asked = question.trim();
    setQuestion(""); setChatBusy(true); setMessages((current) => [...current, { role: "user", text: asked }]);
    if (!run) {
      await startResearch(asked);
      setChatBusy(false);
      return;
    }
    try {
      const response = await fetch(`${api}/api/v1/research-runs/${run.id}/chat`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify({ question: asked }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message ?? "问答暂不可用");
      setMessages((current) => [...current, { role: "assistant", text: data.answer, citations: data.citations, mode: data.mode }]);
    } catch (error) { setMessages((current) => [...current, { role: "assistant", text: (error as Error).message }]); }
    finally { setChatBusy(false); }
  }

  const nodeEntries = run ? Object.entries(run.nodes) : [];
  const completed = nodeEntries.filter(([, node]) => node.status === "SUCCEEDED").length;
  const statusText = run?.status === "SUCCEEDED" ? "分析完成" : run?.status === "RUNNING" ? "正在分析" : run?.status === "CANCELLED" ? "已取消" : "等待开始";

  return <main className="workbench">
    <header className="app-header"><div className="app-brand"><span className="brand-icon"><IconSparkles size={18} /></span><span>跨境电商选品调研 Agent</span></div><p>输入品类关键词或问题，AI 自动完成市场调研全流程</p><div className="header-actions"><span className="tenant-dot" /> tenant-a <IconChevronDown size={15} /></div></header>
    <section className="workspace">
      <div className="report-pane">
        <div className="pane-toolbar"><div><span className="eyebrow">Agent workspace</span><h1>{report ? `${form.keyword} · US 市场初筛` : "Agent智能助理"}</h1></div><span className={`status-badge ${run?.status === "SUCCEEDED" ? "success" : ""}`}><span />{statusText}</span></div>
        <section className={`assistant-dock ${report ? "expanded" : "compact"}`}><div className="assistant-head"><div className="assistant-avatar"><IconSparkles size={17} /></div><div><strong>Agent智能助理</strong><span>{report ? "基于本轮数据回答，可追溯到证据" : "直接描述商品问题，助理会完成分析"}</span></div><span className="assistant-state"><span />在线</span></div><div className="chat-body">{messages.length === 0 ? <div className="chat-empty"><IconMessageCircle size={34} /><h3>你想研究什么商品？</h3><p>例如：帮我研究 travel organizer 在美国市场的利润空间</p><div className="assistant-settings"><label><span>商品关键词</span><input value={form.keyword} onChange={(event) => setForm({ ...form, keyword: event.target.value })} placeholder="例如：wireless charger" /></label><label><span>目标售价 / USD</span><input type="number" min="1" value={form.price_max} onChange={(event) => setForm({ ...form, price_max: event.target.value })} /></label><label><span>目标市场</span><select value={form.market} disabled><option value="US">US · 美国</option></select></label><label><span>分析深度</span><select value={form.depth} onChange={(event) => setForm({ ...form, depth: event.target.value })}><option value="standard">标准调研</option><option value="enhanced">增强调研</option></select></label></div><div className="suggestions"><button type="button" onClick={() => setQuestion("帮我研究 travel organizer 在美国市场的机会")}>研究一个商品机会</button><button type="button" onClick={() => setQuestion("帮我分析这款商品的利润空间")}>分析利润空间</button><button type="button" onClick={() => setQuestion("帮我识别这款商品的主要风险")}>识别主要风险</button></div></div> : <ConversationView messages={messages} report={report} />}</div><form className="chat-form" onSubmit={askQuestion}><input value={question} onChange={(event) => setQuestion(event.target.value)} disabled={!token || Boolean(run && (!report || run.status !== "SUCCEEDED")) || chatBusy} placeholder={report ? "问问 Agent智能助理，例如：为什么推荐等级是 B？" : run ? "助理正在分析，请稍候" : "向 Agent描述你想研究的商品或问题"} /><button aria-label="发送问题" disabled={!token || !question.trim() || Boolean(run && (!report || run.status !== "SUCCEEDED")) || chatBusy}><IconSend size={18} /></button></form></section>
        {message && !run && <div className="inline-message"><IconAlertCircle size={15} />{message}</div>}
      </div>
      <aside className="process-pane"><div className="process-card"><div className="process-title"><div><span className="eyebrow">Workflow</span><h2>执行流程</h2></div><span className="process-count">{completed}/{nodeEntries.length || 10}</span></div><div className="node-list">{(nodeEntries.length ? nodeEntries : Object.keys(labels).map((key) => [key, { status: "NOT_STARTED" }] as [string, Node])).map(([key, node]) => { const Icon = nodeIcons[key] ?? IconClipboardList; return <div className={`workflow-node ${node.status.toLowerCase()}`} key={key}><span className="node-check">{node.status === "SUCCEEDED" ? <IconCheck size={14} /> : node.status === "RUNNING" ? <IconRefresh className="spin" size={14} /> : <Icon size={15} />}</span><span>{labels[key]}</span><small>{node.status === "SUCCEEDED" ? "已完成" : node.status === "RUNNING" ? "进行中" : node.status === "FAILED" ? "失败" : "待执行"}</small></div>; })}</div><div className={`process-footer ${run?.status === "SUCCEEDED" ? "ready" : ""}`}><span className="footer-check">{run?.status === "SUCCEEDED" ? <IconCheck size={13} /> : <IconRefresh className={run ? "spin" : ""} size={13} />}</span>{run?.status === "SUCCEEDED" ? "分析完成，可以开始问答" : run ? "节点正在运行" : "等待启动调研"}</div></div><div className="source-note"><IconFileText size={16} /><div><strong>数据边界</strong><p>固定 fixture、公开数据和 synthetic 供应链假设。搜索兴趣不等于销量。</p></div></div></aside>
    </section>
    <footer className="app-footer"><span>Scout workspace · fixture-2026.10.13</span><span>所有关键数字均可追溯至计算结果或证据</span></footer>
  </main>;
}

function ReportContent({ report, trendMax }: { report: Report; trendMax: number }) {
  return <div className="report-content"><div className="report-hero"><div><span className="eyebrow">Decision brief</span><h2>{report.overview.recommendation}</h2><p>推荐等级 <b>{report.overview.grade}</b> · 综合评分 {report.score.total_score}</p></div><div className="grade">{report.overview.grade}</div></div><div className="metrics"><div><span>预估毛利率</span><strong>{Math.round(report.profit.gross_margin * 100)}%</strong><small>含广告、退货与税费</small></div><div><span>毛利 / 单</span><strong>{report.profit.gross_profit_cny.toFixed(0)} <em>CNY</em></strong><small>按 ${report.profit.sale_price} 售价</small></div><div><span>盈亏平衡售价</span><strong>${report.profit.break_even_price}</strong><small>目标售价上限内</small></div></div><section className="report-section"><div className="section-heading"><div><span className="eyebrow">01 / Demand signal</span><h3>趋势分析</h3></div><span className="trend-up">↗ {Math.round(report.trend.growth * 100)}% 增长</span></div><div className="chart"><div className="chart-grid"><span /><span /><span /></div><div className="bars">{report.trend.values.map((value, index) => <i key={index} style={{ height: `${Math.max(10, value / trendMax * 100)}%` }} className={index === report.trend.values.length - 1 ? "highlight" : ""} />)}</div></div><div className="chart-labels"><span>近 12 个月搜索兴趣</span><span>峰值：{report.trend.peak_month} 月</span></div></section><section className="report-section"><div className="section-heading"><div><span className="eyebrow">02 / Competitive set</span><h3>商品与竞品</h3></div><span className="muted-label">{report.products.length} 个候选</span></div><div className="product-table">{report.products.map((product) => <div className="product-row" key={product.name}><div className="product-thumb"><IconPackage size={17} /></div><div className="product-name"><strong>{product.name}</strong><span>{product.themes.join(" · ")}</span></div><b>${product.price}</b><span className="rating">{product.rating > 0 ? `★ ${product.rating}` : "暂无评分"}</span><span className="reviews">{product.reviews > 0 ? `${product.reviews.toLocaleString()} 条评论` : "平台未提供评论"}</span></div>)}</div></section><section className="report-section compact"><div className="section-heading"><div><span className="eyebrow">03 / Evidence note</span><h3>用户痛点</h3></div><span className="muted-label">{report.traceability.evidence_count} 条证据</span></div>{report.comments.slice(0, 2).map((comment) => <div className="comment-row" key={comment.text}><IconMessageCircle size={16} /><span>{comment.text}</span><em>{comment.theme}</em></div>)}</section><div className="report-footnote"><IconFileText size={14} /> {report.scope?.data_notice ?? `数据版本 ${report.traceability.source_version}，供应商成本等为 synthetic 假设。`}</div></div>;
}

function ConversationView({ messages, report }: { messages: ChatMessage[]; report: Report | null }) {
  const turns: { question: ChatMessage; answer?: ChatMessage }[] = [];
  for (let index = 0; index < messages.length; index += 1) {
    const question = messages[index];
    if (question.role !== "user") continue;
    turns.push({ question, answer: messages[index + 1]?.role === "assistant" ? messages[index + 1] : undefined });
  }
  return <div className="conversation">{turns.map((turn, index) => <section className="conversation-turn" key={`${turn.question.text}-${index}`}><ChatMessageView item={turn.question} index={index * 2} />{turn.answer && <ChatMessageView item={turn.answer} index={index * 2 + 1} />}{turn.answer && report && isResearchQuestion(turn.question.text) && <AssistantReport report={report} question={turn.question.text} />}</section>)}</div>;
}

function ChatMessageView({ item, index }: { item: ChatMessage; index: number }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await copyText(item.text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return <div className={`chat-message ${item.role}`} data-message-index={index}><div className="message-avatar">{item.role === "assistant" ? <IconSparkles size={14} /> : "我"}</div><div className="message-content">{item.role === "assistant" && <div className="message-label">回答<button type="button" className="copy-button" onClick={handleCopy} aria-label="复制回答" title="复制回答">{copied ? <IconCheck size={13} /> : <IconCopy size={13} />}{copied ? "已复制" : "复制"}</button></div>}{item.role === "assistant" ? <div className="answer-content">{formatAssistantText(item.text)}</div> : <p>{item.text}</p>}</div></div>;
}

function formatAssistantText(text: string) {
  const cleanedText = text.replace(/(^|\n)\s*#{1,6}\s*(依据|证据|假设|验证建议|下一步)(?:\s*[:：])?\s*/gi, "$1").replace(/^\s*(依据|证据|假设|验证建议|下一步)\s*[:：]\s*/gim, "").replace(/\*\*(依据|证据|假设|验证建议|下一步)\*\*/gi, "").replace(/\*\*(.*?)\*\*/g, "$1");
  const normalized = cleanedText.replace(/\r/g, "").replace(/\s+(?=#{1,6}\s)/g, "\n").replace(/\s+(?=\d+[.)]\s)/g, "\n").replace(/\s+(?=[-*]\s)/g, "\n");
  const lines = normalized.split("\n").map((line) => line.trim()).filter(Boolean);
  const structured = lines.some((line) => /^#{1,6}\s+/.test(line) || /^\d+[.)]\s+/.test(line) || /^[-*]\s+/.test(line));
  if (!structured) {
    const sentences = normalized.split(/(?<=[。！？!?；;])\s*/).map((line) => line.trim()).filter(Boolean);
    return sentences.map((sentence, index) => <div className="answer-item" key={index}><b>{index + 1}</b><span>{sentence}</span></div>);
  }
  return lines.map((line, index) => {
    const value = line.replace(/\*\*(.*?)\*\*/g, "$1").trim();
    if (!value) return null;
    if (/^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$/.test(value)) return null;
    const heading = value.match(/^#{1,6}\s+(.+)/);
    if (heading) return <h4 key={index}>{heading[1]}</h4>;
    const ordered = value.match(/^(\d+)[.)]\s+(.+)/);
    if (ordered) return <div className="answer-item" key={index}><b>{ordered[1]}</b><span>{ordered[2]}</span></div>;
    const bullet = value.match(/^[-*]\s+(.+)/);
    if (bullet) return <div className="answer-bullet" key={index}><span>•</span>{bullet[1]}</div>;
    if (value.includes("|") && value.trim().startsWith("|")) return <div className="answer-table-row" key={index}>{value.split("|").map((cell) => cell.trim()).filter(Boolean).map((cell, cellIndex) => <span key={cellIndex}>{cell}</span>)}</div>;
    return <p key={index}>{value}</p>;
  });
}

function copyText(text: string) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
  return Promise.resolve();
}

function buildReportText(report: Report) {
  return [
    report.overview.recommendation,
    `推荐等级 ${report.overview.grade}，综合评分 ${report.score.total_score}`,
    `预估毛利率 ${Math.round(report.profit.gross_margin * 100)}%` ,
    `毛利 / 单 ${report.profit.gross_profit_cny.toFixed(0)} CNY`,
    `盈亏平衡售价 $${report.profit.break_even_price}`,
    `趋势增长 ${Math.round(report.trend.growth * 100)}%`,
    "商品与竞品：",
    ...report.products.map((product) => `${product.name}，$${product.price}，${product.rating > 0 ? `评分 ${product.rating}` : "平台未提供商品评分"}，${product.reviews > 0 ? `${product.reviews} 条评论` : "平台未提供评论"}`),
    "用户痛点：",
    ...report.comments.map((comment) => `${comment.text}（${comment.theme}）`),
  ].join("\n");
}

type ReportFocus = "all" | "trend" | "products" | "comments" | "profit" | "risks";

function getReportFocus(question: string): ReportFocus {
  if (/(评论|痛点|反馈|拉链|隔层|收纳)/i.test(question)) return "comments";
  if (/(利润|毛利|成本|售价|盈亏)/i.test(question)) return "profit";
  if (/(竞品|竞争|商品对比|对手)/i.test(question)) return "products";
  if (/(风险|合规|物流|供应链|退货)/i.test(question)) return "risks";
  if (/(趋势|需求|搜索|增长|关键词)/i.test(question)) return "trend";
  return "all";
}

function FocusedReport({ report, focus }: { report: Report; focus: Exclude<ReportFocus, "all"> }) {
  const trendMax = Math.max(...report.trend.values);
  if (focus === "profit") return <div className="focused-report"><div className="metrics"><div><span>预估毛利率</span><strong>{Math.round(report.profit.gross_margin * 100)}%</strong><small>含广告、退货与税费</small></div><div><span>毛利 / 单</span><strong>{report.profit.gross_profit_cny.toFixed(0)} <em>CNY</em></strong><small>按 ${report.profit.sale_price} 售价</small></div><div><span>盈亏平衡售价</span><strong>${report.profit.break_even_price}</strong><small>目标售价上限内</small></div></div></div>;
  if (focus === "trend") return <div className="focused-report"><div className="section-heading"><div><h3>趋势分析</h3></div><span className="trend-up">↗ {Math.round(report.trend.growth * 100)}% 增长</span></div><div className="chart"><div className="chart-grid"><span /><span /><span /></div><div className="bars">{report.trend.values.map((value, index) => <i key={index} style={{ height: `${Math.max(10, value / trendMax * 100)}%` }} className={index === report.trend.values.length - 1 ? "highlight" : ""} />)}</div></div><div className="chart-labels"><span>近 12 个月搜索兴趣</span><span>峰值：{report.trend.peak_month} 月</span></div></div>;
  if (focus === "products") return <div className="focused-report"><div className="section-heading"><div><h3>商品与竞品</h3></div><span className="muted-label">{report.products.length} 个候选</span></div><div className="product-table">{report.products.map((product) => <div className="product-row" key={product.name}><div className="product-thumb"><IconPackage size={17} /></div><div className="product-name"><strong>{product.name}</strong><span>{product.themes.join(" · ")}</span></div><b>${product.price}</b><span className="rating">{product.rating > 0 ? `★ ${product.rating}` : "暂无评分"}</span><span className="reviews">{product.reviews > 0 ? `${product.reviews.toLocaleString()} 条评论` : "平台未提供评论"}</span></div>)}</div></div>;
  if (focus === "comments") return <div className="focused-report"><div className="section-heading"><div><h3>用户痛点</h3></div><span className="muted-label">{report.comments.length} 条评论证据</span></div>{report.comments.map((comment) => <div className="comment-row" key={comment.text}><IconMessageCircle size={16} /><span>{comment.text}</span><em>{comment.theme}</em></div>)}</div>;
  return <div className="focused-report"><div className="section-heading"><div><h3>风险与验证建议</h3></div><span className="muted-label">{report.risks.length} 项风险</span></div>{report.risks.map((risk) => <div className="comment-row" key={risk.type}><IconShieldCheck size={16} /><span>{risk.description}</span><em>{risk.level}</em></div>)}</div>;
}

function AssistantReport({ report, question }: { report: Report; question: string }) {
  const trendMax = Math.max(...report.trend.values);
  const focus = getReportFocus(question);
  const [copied, setCopied] = useState(false);
  if (focus !== "all") return null;
  async function handleCopy() {
    try {
      await copyText(buildReportText(report));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }
  return <div className="assistant-report-full"><div className="report-toolbar"><button type="button" className="copy-button" onClick={handleCopy}>{copied ? <IconCheck size={13} /> : <IconCopy size={13} />}{copied ? "已复制" : "复制"}</button></div>{focus === "all" ? <ReportContent report={report} trendMax={trendMax} /> : <FocusedReport report={report} focus={focus} />}</div>;
}
