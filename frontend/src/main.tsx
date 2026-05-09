import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileText,
  PauseCircle,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

type ClaimStatus =
  | "submitted"
  | "running"
  | "awaiting_human_review"
  | "manual_handling"
  | "report_ready"
  | "failed";

type ClaimRecord = {
  claim_id: string;
  customer_id: string;
  policy_id: string;
  claim_type: "travel" | "home" | "car";
  incident_date: string;
  description: string;
  claimed_amount: number;
  uploaded_documents: { document_type: string; filename: string }[];
  status: ClaimStatus;
  created_at: string;
  updated_at: string;
};

type ClaimDetail = {
  claim: ClaimRecord;
  classification?: {
    claim_type: string;
    complexity_level: string;
    confidence: number;
    reasoning_summary: string;
  };
  policy_clauses: { clause_id: string; title: string; text: string; score: number }[];
  coverage_analysis?: {
    likely_covered: boolean;
    likely_excluded: boolean;
    uncertain: boolean;
    explanation: string;
  };
  missing_information?: { checklist: string[] };
  risk_analysis?: {
    risk_score: number;
    risk_signals: { code: string; message: string; severity: string }[];
    disclaimer: string;
  };
  timeline: { node: string; status: string; summary: string; timestamp: string }[];
  report?: {
    recommended_next_action: string;
    markdown_report: string;
    disclaimer: string;
  };
};

const seedForm = {
  claim_id: `DEMO-${Math.floor(Math.random() * 9000 + 1000)}`,
  customer_id: "CUST-1003",
  policy_id: "CAR-7001",
  claim_type: "car",
  incident_date: "2026-04-12",
  description:
    "Collision damage to the insured vehicle while parking. Front bumper and headlight need repair.",
  claimed_amount: 6400,
  uploaded_documents: "photos:car_damage_photos.zip",
};

