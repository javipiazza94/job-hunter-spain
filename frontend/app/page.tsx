"use client";

import { useEffect, useState } from "react";
import { Building2, Briefcase, Send, Users, RefreshCw, Play, Check, ChevronRight } from "lucide-react";
import { fetchStats, fetchCompanies, fetchOffers, fetchContacts, fetchApplications, triggerScraper, fetchPendingApplications, createDrafts, type PendingApplication } from "@/lib/api";
import { PendingCard } from "@/app/components/PendingCard";

interface Stats {
  companies: number;
  job_offers: number;
  relevant_offers: number;
  applications_sent: number;
  contacts_found: number;
}

interface Company {
  id: string;
  name: string;
  website: string;
  careers_url: string;
  sector: string;
  country: string;
  remote_policy: string | null;
  salary_transparent: number;
  offer_count: number;
  application_count: number;
}

interface JobOffer {
  id: string;
  title: string;
  company_name: string | null;
  location: string | null;
  relevance_score: number;
  url: string | null;
  description: string | null;
  cv_profile: string | null;
  modality: string | null;
  salary_text: string | null;
  experience_level: string | null;
  contract_type: string | null;
  source: string;
}

interface ContactOffer {
  id: string;
  title: string;
  url: string | null;
  relevance_score: number;
  location: string | null;
}

interface Contact {
  id: string;
  value: string;
  type: string | null;
  method: string | null;
  company_name: string | null;
  company_website: string | null;
  offers: ContactOffer[];
}

interface Application {
  id: string;
  company_name: string;
  job_title: string | null;
  status: string;
  method: string;
  sent_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  sent: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  replied: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
  interview: "bg-green-500/10 text-green-400 border border-green-500/20",
  rejected: "bg-red-500/10 text-red-400 border border-red-500/20",
  pending: "bg-gray-500/10 text-gray-400 border border-gray-500/20",
  withdrawn: "bg-gray-500/10 text-gray-500 border border-gray-500/20",
};

const SOURCE_COLORS: Record<string, string> = {
  tecnoempleo: "text-blue-400 bg-blue-400/10",
  indeed: "text-indigo-400 bg-indigo-400/10",
  manfred: "text-emerald-400 bg-emerald-400/10",
  seed: "text-purple-400 bg-purple-400/10",
  linkedin: "text-sky-400 bg-sky-400/10",
};

