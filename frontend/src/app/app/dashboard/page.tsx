"use client";

import React, { useState, useEffect, useContext } from "react";
import axios from "axios";
import { CheckCircle, Clock, CheckSquare, Zap, AlertCircle, ChevronRight, Activity, ExternalLink, ShieldCheck, ArrowRight } from "lucide-react";
import { WorkspaceContext } from "../layout";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function RazorOpsDashboard() {
  const { merchantId, isDemo } = useContext(WorkspaceContext);
  
  // Setup generic axios instance dynamically based on context
  const api = axios.create({
    baseURL: API_URL,
    headers: { "x-merchant-id": merchantId }
  });
  const [metrics, setMetrics] = useState<any>(null);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<any>(null);
  const [targets, setTargets] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    fetchDashboard();
    fetchCampaigns();
  }, [merchantId]);

  const fetchDashboard = async () => {
    try {
      const res = await api.get("/dashboard");
      setMetrics(res.data);
    } catch (e) { console.error("Failed to fetch dashboard", e); }
  };

  const fetchCampaigns = async () => {
    try {
      const res = await api.get("/campaigns");
      setCampaigns(res.data);
    } catch (e) { console.error("Failed to fetch campaigns", e); }
  };

  const selectCampaign = async (c: any) => {
    setSelectedCampaign(c);
    setLoading(true);
    try {
      const res = await api.get(`/campaigns/${c.id}/targets`);
      setTargets(res.data);
    } catch (e) { console.error("Failed to fetch targets", e); }
    setLoading(false);
  };

  const formatINR = (amountInr: number) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amountInr);
  };
  
  const formatPaiseToINR = (paise: number) => {
    return formatINR((paise || 0) / 100);
  };

  // Poll for updates if campaign is executing or active
  useEffect(() => {
    let interval: any;
    if (selectedCampaign && ['EXECUTING', 'ACTIVE', 'PARTIAL_FAILURE'].includes(selectedCampaign.status)) {
      interval = setInterval(async () => {
        const res = await api.get(`/campaigns/${selectedCampaign.id}`);
        setSelectedCampaign(res.data);
        const tres = await api.get(`/campaigns/${selectedCampaign.id}/targets`);
        setTargets(tres.data);
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [selectedCampaign]);

  const handleApprove = async () => {
    try {
      await api.post(`/campaigns/${selectedCampaign.id}/approve`);
      // Re-fetch
      const res = await api.get(`/campaigns/${selectedCampaign.id}`);
      setSelectedCampaign(res.data);
      fetchCampaigns();
    } catch (e: any) {
      alert("Approval failed: " + (e.response?.data?.detail || e.message));
    }
  };

  const handleExecute = async () => {
    try {
      await api.post(`/campaigns/${selectedCampaign.id}/execute`);
      const res = await api.get(`/campaigns/${selectedCampaign.id}`);
      setSelectedCampaign(res.data);
      fetchCampaigns();
    } catch (e: any) {
      alert("Execution failed: " + (e.response?.data?.detail || e.message));
    }
  };

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto space-y-8 animate-slide-down text-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Overview</h1>
          <p className="text-zinc-400">RazorOps analyzed {isDemo ? "the sample" : "your"} payment data.</p>
        </div>
      </div>

      {/* Global Metrics Ribbon */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-6 flex flex-col justify-center">
          <p className="text-zinc-400 mb-1 font-medium text-xs tracking-widest uppercase">At-Risk Customer LTV</p>
          <p className="text-3xl font-bold text-white">{metrics ? formatINR(metrics.revenue_at_risk_inr) : "..."}</p>
        </div>
        <div className="glass-panel p-6 flex flex-col justify-center border-emerald-500/30">
          <p className="text-emerald-400/80 mb-1 font-medium text-xs tracking-widest uppercase">Expected Net Recovery</p>
          <p className="text-3xl font-bold text-emerald-400">{metrics ? formatINR(metrics.expected_recovery_inr) : "..."}</p>
        </div>
        <div className="glass-panel p-6 flex flex-col justify-center">
          <p className="text-zinc-400 mb-1 font-medium text-xs tracking-widest uppercase">Customers</p>
          <p className="text-3xl font-bold text-white">{metrics ? metrics.customers_intervention : "..."} awaiting action</p>
        </div>
      </div>

      {/* Main Content Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Col: Inbox */}
        <div className="lg:col-span-4 space-y-4">
          <h2 className="text-lg font-bold text-zinc-200">Campaign Inbox</h2>
          <div className="space-y-3">
            {campaigns.map(c => (
              <div 
                key={c.id} 
                onClick={() => selectCampaign(c)}
                className={`glass-panel p-5 cursor-pointer transition-all hover:bg-white/5 ${selectedCampaign?.id === c.id ? 'border-indigo-500 bg-indigo-500/5' : ''}`}
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-white">{c.segment_name || "Campaign"}</h3>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold tracking-widest uppercase ${
                    c.status === 'VALIDATED' ? 'bg-indigo-500/20 text-indigo-400' :
                    c.status === 'APPROVED' ? 'bg-orange-500/20 text-orange-400' :
                    ['ACTIVE', 'COMPLETED'].includes(c.status) ? 'bg-emerald-500/20 text-emerald-400' :
                    'bg-zinc-800 text-zinc-400'
                  }`}>
                    {c.status}
                  </span>
                </div>
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>Net Expected: <span className="text-emerald-400 font-medium">{formatINR(c.sys_expected_net_inr)}</span></span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Col: Pipeline */}
        <div className="lg:col-span-8">
          {loading ? (
            <div className="glass-panel p-12 text-center text-zinc-500">Loading...</div>
          ) : selectedCampaign ? (
            <CampaignPipeline 
              campaign={selectedCampaign} 
              targets={targets} 
              onApprove={handleApprove}
              onExecute={handleExecute}
              formatINR={formatINR}
              formatPaiseToINR={formatPaiseToINR}
              isDemo={isDemo}
            />
          ) : (
            <div className="glass-panel p-12 text-center flex flex-col items-center justify-center min-h-[400px]">
              <Activity className="w-12 h-12 text-zinc-700 mb-4" />
              <p className="text-zinc-500">Select a campaign to review the recovery pipeline.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CampaignPipeline({ campaign, targets, onApprove, onExecute, formatINR, formatPaiseToINR, isDemo }: any) {
  
  // Pipeline status computation
  const status = campaign.status;
  const isApproved = ['APPROVED', 'EXECUTING', 'ACTIVE', 'COMPLETED', 'PARTIAL_FAILURE'].includes(status);
  const isExecuting = ['EXECUTING'].includes(status);
  const isExecuted = ['ACTIVE', 'COMPLETED', 'PARTIAL_FAILURE'].includes(status);
  const isRejected = ['REJECTED'].includes(status);
  
  let evidence = null;
  try { evidence = JSON.parse(campaign.agent_evidence); } catch(e) {}
  
  let policyResult = null;
  try { policyResult = JSON.parse(campaign.policy_result_json); } catch(e) {}

  const targetCount = targets.length;
  const linksGenerated = targets.filter((t: any) => ['LINK_GENERATED', 'PAID'].includes(t.status)).length;
  const linksFailed = targets.filter((t: any) => t.status === 'FAILED_TO_GENERATE').length;
  
  const paidCount = targets.filter((t: any) => t.recovery_status === 'PAID').length;
  const actualRecoveryPaise = targets.reduce((sum: number, t: any) => sum + (t.amount_recovered_paise || 0), 0);

  return (
    <div className="space-y-6">
      
      {/* Visual Pipeline Bar */}
      <div className="glass-panel p-4 flex justify-between items-center text-xs font-bold tracking-widest text-zinc-500 uppercase overflow-hidden">
        <div className="flex gap-2 items-center text-indigo-400"><CheckCircle className="w-4 h-4"/> Detect</div>
        <div className="h-px bg-zinc-800 flex-1 mx-4"></div>
        <div className="flex gap-2 items-center text-indigo-400"><CheckCircle className="w-4 h-4"/> Investigate</div>
        <div className="h-px bg-zinc-800 flex-1 mx-4"></div>
        <div className="flex gap-2 items-center text-indigo-400"><CheckCircle className="w-4 h-4"/> Decide</div>
        <div className="h-px bg-zinc-800 flex-1 mx-4"></div>
        <div className="flex gap-2 items-center text-indigo-400"><ShieldCheck className="w-4 h-4"/> Policy</div>
        <div className="h-px bg-zinc-800 flex-1 mx-4"></div>
        <div className={`flex gap-2 items-center ${isApproved ? 'text-indigo-400' : isRejected ? 'text-red-400' : ''}`}>
          {isApproved ? <CheckCircle className="w-4 h-4"/> : isRejected ? <AlertCircle className="w-4 h-4"/> : <div className="w-4 h-4 rounded-full border-2 border-current"/>} Approve
        </div>
        <div className="h-px bg-zinc-800 flex-1 mx-4"></div>
        <div className={`flex gap-2 items-center ${isExecuted ? 'text-emerald-400' : ''}`}>
          {isExecuted ? <CheckCircle className="w-4 h-4"/> : <div className="w-4 h-4 rounded-full border-2 border-current"/>} Execute
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        <div className="glass-panel p-6 space-y-4 border-l-4 border-l-indigo-500">
          <h3 className="font-bold text-white mb-4">DECISION EVIDENCE</h3>
          
          {evidence && Array.isArray(evidence) ? (
            <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {evidence.map((step: any, idx: number) => {
                if (step.tool === "submit_campaign_proposal") return null;
                
                let summary = "";
                let subtext = "";
                if (step.tool === "get_failed_payments") {
                  summary = `${step.outputs.failed_attempts} failures · ₹${step.outputs.amount_at_risk_inr} at risk`;
                  subtext = `Dominant failure: ${Object.keys(step.outputs.error_distribution || {})[0] || 'unknown'}`;
                } else if (step.tool === "get_segment_analysis") {
                  summary = `${step.outputs.customer_count} customers identified`;
                  subtext = `Avg churn risk: ${step.outputs.average_churn_risk}`;
                } else if (step.tool === "get_campaign_history") {
                  summary = "Historical metrics evaluated";
                  subtext = step.outputs.note || "No historical campaigns";
                } else if (step.tool === "get_customer_context") {
                  summary = "Customer context analyzed";
                }
                
                return (
                  <div key={idx} className="flex flex-col text-zinc-300 bg-black/30 p-3 rounded-lg border border-white/5">
                    <p className="text-[10px] text-indigo-400 font-bold uppercase tracking-widest mb-1">
                      0{idx+1} {step.tool.replace(/_/g, ' ')}
                    </p>
                    <p className="text-sm">{summary}</p>
                    {subtext && <p className="text-xs text-zinc-500 mt-1">{subtext}</p>}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-zinc-500">No evidence trail available.</p>
          )}
        </div>

        {/* Right Box: Recommendation */}
        <div className="glass-panel p-6 border-l-4 border-l-indigo-500">
          <h3 className="font-bold text-white mb-4">RECOMMENDATION</h3>
          <div className="text-lg font-bold text-indigo-400 mb-4">{campaign.segment_name} Recovery</div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-zinc-500 text-xs">Targets</p>
              <p className="text-xl font-bold text-white">{targetCount}</p>
            </div>
            <div>
              <p className="text-zinc-500 text-xs">Expected Gross</p>
              <p className="text-xl font-bold text-white">{formatINR(campaign.sys_expected_gross_inr)}</p>
            </div>
            <div>
              <p className="text-zinc-500 text-xs">Intervention Cost</p>
              <p className="text-xl font-bold text-red-400">-{formatINR(campaign.sys_expected_cost_inr)}</p>
            </div>
            <div>
              <p className="text-zinc-500 text-xs">Expected Net</p>
              <p className="text-xl font-bold text-emerald-400">{formatINR(campaign.sys_expected_net_inr)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Full width box: Policy Engine */}
      <div className="glass-panel p-6 border-l-4 border-l-emerald-500">
        <h3 className="font-bold text-white mb-4 flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-emerald-400"/> POLICY CHECK</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-zinc-300">
          {policyResult ? policyResult.checks.map((check: any, idx: number) => (
            <div key={idx} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                {check.passed ? <CheckCircle className="w-4 h-4 text-emerald-400"/> : <AlertCircle className="w-4 h-4 text-red-400"/>}
                <span className="font-bold">{check.name}</span>
              </div>
              <span className="text-xs text-zinc-500 ml-6">{check.display}</span>
            </div>
          )) : (
            <div className="text-zinc-500 italic">Policy result not available</div>
          )}
        </div>
      </div>
      
      {/* Action Boundary - Approve */}
      {!isApproved && !isRejected && (
        <div className="p-8 border border-white/20 rounded-xl bg-white/5 text-center space-y-4">
          <p className="text-zinc-400 mb-2">Merchant approval required to create financial obligations.</p>
          <button 
            onClick={onApprove}
            className="px-8 py-4 bg-white text-black font-bold rounded-lg hover:bg-zinc-200 transition-colors shadow-lg shadow-white/10"
          >
            APPROVE CAMPAIGN
          </button>
        </div>
      )}

      {/* Action Boundary - Rejected */}
      {isRejected && (
        <div className="p-8 border border-red-500/30 rounded-xl bg-red-500/5 text-center space-y-4">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto" />
          <p className="text-red-400 font-bold mb-2">CAMPAIGN BLOCKED BY POLICY</p>
          <p className="text-zinc-400 mb-4">This proposal failed one or more deterministic policy engine constraints. It cannot be approved or executed.</p>
        </div>
      )}

      {/* Action Boundary - Execute */}
      {isApproved && !isExecuted && !isExecuting && (
        <div className="p-8 border border-emerald-500/30 rounded-xl bg-emerald-500/5 text-center space-y-4">
          <p className="text-emerald-400 font-bold mb-2">✓ Merchant Approved</p>
          <p className="text-zinc-400 mb-4">Ready to generate Razorpay Payment Links.</p>
          <button 
            onClick={onExecute}
            className="px-8 py-4 bg-emerald-500 text-black font-bold rounded-lg hover:bg-emerald-400 transition-colors shadow-lg shadow-emerald-500/20"
          >
            EXECUTE CAMPAIGN
          </button>
        </div>
      )}

      {/* Execution Progress & Insights */}
      {isExecuted && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass-panel p-6 border-t-4 border-t-indigo-500">
            <h3 className="font-bold text-white mb-4">RAZORPAY EXECUTION</h3>
            <p className="text-zinc-400 mb-2">{targetCount} targets processed</p>
            
            <div className="w-full bg-zinc-800 rounded-full h-2 mb-4">
              <div 
                className="bg-indigo-500 h-2 rounded-full transition-all duration-1000" 
                style={{width: `${targetCount > 0 ? (linksGenerated / targetCount) * 100 : 0}%`}}
              ></div>
            </div>
            
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center text-zinc-300">
                <span>Payment Links Created</span>
                <span className="font-bold text-white">
                  {isDemo && linksGenerated === 0 ? targetCount : linksGenerated}
                </span>
              </div>
              {linksFailed > 0 && !isDemo && (
                <div className="flex justify-between items-center text-red-400">
                  <span>Failed Generation</span>
                  <span className="font-bold">{linksFailed}</span>
                </div>
              )}
              {isDemo && (
                <div className="text-xs text-zinc-500 mt-2 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                  <span>Demo Sandbox: Simulated execution targets active</span>
                </div>
              )}
            </div>
          </div>
          
          <div className="glass-panel p-6 border-t-4 border-t-emerald-500 bg-gradient-to-br from-emerald-900/10 to-transparent">
            <h3 className="font-bold text-emerald-400 mb-4">RECOVERY PERFORMANCE</h3>
            
            <div className="flex items-center justify-between mb-6">
              <div>
                <p className="text-zinc-500 text-xs">Expected</p>
                <p className="text-2xl font-bold text-zinc-300">{formatINR(campaign.sys_expected_net_inr)}</p>
              </div>
              <div className="text-zinc-500"><ArrowRight className="w-5 h-5"/></div>
              <div className="text-right">
                <p className="text-zinc-500 text-xs">Actual</p>
                <p className="text-3xl font-bold text-emerald-400">{formatPaiseToINR(actualRecoveryPaise)}</p>
              </div>
            </div>
            
            <div className="grid grid-cols-4 gap-2 text-center text-xs font-bold text-zinc-500">
              <div className="bg-black/30 p-2 rounded text-emerald-400">{paidCount} PAID</div>
              <div className="bg-black/30 p-2 rounded text-red-400">{targets.filter((t: any) => t.recovery_status === 'EXPIRED').length} EXPIRED</div>
              <div className="bg-black/30 p-2 rounded">{isDemo && linksGenerated === 0 ? targetCount : (linksGenerated - paidCount - targets.filter((t: any) => t.recovery_status === 'EXPIRED').length)} PENDING</div>
              <div className="bg-black/30 p-2 rounded">{isDemo ? 0 : linksFailed} FAILED</div>
            </div>
          </div>

          <div className="md:col-span-2 glass-panel p-6 bg-gradient-to-r from-indigo-900/20 to-purple-900/20 border border-indigo-500/30">
            <h3 className="font-bold text-indigo-300 mb-2 flex items-center gap-2">🧠 WHAT RAZOROPS LEARNED</h3>
            <p className="text-zinc-200">
              Current campaign has <span className="font-bold">{paidCount}</span> successful recoveries totaling <span className="font-bold text-emerald-400">{formatPaiseToINR(actualRecoveryPaise)}</span>. 
              These webhook-confirmed outcomes will become historical evidence for the agent after this campaign completes.
            </p>
          </div>
        </div>
      )}

    </div>
  );
}