function App() {
  const [claims, setClaims] = useState<ClaimRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [form, setForm] = useState(seedForm);
  const [reviewNotes, setReviewNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const selected = useMemo(
    () => claims.find((claim) => claim.claim_id === selectedId),
    [claims, selectedId],
  );

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
      ...options,
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }

  async function refresh(nextId = selectedId) {
    const rows = await request<ClaimRecord[]>("/claims");
    setClaims(rows);
    const id = nextId || rows[0]?.claim_id || "";
    setSelectedId(id);
    if (id) setDetail(await request<ClaimDetail>(`/claims/${id}`));
  }

  useEffect(() => {
    refresh().catch(console.error);
  }, []);

  async function submitClaim(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const uploaded_documents = form.uploaded_documents
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
        .map((item) => {
          const [document_type, filename] = item.split(":");
          return { document_type: document_type || "document", filename: filename || item };
        });
      await request("/claims", {
        method: "POST",
        body: JSON.stringify({ ...form, claimed_amount: Number(form.claimed_amount), uploaded_documents }),
      });
      await refresh(form.claim_id);
    } finally {
      setBusy(false);
    }
  }

  async function runAgent() {
    if (!selectedId) return;
    setBusy(true);
    try {
      await request(`/claims/${selectedId}/run`, { method: "POST" });
      await refresh(selectedId);
    } finally {
      setBusy(false);
    }
  }

  async function review(action: "continue" | "request_more_information" | "manual_handling") {
    if (!selectedId) return;
    setBusy(true);
    try {
      await request(`/claims/${selectedId}/review`, {
        method: "POST",
        body: JSON.stringify({ action, reviewer_id: "portfolio-reviewer", notes: reviewNotes }),
      });
      setReviewNotes("");
      await refresh(selectedId);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <h1>ClaimPilot AI</h1>
          <p>Human-in-the-loop decision support for insurance claims.</p>
        </div>
        <button onClick={() => refresh()} disabled={busy} title="Refresh claims">
          <RefreshCw size={18} /> Refresh
        </button>
      </header>

      <section className="workspace">
        <aside className="sidebar">
          <div className="panel-head">
            <h2>Claims</h2>
            <span>{claims.length}</span>
          </div>
          <div className="claim-list">
            {claims.map((claim) => (
              <button
                key={claim.claim_id}
                className={claim.claim_id === selectedId ? "claim active" : "claim"}
                onClick={() => refresh(claim.claim_id)}
              >
                <span>{claim.claim_id}</span>
                <small>{claim.claim_type} · EUR {claim.claimed_amount.toLocaleString()}</small>
                <StatusBadge status={claim.status} />
              </button>
            ))}
          </div>
        </aside>

        <section className="content">
          <ClaimForm form={form} setForm={setForm} submitClaim={submitClaim} busy={busy} />
          {selected && detail && (
            <>
              <section className="toolbar">
                <div>
                  <h2>{selected.claim_id}</h2>
                  <p>{selected.description}</p>
                </div>
                <button onClick={runAgent} disabled={busy || selected.status === "running"} title="Run LangGraph workflow">
                  <Play size={18} /> Run agent
                </button>
              </section>
              <Dashboard detail={detail} />
              {selected.status === "awaiting_human_review" && (
                <ReviewPanel notes={reviewNotes} setNotes={setReviewNotes} review={review} busy={busy} />
              )}
              <ReportPanel detail={detail} />
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function ClaimForm({ form, setForm, submitClaim, busy }: any) {
  return (
    <form className="form-band" onSubmit={submitClaim}>
      <div className="form-grid">
        <label>Claim ID<input value={form.claim_id} onChange={(e) => setForm({ ...form, claim_id: e.target.value })} /></label>
        <label>Customer<input value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} /></label>
        <label>Policy<input value={form.policy_id} onChange={(e) => setForm({ ...form, policy_id: e.target.value })} /></label>
        <label>Type<select value={form.claim_type} onChange={(e) => setForm({ ...form, claim_type: e.target.value })}><option>travel</option><option>home</option><option>car</option></select></label>
        <label>Incident date<input type="date" value={form.incident_date} onChange={(e) => setForm({ ...form, incident_date: e.target.value })} /></label>
        <label>Amount<input type="number" value={form.claimed_amount} onChange={(e) => setForm({ ...form, claimed_amount: Number(e.target.value) })} /></label>
      </div>
      <label>Description<textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
      <label>Documents<input value={form.uploaded_documents} onChange={(e) => setForm({ ...form, uploaded_documents: e.target.value })} /></label>
      <button disabled={busy} title="Submit claim"><Send size={18} /> Submit claim</button>
    </form>
  );
}

function Dashboard({ detail }: { detail: ClaimDetail }) {
  return (
    <section className="dashboard">
      <Metric icon={<ShieldCheck />} label="Confidence" value={detail.classification ? `${Math.round(detail.classification.confidence * 100)}%` : "Pending"} />
      <Metric icon={<AlertTriangle />} label="Risk score" value={detail.risk_analysis ? `${detail.risk_analysis.risk_score}/100` : "Pending"} />
      <Metric icon={<ClipboardList />} label="Missing items" value={`${detail.missing_information?.checklist.length ?? 0}`} />
      <Metric icon={<FileText />} label="Clauses" value={`${detail.policy_clauses.length}`} />
      <Timeline detail={detail} />
      <ClauseList detail={detail} />
    </section>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="metric">{icon}<span>{label}</span><strong>{value}</strong></div>;
}

function Timeline({ detail }: { detail: ClaimDetail }) {
  const fallback = ["classify_claim", "retrieve_policy", "coverage_analysis", "missing_information", "risk_signals", "human_review", "final_summary"];
  return (
    <div className="wide panel">
      <h3>Agent timeline</h3>
      <div className="timeline">
        {(detail.timeline.length ? detail.timeline : fallback.map((node) => ({ node, status: "skipped", summary: "Waiting to run.", timestamp: "" }))).map((item) => (
          <div className="step" key={`${item.node}-${item.timestamp}`}>
            {item.status === "paused" ? <PauseCircle size={18} /> : <CheckCircle2 size={18} />}
            <div><strong>{item.node.replaceAll("_", " ")}</strong><p>{item.summary}</p></div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ClauseList({ detail }: { detail: ClaimDetail }) {
  return (
    <div className="wide panel">
      <h3>Retrieved policy clauses</h3>
      <div className="clauses">
        {detail.policy_clauses.map((clause) => (
          <article key={clause.clause_id}>
            <strong>{clause.clause_id}: {clause.title}</strong>
            <p>{clause.text}</p>
          </article>
        ))}
        {!detail.policy_clauses.length && <p>No clauses retrieved yet.</p>}
      </div>
    </div>
  );
}

function ReviewPanel({ notes, setNotes, review, busy }: any) {
  return (
    <section className="review-band">
      <h2>Human review required</h2>
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Reviewer notes" />
      <div className="review-actions">
        <button disabled={busy} onClick={() => review("continue")}>Continue</button>
        <button disabled={busy} onClick={() => review("request_more_information")}>Request info</button>
        <button disabled={busy} onClick={() => review("manual_handling")}>Manual handling</button>
      </div>
    </section>
  );
}

function ReportPanel({ detail }: { detail: ClaimDetail }) {
  return (
    <section className="report panel">
      <h2>Final report</h2>
      {detail.report ? (
        <>
          <strong>{detail.report.recommended_next_action}</strong>
          <pre>{detail.report.markdown_report}</pre>
        </>
      ) : (
        <p>Run the workflow and complete review if required to generate the structured report.</p>
      )}
    </section>
  );
}

function StatusBadge({ status }: { status: ClaimStatus }) {
  return <em className={`status ${status}`}>{status.replaceAll("_", " ")}</em>;
}

createRoot(document.getElementById("root")!).render(<App />);