function StatCard({ icon: Icon, label, value, colorClass }: { icon: React.ElementType; label: string; value: number; colorClass: string }) {
  return (
    <div className="glass-card p-5 flex items-center gap-4 animate-fade-in">
      <div className={`p-3 rounded-xl bg-opacity-10 backdrop-blur-md border border-white/5 ${colorClass}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <div className="text-3xl font-bold tracking-tight text-white mb-1">{value}</div>
        <div className="text-sm font-medium text-gray-400">{label}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [offers, setOffers] = useState<JobOffer[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [pendingApps, setPendingApps] = useState<PendingApplication[]>([]);
  const [tab, setTab] = useState<"offers" | "companies" | "contacts" | "applications" | "pending">("offers");
  const [selectedOffer, setSelectedOffer] = useState<JobOffer | null>(null);
  
  // Filters
  const [profileFilter, setProfileFilter] = useState("all");
  const [modalityFilter, setModalityFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [experienceFilter, setExperienceFilter] = useState("all");
  const [locationSearch, setLocationSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState("");

  const load = async () => {
    const [s, c, o, ct, a, p] = await Promise.all([
      fetchStats(),
      fetchCompanies(),
      fetchOffers({ relevant_only: true }),
      fetchContacts(),
      fetchApplications(),
      fetchPendingApplications(),
    ]);
    setStats(s);
    setCompanies(c);
    setOffers(o);
    setContacts(ct);
    setApplications(a);
    setPendingApps(p);
  };

  useEffect(() => { load(); }, []);

  const handleScrape = async (source: string) => {
    setLoading(true);
    setActionMsg(`Scraping ${source}...`);
    await triggerScraper(source);
    setTimeout(() => { load(); setLoading(false); setActionMsg(""); }, 2000);
  };

  const handleApply = async () => {
    setLoading(true);
    setActionMsg("Generando borradores...");
    try {
      const result = await createDrafts();
      setActionMsg(`${result.drafts_created} borradores creados`);
      await load();
      setTab("pending");
      setTimeout(() => setActionMsg(""), 3000);
    } finally {
      setLoading(false);
    }
  };

  const filteredOffers = offers.filter(o => {
    if (profileFilter !== "all" && o.cv_profile !== profileFilter) return false;
    if (modalityFilter !== "all" && o.modality !== modalityFilter) return false;
    if (sourceFilter !== "all" && o.source !== sourceFilter) return false;
    if (experienceFilter !== "all" && o.experience_level !== experienceFilter) return false;
    if (locationSearch && !o.location?.toLowerCase().includes(locationSearch.toLowerCase())) return false;
    return true;
  });

  const PROFILE_BADGE: Record<string, string> = {
    sap: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
    ia_dev: "bg-purple-500/10 text-purple-400 border border-purple-500/20",
    manual_review: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
  };
  const MODALITY_BADGE: Record<string, string> = {
    remoto: "bg-green-500/10 text-green-400 border border-green-500/20",
    hibrido: "bg-amber-500/10 text-amber-400 border border-amber-500/20",
    presencial: "bg-gray-500/10 text-gray-400 border border-gray-500/20",
  };

  return (
    <div className="min-h-screen bg-[#0f0f14] text-gray-300 font-sans selection:bg-indigo-500/30">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-[#0f0f14]/80 backdrop-blur-xl border-b border-white/5 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_20px_rgba(99,102,241,0.3)]">
              <Briefcase className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">Job Hunter Spain</h1>
              <p className="text-xs text-indigo-300/80 font-medium tracking-wide uppercase">v2.0 Premium</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            {actionMsg && (
              <span className="text-sm text-indigo-400 font-medium px-4 py-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 animate-pulse">
                {actionMsg}
              </span>
            )}
            
            <div className="flex items-center p-1 bg-white/5 rounded-xl border border-white/5">
              {(["seed", "tecnoempleo", "indeed", "manfred", "linkedin", "contacts"] as const).map(src => (
                <button
                  key={src}
                  onClick={() => handleScrape(src)}
                  disabled={loading}
                  className="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all capitalize disabled:opacity-40"
                >
                  {src}
                </button>
              ))}
            </div>
            
            <button
              onClick={handleApply}
              disabled={loading}
              className="gradient-border group px-5 py-2.5 flex items-center gap-2 transition-all disabled:opacity-50"
            >
              <div className="absolute inset-0 bg-indigo-500/20 group-hover:bg-indigo-500/30 transition-colors"></div>
              <Play className="w-4 h-4 fill-white relative z-10 text-white group-hover:scale-110 transition-transform" /> 
              <span className="text-sm font-semibold text-white relative z-10 tracking-wide">Generar Borradores</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Analytics row */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-5">
            <StatCard icon={Building2} label="Empresas" value={stats.companies} colorClass="text-blue-400 bg-blue-500" />
            <StatCard icon={Briefcase} label="Ofertas Totales" value={stats.job_offers} colorClass="text-purple-400 bg-purple-500" />
            <StatCard icon={Check} label="Relevantes (>55%)" value={stats.relevant_offers} colorClass="text-green-400 bg-green-500" />
            <StatCard icon={Send} label="Enviadas" value={stats.applications_sent} colorClass="text-orange-400 bg-orange-500" />
            <StatCard icon={Users} label="Contactos Extraídos" value={stats.contacts_found} colorClass="text-teal-400 bg-teal-500" />
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 p-1.5 bg-white/5 backdrop-blur-sm border border-white/5 rounded-2xl w-fit animate-slide-in">
          {(
            [
              { id: "offers", label: "Ofertas", count: offers.length },
              { id: "companies", label: "Empresas", count: companies.length },
              { id: "contacts", label: "Contactos", count: contacts.length },
              { id: "applications", label: "Candidaturas", count: applications.length },
              { id: "pending", label: "Revisión", count: pendingApps.length },
            ] as const
          ).map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative px-5 py-2 text-sm font-medium rounded-xl transition-all duration-300 ${
                tab === t.id 
                  ? "text-white bg-white/10 shadow-[0_2px_10px_rgba(0,0,0,0.2)] border border-white/10" 
                  : "text-gray-400 hover:text-gray-200 hover:bg-white/5"
              }`}
            >
              {t.label} 
              <span className={`ml-2 px-2 py-0.5 rounded-md text-xs ${tab === t.id ? 'bg-white/20' : 'bg-black/20'}`}>
                {t.count}
              </span>
              {t.id === "pending" && t.count > 0 && (
                <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-amber-500 animate-pulse shadow-[0_0_8px_rgba(245,158,11,0.6)]" />
              )}
            </button>
          ))}
        </div>

        {/* Tab Content: Offers */}
        {tab === "offers" && (
          <div className="glass-card overflow-hidden animate-fade-in">
            {/* Filters Bar */}
            <div className="p-4 border-b border-white/5 bg-black/20 flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Perfil</span>
                <select 
                  value={profileFilter} onChange={e => setProfileFilter(e.target.value)}
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none"
                >
                  <option value="all">Todos</option>
                  <option value="sap">SAP</option>
                  <option value="ia_dev">IA/Dev</option>
                  <option value="manual_review">Revisar</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Fuente</span>
                <select 
                  value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none"
                >
                  <option value="all">Todas</option>
                  <option value="tecnoempleo">Tecnoempleo</option>
                  <option value="indeed">Indeed</option>
                  <option value="manfred">Manfred</option>
                  <option value="linkedin">LinkedIn</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Nivel</span>
                <select
                  value={experienceFilter} onChange={e => setExperienceFilter(e.target.value)}
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none"
                >
                  <option value="all">Todos</option>
                  <option value="junior">Junior</option>
                  <option value="mid">Mid</option>
                  <option value="senior">Senior</option>
                  <option value="lead">Lead</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Ubicación</span>
                <input
                  value={locationSearch} onChange={e => setLocationSearch(e.target.value)}
                  placeholder="Buscar ciudad..."
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none w-48 placeholder-gray-600"
                />
              </div>

              <div className="ml-auto flex items-center gap-4">
                <span className="text-sm font-medium text-indigo-300/80 bg-indigo-500/10 px-3 py-1 rounded-lg border border-indigo-500/20">
                  {filteredOffers.length} / {offers.length} ofertas
                </span>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5 tracking-wider">
                  <tr>
                    <th className="px-6 py-4 font-semibold">Oferta</th>
                    <th className="px-6 py-4 font-semibold">Empresa</th>
                    <th className="px-6 py-4 font-semibold">Ubicación & Stats</th>
                    <th className="px-6 py-4 font-semibold text-right">Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredOffers.map((o, idx) => (
                    <tr key={o.id} className="hover:bg-white/[0.02] transition-colors stagger-row" style={{ animationDelay: `${idx * 0.03}s` }}>
                      <td className="px-6 py-4">
                        <div className="flex flex-col gap-1.5">
                          <button onClick={() => setSelectedOffer(o)} className="font-semibold text-left text-gray-200 hover:text-indigo-400 transition-colors inline-flex items-center gap-1">
                            {o.title} {o.url && <ChevronRight className="w-3 h-3 opacity-50" />}
                          </button>
                          <div className="flex items-center gap-2">
                            {o.source && <span className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded ${SOURCE_COLORS[o.source] || SOURCE_COLORS.seed}`}>{o.source}</span>}
                            {o.experience_level && <span className="text-xs text-gray-500 font-mono capitalize">{o.experience_level}</span>}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-gray-400 font-medium">
                        {o.company_name || "—"}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-col gap-1">
                          <span className="text-gray-300">{o.location || "—"}</span>
                          <div className="flex gap-2">
                            {o.modality && <span className={`text-xs px-2 py-0.5 rounded-md font-medium ${MODALITY_BADGE[o.modality] ?? ""}`}>{o.modality}</span>}
                            {o.salary_text && <span className="text-xs text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-md font-mono">{o.salary_text}</span>}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex flex-col items-end gap-2">
                          <span className={`px-3 py-1 rounded-lg text-sm font-bold tracking-wide border ${o.relevance_score >= 0.8 ? "bg-green-500/10 text-green-400 border-green-500/20" : o.relevance_score >= 0.65 ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" : "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}>
                            {(o.relevance_score * 100).toFixed(0)}%
                          </span>
                          {o.cv_profile && <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${PROFILE_BADGE[o.cv_profile] ?? "bg-gray-800 text-gray-400"}`}>{o.cv_profile}</span>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Other tabs will follow the same pattern, abbreviated here for space */}
        {tab === "pending" && (
          <div className="space-y-6 animate-fade-in">
            {pendingApps.length === 0 ? (
              <div className="glass-card p-16 text-center border-dashed border-white/10">
                <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-gray-500" />
                </div>
                <h3 className="text-lg font-medium text-gray-300 mb-2">Bandeja limpia</h3>
                <p className="text-sm text-gray-500">Pulsa &quot;Generar borradores&quot; en la barra superior para evaluar nuevas ofertas.</p>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-medium text-gray-200">Revisión de Candidaturas</h2>
                  <span className="text-sm font-mono text-amber-400 bg-amber-400/10 px-3 py-1 rounded-lg border border-amber-400/20">
                    {pendingApps.length} esperando
                  </span>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                  {pendingApps.map((a, idx) => (
                    <div key={a.id} className="stagger-row" style={{ animationDelay: `${idx * 0.05}s` }}>
                      <PendingCard app={a} onAction={load} />
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        
        {tab === "companies" && (
          <div className="glass-card overflow-hidden animate-fade-in">
            <div className="p-4 border-b border-white/5 bg-black/20 flex items-center gap-3">
              <span className="text-sm font-medium text-gray-500 uppercase tracking-wider">País:</span>
              <select
                value={countryFilter}
                onChange={(e) => setCountryFilter(e.target.value)}
                className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none"
              >
                <option value="">Todos</option>
                <option value="ES">España</option>
                <option value="US">USA</option>
                <option value="UK">UK</option>
              </select>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5 tracking-wider">
                  <tr>
                    <th className="px-6 py-4 font-semibold">Empresa</th>
                    <th className="px-6 py-4 font-semibold">Sector</th>
                    <th className="px-6 py-4 font-semibold">País</th>
                    <th className="px-6 py-4 font-semibold text-right">Ofertas</th>
                    <th className="px-6 py-4 font-semibold text-right">Enviadas</th>
                    <th className="px-6 py-4 font-semibold">Empleos</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {companies.map((c, idx) => (
                    <tr key={c.id} className="hover:bg-white/[0.02] transition-colors stagger-row" style={{ animationDelay: `${idx * 0.02}s` }}>
                      <td className="px-6 py-4 font-semibold text-gray-200">{c.name}</td>
                      <td className="px-6 py-4">
                        <span className="bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full text-[10px] uppercase font-bold tracking-wider">{c.sector}</span>
                      </td>
                      <td className="px-6 py-4 text-gray-400">{c.country}</td>
                      <td className="px-6 py-4 text-right text-gray-300 tabular-nums font-mono">{c.offer_count}</td>
                      <td className="px-6 py-4 text-right tabular-nums font-mono">
                        <span className={c.application_count > 0 ? "text-emerald-400 font-semibold" : "text-gray-600"}>
                          {c.application_count}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {c.careers_url && (
                          <a href={c.careers_url} target="_blank" rel="noopener noreferrer"
                            className="text-indigo-400 hover:text-indigo-300 hover:underline text-xs font-medium inline-flex items-center gap-1">Ver <ChevronRight className="w-3 h-3" /></a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "contacts" && (
          <div className="glass-card overflow-hidden animate-fade-in">
            {contacts.length === 0 ? (
              <div className="p-16 text-center border-dashed border-white/10">
                <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
                  <Users className="w-8 h-8 text-gray-500" />
                </div>
                <h3 className="text-lg font-medium text-gray-300 mb-2">Sin contactos aún</h3>
                <p className="text-sm text-gray-500">Pulsa &quot;Contactos&quot; en la barra superior para extraer emails de las webs de empresas.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5 tracking-wider">
                    <tr>
                      <th className="px-6 py-4 font-semibold">Contacto</th>
                      <th className="px-6 py-4 font-semibold">Empresa</th>
                      <th className="px-6 py-4 font-semibold">Ofertas relevantes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {contacts.map((ct, idx) => (
                      <tr key={ct.id} className="hover:bg-white/[0.02] transition-colors align-top stagger-row" style={{ animationDelay: `${idx * 0.02}s` }}>
                        <td className="px-6 py-4">
                          <div className="font-mono text-sm text-indigo-400 mb-1">{ct.value}</div>
                          <span className="bg-white/5 text-gray-400 border border-white/10 px-1.5 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">{ct.type || "email"}</span>
                        </td>
                        <td className="px-6 py-4 text-gray-400 text-sm">
                          <div className="font-medium text-gray-200 mb-1">{ct.company_name || "—"}</div>
                          {ct.company_website && <a href={ct.company_website} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 hover:underline text-xs inline-flex items-center gap-1">Web <ChevronRight className="w-3 h-3" /></a>}
                        </td>
                        <td className="px-6 py-4">
                          {ct.offers.length === 0 ? (
                            <span className="text-xs text-gray-500 italic">Sin ofertas activas</span>
                          ) : (
                            <div className="flex flex-col gap-2">
                              {ct.offers.slice(0, 4).map(o => (
                                <div key={o.id} className="flex items-center gap-3">
                                  {o.url ? (
                                    <a href={o.url} target="_blank" rel="noopener noreferrer" className="text-sm text-gray-300 hover:text-indigo-400 hover:underline truncate max-w-xs font-medium">{o.title}</a>
                                  ) : (
                                    <span className="text-sm text-gray-300 truncate max-w-xs font-medium">{o.title}</span>
                                  )}
                                  <span className="text-xs text-gray-500 shrink-0 bg-black/20 px-2 py-0.5 rounded-md border border-white/5">{o.location || "Remoto"}</span>
                                  <span className={`text-[10px] font-bold tracking-wider px-2 py-0.5 rounded shrink-0 border ${o.relevance_score >= 0.8 ? "bg-green-500/10 text-green-400 border-green-500/20" : "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}>
                                    {(o.relevance_score * 100).toFixed(0)}%
                                  </span>
                                </div>
                              ))}
                              {ct.offers.length > 4 && <span className="text-xs text-indigo-400/80 font-medium ml-1">+{ct.offers.length - 4} más</span>}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {tab === "applications" && (
          <div className="glass-card overflow-hidden animate-fade-in">
            {applications.length === 0 ? (
              <div className="p-16 text-center border-dashed border-white/10">
                <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
                  <Send className="w-8 h-8 text-gray-500" />
                </div>
                <h3 className="text-lg font-medium text-gray-300 mb-2">Aún no hay candidaturas enviadas</h3>
                <p className="text-sm text-gray-500">Extrae contactos, genera borradores y aprueba envíos.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5 tracking-wider">
                    <tr>
                      <th className="px-6 py-4 font-semibold">Empresa</th>
                      <th className="px-6 py-4 font-semibold">Puesto</th>
                      <th className="px-6 py-4 font-semibold">Estado</th>
                      <th className="px-6 py-4 font-semibold">Método</th>
                      <th className="px-6 py-4 font-semibold">Fecha</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {applications.map((a, idx) => (
                      <tr key={a.id} className="hover:bg-white/[0.02] transition-colors stagger-row" style={{ animationDelay: `${idx * 0.02}s` }}>
                        <td className="px-6 py-4 font-semibold text-gray-200">{a.company_name}</td>
                        <td className="px-6 py-4 text-gray-400 font-medium">{a.job_title || "Candidatura espontánea"}</td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 rounded-md text-[10px] uppercase tracking-wider font-bold ${STATUS_COLORS[a.status] || "bg-gray-500/10 text-gray-400 border border-gray-500/20"}`}>
                            {a.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-400 capitalize">{a.method}</td>
                        <td className="px-6 py-4 text-gray-500 font-mono text-xs">
                          {a.sent_at ? new Date(a.sent_at).toLocaleDateString("es-ES") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

      </main>

      {/* Offer Detail Modal */}
      {selectedOffer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-fade-in">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedOffer(null)}></div>
          <div className="relative w-full max-w-3xl max-h-[85vh] flex flex-col bg-[#16161f] border border-white/10 rounded-2xl shadow-[0_0_40px_rgba(0,0,0,0.5)] overflow-hidden">
            <div className="p-6 border-b border-white/5 flex items-start justify-between bg-white/5">
              <div>
                <h2 className="text-xl font-bold text-white mb-2">{selectedOffer.title}</h2>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm font-medium text-indigo-400">{selectedOffer.company_name || "Empresa Confidencial"}</span>
                  <span className="text-gray-500">•</span>
                  <span className="text-sm text-gray-400">{selectedOffer.location || "Remoto"}</span>
                  <span className="text-gray-500">•</span>
                  {selectedOffer.salary_text && <span className="text-xs text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-md font-mono">{selectedOffer.salary_text}</span>}
                  {selectedOffer.modality && <span className={`text-xs px-2 py-0.5 rounded-md font-medium ${MODALITY_BADGE[selectedOffer.modality] ?? ""}`}>{selectedOffer.modality}</span>}
                </div>
              </div>
              <button onClick={() => setSelectedOffer(null)} className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1 custom-scrollbar">
              <div className="flex gap-2 mb-6">
                <span className={`px-3 py-1 rounded-lg text-sm font-bold tracking-wide border ${selectedOffer.relevance_score >= 0.8 ? "bg-green-500/10 text-green-400 border-green-500/20" : selectedOffer.relevance_score >= 0.65 ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" : "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}>
                  Score: {(selectedOffer.relevance_score * 100).toFixed(0)}%
                </span>
                {selectedOffer.cv_profile && <span className={`text-xs uppercase font-bold tracking-wider px-3 py-1 rounded-lg flex items-center ${PROFILE_BADGE[selectedOffer.cv_profile] ?? "bg-gray-800 text-gray-400"}`}>Perfil: {selectedOffer.cv_profile}</span>}
                {selectedOffer.source && <span className={`text-xs uppercase font-bold tracking-wider px-3 py-1 rounded-lg flex items-center border border-current ${SOURCE_COLORS[selectedOffer.source] || SOURCE_COLORS.seed}`}>{selectedOffer.source}</span>}
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4 border-b border-white/5 pb-2">Descripción del Puesto</h3>
                {selectedOffer.description ? (
                  <div className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap font-sans">
                    {selectedOffer.description}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">No hay descripción disponible para esta oferta.</p>
                )}
              </div>
            </div>
            
            <div className="p-5 border-t border-white/5 bg-black/20 flex justify-end gap-3">
              <button onClick={() => setSelectedOffer(null)} className="px-5 py-2 text-sm font-medium text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-colors">
                Cerrar
              </button>
              {selectedOffer.url && (
                <a href={selectedOffer.url} target="_blank" rel="noopener noreferrer" className="px-5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all flex items-center gap-2">
                  Abrir Oferta Original <ChevronRight className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
