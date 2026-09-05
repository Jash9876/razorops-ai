"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { CheckCircle, Loader2, Shield, ArrowRight } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function ConnectRazorpay() {
  const router = useRouter();
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [status, setStatus] = useState<"idle" | "connecting" | "syncing" | "ready" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyId || !keySecret) return;
    
    setStatus("connecting");
    setErrorMsg("");

    try {
      // 1. Connect and store keys securely
      const connectRes = await axios.post(`${API_URL}/connect`, {
        key_id: keyId,
        key_secret: keySecret,
        environment: "Test"
      });
      
      const newMerchantId = connectRes.data.merchant_id;
      
      // We store the connected merchant id locally to signal we are in Connected Workspace
      localStorage.setItem("rzops_connected_merchant", newMerchantId);
      
      // 2. Trigger data sync
      setStatus("syncing");
      await axios.post(`${API_URL}/sync-data`, null, {
        headers: { "x-merchant-id": newMerchantId }
      });
      
      setStatus("ready");
    } catch (e: any) {
      setStatus("error");
      setErrorMsg(e.response?.data?.detail || e.message || "Failed to connect.");
    }
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-8 font-sans">
      <div className="max-w-md w-full">
        
        <div className="mb-8 text-center">
          <div className="w-16 h-16 bg-indigo-500 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-indigo-500/20 mb-6">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Connect Razorpay</h1>
          <p className="text-zinc-400">
            Connect your Razorpay Test Mode account to analyze your payment activity securely.
          </p>
        </div>

        {status === "idle" || status === "error" ? (
          <form onSubmit={handleConnect} className="glass-panel p-8 space-y-6">
            {status === "error" && (
              <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {errorMsg}
              </div>
            )}
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Environment</label>
                <div className="w-full bg-zinc-900 border border-white/10 rounded-lg px-4 py-3 text-zinc-400 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-orange-400"></div> Test Mode
                </div>
                <p className="text-xs text-zinc-500 mt-2">Live mode requires OAuth partner approval.</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Key ID</label>
                <input 
                  type="text" 
                  value={keyId}
                  onChange={e => setKeyId(e.target.value)}
                  placeholder="rzp_test_..."
                  className="w-full bg-black border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-colors"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Key Secret</label>
                <input 
                  type="password" 
                  value={keySecret}
                  onChange={e => setKeySecret(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="w-full bg-black border border-white/10 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-colors"
                  required
                />
              </div>
            </div>
            
            <button 
              type="submit"
              className="w-full bg-indigo-500 hover:bg-indigo-400 text-white font-bold py-4 rounded-lg transition-colors flex justify-center items-center gap-2"
            >
              Connect Securely
            </button>
            <p className="text-xs text-zinc-500 text-center">
              Credentials are only sent to your backend and never stored in the database.
            </p>
          </form>
        ) : (
          <div className="glass-panel p-8 space-y-6">
            <h2 className="text-xl font-bold text-white text-center mb-8">
              {status === "ready" ? "Workspace Ready" : "Connecting..."}
            </h2>
            
            <div className="space-y-4">
              <SyncStep label="Razorpay account connected" active={status !== "idle"} />
              <SyncStep label="Importing payment data" active={status === "syncing" || status === "ready"} loading={status === "syncing"} />
              <SyncStep label="Building customer profiles" active={status === "syncing" || status === "ready"} loading={status === "syncing"} />
              <SyncStep label="Calculating recovery opportunities" active={status === "syncing" || status === "ready"} loading={status === "syncing"} />
              <SyncStep label="Ready" active={status === "ready"} />
            </div>
            
            {status === "ready" && (
              <button 
                onClick={() => router.push("/app/dashboard")}
                className="w-full mt-8 bg-emerald-500 hover:bg-emerald-400 text-black font-bold py-4 rounded-lg transition-colors flex justify-center items-center gap-2"
              >
                Open Workspace <ArrowRight className="w-5 h-5" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SyncStep({ label, active, loading }: any) {
  return (
    <div className={`flex items-center gap-3 transition-opacity duration-500 ${active ? 'opacity-100' : 'opacity-30'}`}>
      {loading ? (
        <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
      ) : active ? (
        <CheckCircle className="w-5 h-5 text-emerald-400" />
      ) : (
        <div className="w-5 h-5 rounded-full border-2 border-zinc-700" />
      )}
      <span className={`text-sm ${active && !loading ? 'text-zinc-200' : 'text-zinc-500'}`}>{label}</span>
    </div>
  );
}
