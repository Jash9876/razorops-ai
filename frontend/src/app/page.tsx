import React from "react";
import Link from "next/link";
import { ArrowRight, ShieldCheck, Activity, Zap, CreditCard, ChevronRight } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black text-white selection:bg-indigo-500/30 font-sans">
      
      {/* Navbar */}
      <nav className="w-full flex justify-between items-center px-8 py-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-xl tracking-tight">RazorOps AI</span>
        </div>
        <div className="flex gap-4">
          <Link href="/connect" className="text-zinc-300 hover:text-white font-medium px-4 py-2 transition-colors">
            Connect Razorpay
          </Link>
          <Link href="/app/dashboard" className="bg-white/10 hover:bg-white/20 text-white font-medium px-4 py-2 rounded-lg transition-colors border border-white/10">
            Explore Demo
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-8 pt-20 pb-32">
        <div className="max-w-4xl">
          <h1 className="text-6xl md:text-7xl font-extrabold tracking-tighter mb-8 leading-[1.1]">
            Recover revenue you've <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-emerald-400">already earned.</span>
          </h1>
          <p className="text-xl text-zinc-400 mb-12 max-w-2xl leading-relaxed">
            RazorOps uses AI to investigate failed payments, prioritize recovery opportunities, and execute merchant-approved recovery campaigns through Razorpay.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4">
            <Link href="/connect" className="bg-indigo-500 hover:bg-indigo-400 text-white font-bold px-8 py-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-500/25">
              Connect Razorpay <ArrowRight className="w-5 h-5" />
            </Link>
            <Link href="/app/dashboard" className="bg-white/5 hover:bg-white/10 border border-white/10 text-white font-bold px-8 py-4 rounded-xl flex items-center justify-center gap-2 transition-all">
              Explore Interactive Demo
            </Link>
          </div>
        </div>

        {/* Pipeline Explanation */}
        <div className="mt-32">
          <h2 className="text-2xl font-bold mb-12 flex items-center gap-3">
            <Activity className="w-6 h-6 text-indigo-400" />
            From failed payment to recovered revenue
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative">
            
            <PipelineCard 
              step="01" title="Detect" 
              desc="Failed payments and high-LTV churn risks detected." 
              icon={<CreditCard className="w-5 h-5 text-indigo-400" />}
            />
            <PipelineCard 
              step="02" title="Investigate" 
              desc="AI analyzes customer and payment context." 
              icon={<Zap className="w-5 h-5 text-indigo-400" />}
            />
            <PipelineCard 
              step="03" title="Decide" 
              desc="AI proposes the optimal intervention strategy." 
              icon={<Activity className="w-5 h-5 text-indigo-400" />}
            />
            <PipelineCard 
              step="04" title="Protect" 
              desc="Policy Engine checks discount, ROI, and budgets." 
              icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />}
            />
            <PipelineCard 
              step="05" title="Approve" 
              desc="Merchant remains in complete control." 
              icon={<CheckSquare className="w-5 h-5 text-orange-400" />}
            />
            <PipelineCard 
              step="06" title="Recover" 
              desc="Razorpay automatically executes the action." 
              icon={<ArrowRight className="w-5 h-5 text-emerald-400" />}
            />
            <PipelineCard 
              step="07" title="Learn" 
              desc="Actual outcomes improve future AI decisions." 
              icon={<Activity className="w-5 h-5 text-indigo-400" />}
            />
            
          </div>
        </div>
      </main>
    </div>
  );
}

function PipelineCard({ step, title, desc, icon }: any) {
  return (
    <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-colors flex flex-col relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-6 text-6xl font-black text-white/[0.02] group-hover:text-white/[0.04] transition-colors pointer-events-none -mt-4 -mr-4">
        {step}
      </div>
      <div className="mb-4">{icon}</div>
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-zinc-400">{desc}</p>
    </div>
  );
}

function CheckSquare(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 11 12 14 22 4"></polyline>
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
    </svg>
  );
}
