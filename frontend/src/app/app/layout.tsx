"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Zap, LayoutDashboard, Target, Layers, LogOut } from "lucide-react";

export const WorkspaceContext = createContext<{ merchantId: string; isDemo: boolean; setDemoMode: (val: boolean) => void }>({
  merchantId: "merchant_acme_001",
  isDemo: true,
  setDemoMode: () => {}
});

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isDemo, setIsDemo] = useState(true);
  const [connectedMerchant, setConnectedMerchant] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("rzops_connected_merchant");
    if (saved) {
      setConnectedMerchant(saved);
      setIsDemo(false);
    }
    setMounted(true);
  }, []);

  const toggleWorkspace = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (e.target.value === "demo") {
      setIsDemo(true);
    } else {
      if (connectedMerchant) {
        setIsDemo(false);
      } else {
        router.push("/connect");
      }
    }
  };

  const merchantId = isDemo ? "merchant_acme_001" : (connectedMerchant || "merchant_acme_001");

  if (!mounted) return null;

  return (
    <WorkspaceContext.Provider value={{ merchantId, isDemo, setDemoMode: setIsDemo }}>
      <div className="flex h-screen bg-black text-white font-sans overflow-hidden">
        
        {/* Sidebar */}
        <aside className="w-64 border-r border-white/10 flex flex-col bg-zinc-950">
          <div className="p-6">
            <div className="flex items-center gap-2 mb-8">
              <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-xl tracking-tight">RazorOps AI</span>
            </div>

            <nav className="space-y-2">
              <NavItem href="/app/dashboard" icon={<LayoutDashboard />} label="Dashboard" active={pathname === "/app/dashboard"} />
              <NavItem href="/app/opportunities" icon={<Target />} label="Opportunities" active={pathname === "/app/opportunities"} />
              <NavItem href="/app/campaigns" icon={<Layers />} label="Campaigns" active={pathname === "/app/campaigns"} />
            </nav>
          </div>

          <div className="mt-auto p-6">
            <button 
              onClick={() => {
                localStorage.removeItem("rzops_connected_merchant");
                router.push("/");
              }}
              className="flex items-center gap-3 text-zinc-500 hover:text-white transition-colors w-full text-sm font-medium"
            >
              <LogOut className="w-4 h-4" /> Exit App
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1 flex flex-col h-screen overflow-hidden">
          
          {/* Topbar */}
          <header className="h-16 border-b border-white/10 flex items-center justify-between px-8 bg-black/50 backdrop-blur-md sticky top-0 z-10">
            <div className="flex items-center gap-3">
              <select 
                value={isDemo ? "demo" : "connected"}
                onChange={toggleWorkspace}
                className="bg-zinc-900 border border-white/10 rounded-lg px-3 py-1.5 text-sm font-medium text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="demo">Demo Workspace</option>
                {connectedMerchant && <option value="connected">My Store</option>}
                {!connectedMerchant && <option value="connect">Connect Real Account...</option>}
              </select>
              
              {!isDemo && connectedMerchant && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded-full font-bold uppercase tracking-widest">Test Mode</span>
                  <span className="text-zinc-500">Last synced just now</span>
                </div>
              )}
              {isDemo && (
                <span className="text-xs bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded-full font-bold uppercase tracking-widest">
                  Sample Data
                </span>
              )}
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-y-auto custom-scrollbar relative">
            {isDemo && (
              <div className="absolute top-0 left-0 w-full bg-indigo-500/10 border-b border-indigo-500/20 px-8 py-2 text-xs text-indigo-300 font-medium text-center z-0">
                You are exploring RazorOps using a pre-populated interactive demo dataset.
              </div>
            )}
            <div className={isDemo ? "pt-12" : "pt-4"}>
              {children}
            </div>
          </main>
        </div>

      </div>
    </WorkspaceContext.Provider>
  );
}

function NavItem({ href, icon, label, active }: any) {
  return (
    <Link href={href} className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${active ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white hover:bg-white/5'}`}>
      {React.cloneElement(icon, { className: "w-4 h-4" })} {label}
    </Link>
  );
}
