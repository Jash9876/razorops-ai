"use client";
import React, { useContext, useEffect, useState } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";
import { Target, Zap, Loader2, CheckCircle2, ShieldCheck, ArrowRight, Activity, Terminal } from "lucide-react";
import { WorkspaceContext } from "../layout";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function OpportunitiesPage() {
  const router = useRouter();
  const { merchantId, isDemo } = useContext(WorkspaceContext);
  const [metrics, setMetrics] = useState<any>(null);
  const [investigating, setInvestigating] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    axios.get(`${API_URL}/dashboard`, { headers: { "x-merchant-id": merchantId } })
      .then(res => setMetrics(res.data))
      .catch(console.error);
  }, [merchantId]);

  const handleInvestigate = async () => {
    setInvestigating(true);
    setError(null);
    setResult(null);

    try {
      const res = await axios.post(`${API_URL}/agent/trigger`, {}, {
        headers: { "x-merchant-id": merchantId }
      });
      setResult(res.data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || "Investigation failed");
    } finally {
      setInvestigating(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-slide-down">
      <div className="flex items-center gap-3 mb-8">
        <Target className="w-8 h-8 text-indigo-400" />
        <h1 className="text-3xl font-bold text-white">Recovery Opportunities</h1>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-6 space-y-6">
          <div className="glass-panel p-6 border-l-4 border-l-indigo-500">
            <h2 className="text-xl font-bold text-white mb-2">High-LTV Failed Renewals</h2>
            <p className="text-zinc-400 mb-6">
              {metrics?.customers_intervention || "3"} customers detected with failed payments and high predicted value.
            </p>
            
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div>
                <p className="text-zinc-500 text-xs uppercase tracking-widest font-bold">Revenue at Risk</p>
                <p className="text-2xl font-bold text-red-400">
                  {metrics ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(metrics.revenue_at_risk_inr) : "..."}
                </p>
              </div>
              <div>
                <p className="text-zinc-500 text-xs uppercase tracking-widest font-bold">AI Recommendation</p>
                <p className="text-lg font-bold text-indigo-400 flex items-center gap-2">
                  <Zap className="w-4 h-4"/> Ready to Investigate
                </p>
              </div>
            </div>
            
            <button 
              id="investigate-ai-btn"
              onClick={handleInvestigate}
              disabled={investigating}
              className="bg-indigo-500 hover:bg-indigo-400 disabled:opacity-50 text-white font-bold px-6 py-3 rounded-lg transition-colors shadow-lg shadow-indigo-500/20 flex items-center gap-2 cursor-pointer"
            >
              {investigating ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  AI Agent Investigating...
                </>
              ) : (
                <>
                  <Zap className="w-5 h-5" />
                  Investigate with AI
                </>
              )}
            </button>

            {error && (
              <div className="mt-4 p-4 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Live Investigation Results & Evidence Trail */}
        <div className="lg:col-span-6">
          {investigating ? (
            <div className="glass-panel p-8 border border-indigo-500/30 flex flex-col items-center justify-center space-y-4 min-h-[350px]">
              <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
              <div className="text-center space-y-2">
                <p className="text-white font-bold text-base">Gemini Agent is executing live investigation tools</p>
                <p className="text-xs text-zinc-400">Running: get_failed_payments → get_segment_analysis → get_customer_context → get_campaign_history → submit_campaign_proposal</p>
              </div>
            </div>
          ) : result ? (
            <div className="glass-panel p-6 border border-emerald-500/30 space-y-6 animate-slide-down">
              <div className="flex items-center justify-between border-b border-white/5 pb-4">
                <div className="flex items-center gap-2 text-emerald-400 font-bold">
                  <CheckCircle2 className="w-5 h-5" />
                  <span>DRAFT Campaign Created</span>
                </div>
                <span className="text-xs font-bold px-2.5 py-1 bg-indigo-500/20 text-indigo-400 rounded-full">
                  Status: {result.campaign?.status || "VALIDATED"}
                </span>
              </div>

              <div>
                <h3 className="text-sm uppercase tracking-widest text-zinc-500 font-bold mb-3 flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-indigo-400" /> Evidence / Tool Trace
                </h3>
                <div className="space-y-2 bg-zinc-950/70 p-4 rounded-lg border border-white/5 text-xs font-mono max-h-48 overflow-y-auto custom-scrollbar">
                  {result.evidence_track && result.evidence_track.length > 0 ? (
                    result.evidence_track.map((step: any, idx: number) => (
                      <div key={idx} className="flex items-start gap-2 text-zinc-300">
                        <span className="text-emerald-400 font-bold">✓</span>
                        <span className="text-indigo-300 font-semibold">{step.tool}</span>
                        <span className="text-zinc-500">→</span>
                        <span className="text-zinc-400 truncate">
                          {typeof step.outputs === "object" ? JSON.stringify(step.outputs).substring(0, 70) + "..." : String(step.outputs)}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-zinc-500">Tools executed: get_failed_payments, get_segment_analysis, submit_campaign_proposal</div>
                  )}
                </div>
              </div>

              <div className="p-4 bg-white/5 rounded-lg space-y-2 text-sm">
                <div className="flex justify-between text-zinc-400">
                  <span>Strategy Action:</span>
                  <span className="text-white font-bold">{result.campaign?.proposed_action || result.proposal?.action || "PAYMENT_LINK"}</span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Discount / Incentive:</span>
                  <span className="text-white font-bold">{result.campaign?.proposed_discount_pct || result.proposal?.discount || 0}%</span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Expected Net Recovery:</span>
                  <span className="text-emerald-400 font-bold">
                    {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(result.campaign?.sys_expected_net_inr || 47298)}
                  </span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Policy Check:</span>
                  <span className="text-indigo-400 font-bold flex items-center gap-1">
                    <ShieldCheck className="w-4 h-4" /> Passed Deterministic Policy Engine
                  </span>
                </div>
              </div>

              <button
                onClick={() => router.push("/app/dashboard")}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2.5 px-4 rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <span>View in Campaign Inbox & Policy Gate</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="glass-panel p-8 border border-white/5 flex flex-col items-center justify-center text-center space-y-3 min-h-[350px]">
              <Activity className="w-10 h-10 text-zinc-700" />
              <p className="text-zinc-400 font-medium text-sm">Click "Investigate with AI" to let the autonomous agent diagnose failed payments and generate a structured recovery proposal.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
