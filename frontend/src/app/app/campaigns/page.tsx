"use client";
import React, { useContext, useEffect, useState } from "react";
import axios from "axios";
import { Layers } from "lucide-react";
import { WorkspaceContext } from "../layout";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function CampaignsPage() {
  const { merchantId, isDemo } = useContext(WorkspaceContext);
  const [campaigns, setCampaigns] = useState<any[]>([]);

  useEffect(() => {
    axios.get(`${API_URL}/campaigns`, { headers: { "x-merchant-id": merchantId } })
      .then(res => setCampaigns(res.data))
      .catch(console.error);
  }, [merchantId]);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-slide-down">
      <div className="flex items-center gap-3 mb-8">
        <Layers className="w-8 h-8 text-indigo-400" />
        <h1 className="text-3xl font-bold text-white">Campaigns</h1>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {campaigns.map(c => (
          <div key={c.id} className="glass-panel p-6 border border-white/5 hover:border-indigo-500/50 transition-all block group">
            <div className="flex justify-between items-start mb-4">
              <h3 className="font-bold text-white text-lg">{c.segment_name || "Campaign"}</h3>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold tracking-widest uppercase ${
                c.status === 'VALIDATED' ? 'bg-indigo-500/20 text-indigo-400' :
                c.status === 'APPROVED' ? 'bg-orange-500/20 text-orange-400' :
                ['ACTIVE', 'COMPLETED'].includes(c.status) ? 'bg-emerald-500/20 text-emerald-400' :
                'bg-zinc-800 text-zinc-400'
              }`}>
                {c.status}
              </span>
            </div>
            
            <div className="space-y-2 mb-4">
              <div className="flex justify-between text-sm text-zinc-400">
                <span>Expected Net:</span>
                <span className="text-emerald-400 font-bold">
                  {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(c.sys_expected_net_inr)}
                </span>
              </div>
              <div className="flex justify-between text-sm text-zinc-400">
                <span>Created:</span>
                <span>{new Date(c.created_at).toLocaleDateString()}</span>
              </div>
            </div>
            
          </div>
        ))}
        {campaigns.length === 0 && (
          <div className="col-span-full p-12 glass-panel text-center text-zinc-500">
            No campaigns found.
          </div>
        )}
      </div>
    </div>
  );
}
