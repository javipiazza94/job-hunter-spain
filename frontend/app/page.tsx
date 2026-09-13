"use client";

import { useEffect, useState } from "react";
import { Building2, Briefcase, Send, Users, RefreshCw, Play, Check, ChevronRight } from "lucide-react";
import { fetchStats, fetchCompanies, fetchOffers, fetchContacts, fetchApplications, triggerScraper, fetchPendingApplications, createDrafts, markOfferSent, unmarkOfferSent, type PendingApplication } from "@/lib/api";
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
  is_applied: number;
  sap_tier: number | null;
  sap_module: string | null;
  open_to_junior: number | null;
  ds_tier: number | null;
  ds_category: string | null;
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
  offer_url: string | null;
  offer_source: string | null;
  offer_location: string | null;
  relevance_score: number | null;
  job_offer_id: string | null;
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
  infojobs: "text-orange-400 bg-orange-400/10",
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
  const [sapOffers, setSapOffers] = useState<JobOffer[]>([]);
  const [dsOffers, setDsOffers] = useState<JobOffer[]>([]);
  const [tab, setTab] = useState<"offers" | "companies" | "contacts" | "applications" | "pending" | "sap" | "ds">("offers");
  const [selectedOffer, setSelectedOffer] = useState<JobOffer | null>(null);
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  
  // Filters
  const [profileFilter, setProfileFilter] = useState("all");
  const [modalityFilter, setModalityFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [experienceFilter, setExperienceFilter] = useState("all");
  const [locationSearch, setLocationSearch] = useState("");
  const [textSearch, setTextSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [minScore, setMinScore] = useState(0);

  // Pagination
  const [offersPage, setOffersPage] = useState(0);
  const OFFERS_PER_PAGE = 100;
  
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [togglingIds, setTogglingIds] = useState<Set<string>>(new Set());

  const load = async () => {
    const [s, c, o, ct, a, p, sap] = await Promise.all([
      fetchStats(),
      fetchCompanies(),
      fetchOffers({ limit: 2500 }),
      fetchContacts(),
      fetchApplications(),
      fetchPendingApplications(),
      fetchOffers({ sap_tagged: true, limit: 200 }),
    ]);
    setStats(s);
    setCompanies(c);
    setOffers(o);
    setContacts(ct);
    setApplications(a);
    setPendingApps(p);
    setSapOffers(sap);
  };

  useEffect(() => { load(); }, []);

  const handleScrape = async (source: string) => {
    setLoading(true);
    setActionMsg(`Scraping ${source}...`);
    await triggerScraper(source);
    setTimeout(() => { load(); setLoading(false); setActionMsg(""); }, 2000);
  };

  const handleToggleSent = async (offer: JobOffer) => {
    if (togglingIds.has(offer.id)) return;
    setTogglingIds(prev => new Set(prev).add(offer.id));
    if (offer.is_applied) {
      await unmarkOfferSent(offer.id);
      setOffers(prev => prev.map(o => o.id === offer.id ? { ...o, is_applied: 0 } : o));
      setSapOffers(prev => prev.map(o => o.id === offer.id ? { ...o, is_applied: 0 } : o));
      setApplications(prev => prev.filter(a => a.job_offer_id !== offer.id));
    } else {
      await markOfferSent(offer.id);
      setOffers(prev => prev.map(o => o.id === offer.id ? { ...o, is_applied: 1 } : o));
      setSapOffers(prev => prev.map(o => o.id === offer.id ? { ...o, is_applied: 1 } : o));
      setApplications(prev => [{
        id: crypto.randomUUID(),
        company_name: offer.company_name || "Desconocida",
        job_title: offer.title,
        status: "sent",
        method: "manual",
        sent_at: new Date().toISOString(),
        offer_url: offer.url,
        offer_source: offer.source,
        offer_location: offer.location,
        relevance_score: offer.relevance_score,
        job_offer_id: offer.id,
      }, ...prev]);
      setTab("applications");
    }
    setTogglingIds(prev => { const s = new Set(prev); s.delete(offer.id); return s; });
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
    if (o.is_applied) return false;
    if (textSearch) {
      const q = textSearch.toLowerCase();
      const haystack = `${o.title} ${o.company_name ?? ""} ${o.description ?? ""}`.toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (profileFilter !== "all" && o.cv_profile !== profileFilter) return false;
    if (modalityFilter !== "all" && o.modality !== modalityFilter) return false;
    if (sourceFilter !== "all" && o.source !== sourceFilter) return false;
    if (experienceFilter !== "all" && o.experience_level !== experienceFilter) return false;
    if (locationSearch && !o.location?.toLowerCase().includes(locationSearch.toLowerCase())) return false;
    if (o.relevance_score < minScore) return false;
    return true;
  });

  const totalPages = Math.ceil(filteredOffers.length / OFFERS_PER_PAGE);
  const pagedOffers = filteredOffers.slice(offersPage * OFFERS_PER_PAGE, (offersPage + 1) * OFFERS_PER_PAGE);

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
  const TIER_BADGE: Record<number, { label: string; className: string }> = {
    1: { label: "Tier 1", className: "bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/20" },
    2: { label: "Tier 2", className: "bg-sky-500/10 text-sky-400 border border-sky-500/20" },
    3: { label: "Tier 3", className: "bg-gray-500/10 text-gray-300 border border-gray-500/20" },
    4: { label: "Fuera de lista", className: "bg-white/5 text-gray-500 border border-white/10" },
  };
  const MODULE_ORDER: Record<string, number> = { "PS": 0, "FI-CO": 1, "MM": 2, "SD": 3, "Otro": 4 };
  const sapSorted = [...sapOffers].sort((a, b) => {
    const t = (a.sap_tier ?? 9) - (b.sap_tier ?? 9);
    if (t !== 0) return t;
    return (MODULE_ORDER[a.sap_module ?? "Otro"] ?? 9) - (MODULE_ORDER[b.sap_module ?? "Otro"] ?? 9);
  });
  const sapNew = sapSorted.filter(o => !o.is_applied);
  const sapTracked = sapSorted.filter(o => o.is_applied);

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
              {(["seed", "tecnoempleo", "infojobs", "manfred", "linkedin", "contacts"] as const).map(src => (
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
              { id: "sap", label: "SAP Public Cloud", count: sapOffers.length },
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
              <input
                value={textSearch} onChange={e => { setTextSearch(e.target.value); setOffersPage(0); }}
                placeholder="Buscar por título, empresa, descripción..."
                className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none w-72 placeholder-gray-600"
              />

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Perfil</span>
                <select
                  value={profileFilter} onChange={e => { setProfileFilter(e.target.value); setOffersPage(0); }}
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
                  value={sourceFilter} onChange={e => { setSourceFilter(e.target.value); setOffersPage(0); }}
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none"
                >
                  <option value="all">Todas</option>
                  <option value="tecnoempleo">Tecnoempleo</option>
                  <option value="infojobs">InfoJobs</option>
                  <option value="manfred">Manfred</option>
                  <option value="linkedin">LinkedIn</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Nivel</span>
                <select
                  value={experienceFilter} onChange={e => { setExperienceFilter(e.target.value); setOffersPage(0); }}
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
                  value={locationSearch} onChange={e => { setLocationSearch(e.target.value); setOffersPage(0); }}
                  placeholder="Buscar ciudad..."
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none w-48 placeholder-gray-600"
                />
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Modalidad</span>
                <select
                  value={modalityFilter} onChange={e => { setModalityFilter(e.target.value); setOffersPage(0); }}
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none"
                >
                  <option value="all">Todas</option>
                  <option value="remoto">Remoto</option>
                  <option value="hibrido">Híbrido</option>
                  <option value="presencial">Presencial</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Score</span>
                <select
                  value={minScore} onChange={e => { setMinScore(Number(e.target.value)); setOffersPage(0); }}
                  className="bg-[#16161f] border border-white/10 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500/50 outline-none"
                >
                  <option value={0}>Todos</option>
                  <option value={0.5}>≥ 50%</option>
                  <option value={0.65}>≥ 65%</option>
                  <option value={0.8}>≥ 80%</option>
                </select>
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
                    <th className="px-4 py-4 w-10"></th>
                    <th className="px-6 py-4 font-semibold">Oferta</th>
                    <th className="px-6 py-4 font-semibold">Empresa</th>
                    <th className="px-6 py-4 font-semibold">Ubicación & Stats</th>
                    <th className="px-6 py-4 font-semibold text-right">Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {pagedOffers.map((o, idx) => (
                    <tr key={o.id} className="hover:bg-white/[0.02] transition-colors stagger-row" style={{ animationDelay: `${idx * 0.03}s` }}>
                      <td className="px-4 py-4 text-center">
                        <button
                          onClick={() => handleToggleSent(o)}
                          disabled={togglingIds.has(o.id)}
                          title={o.is_applied ? "Marcar como no enviada" : "Marcar como enviada"}
                          className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${o.is_applied ? "bg-green-500 border-green-500 text-white" : "border-gray-600 hover:border-green-500"} disabled:opacity-40`}
                        >
                          {o.is_applied ? <Check className="w-3 h-3" /> : null}
                        </button>
                      </td>
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

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-white/5 bg-black/20">
                <span className="text-sm text-gray-500">
                  {offersPage * OFFERS_PER_PAGE + 1}–{Math.min((offersPage + 1) * OFFERS_PER_PAGE, filteredOffers.length)} de {filteredOffers.length}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setOffersPage(p => Math.max(0, p - 1))}
                    disabled={offersPage === 0}
                    className="px-3 py-1.5 text-sm rounded-lg border border-white/10 text-gray-400 hover:text-white hover:border-indigo-500/50 hover:bg-indigo-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  >
                    ‹
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i).filter(i =>
                    i === 0 || i === totalPages - 1 || Math.abs(i - offersPage) <= 2
                  ).reduce<(number | "…")[]>((acc, i, idx, arr) => {
                    if (idx > 0 && i - (arr[idx - 1] as number) > 1) acc.push("…");
                    acc.push(i);
                    return acc;
                  }, []).map((item, idx) =>
                    item === "…" ? (
                      <span key={`dots-${idx}`} className="px-2 text-gray-600">…</span>
                    ) : (
                      <button
                        key={item}
                        onClick={() => setOffersPage(item as number)}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition-all ${offersPage === item ? "bg-indigo-500/20 border-indigo-500/50 text-indigo-300 font-bold" : "border-white/10 text-gray-400 hover:text-white hover:border-white/20"}`}
                      >
                        {(item as number) + 1}
                      </button>
                    )
                  )}
                  <button
                    onClick={() => setOffersPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={offersPage === totalPages - 1}
                    className="px-3 py-1.5 text-sm rounded-lg border border-white/10 text-gray-400 hover:text-white hover:border-indigo-500/50 hover:bg-indigo-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  >
                    ›
                  </button>
                </div>
              </div>
            )}
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
        
        {tab === "sap" && (
          <div className="space-y-8 animate-fade-in">
            {/* Nuevas */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-medium text-gray-200">Nuevas</h2>
                <span className="text-sm font-mono text-indigo-300 bg-indigo-500/10 px-3 py-1 rounded-lg border border-indigo-500/20">
                  {sapNew.length} sin candidatura
                </span>
              </div>
              {sapNew.length === 0 ? (
                <div className="glass-card p-10 text-center border-dashed border-white/10 text-sm text-gray-500">
                  No hay ofertas nuevas de la búsqueda SAP Public Cloud pendientes de revisar.
                </div>
              ) : (
                <div className="glass-card overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5 tracking-wider">
                        <tr>
                          <th className="px-4 py-4 w-10"></th>
                          <th className="px-6 py-4 font-semibold">Oferta</th>
                          <th className="px-6 py-4 font-semibold">Empresa</th>
                          <th className="px-6 py-4 font-semibold">Tier / Módulo</th>
                          <th className="px-6 py-4 font-semibold">Ubicación</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {sapNew.map((o, idx) => (
                          <tr key={o.id} className="hover:bg-white/[0.02] transition-colors stagger-row" style={{ animationDelay: `${idx * 0.03}s` }}>
                            <td className="px-4 py-4 text-center">
                              <button
                                onClick={() => handleToggleSent(o)}
                                disabled={togglingIds.has(o.id)}
                                title="Marcar como enviada"
                                className="w-5 h-5 rounded border-2 flex items-center justify-center transition-all border-gray-600 hover:border-green-500 disabled:opacity-40"
                              />
                            </td>
                            <td className="px-6 py-4">
                              <button onClick={() => setSelectedOffer(o)} className="font-semibold text-left text-gray-200 hover:text-indigo-400 transition-colors inline-flex items-center gap-1">
                                {o.title} {o.url && <ChevronRight className="w-3 h-3 opacity-50" />}
                              </button>
                              <div className="flex items-center gap-2 mt-1.5">
                                {o.source && <span className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded ${SOURCE_COLORS[o.source] || SOURCE_COLORS.seed}`}>{o.source}</span>}
                                {o.open_to_junior === 1 && <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Abierto a junior</span>}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-gray-400 font-medium">{o.company_name || "—"}</td>
                            <td className="px-6 py-4">
                              <div className="flex gap-2">
                                {o.sap_tier != null && (
                                  <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md ${TIER_BADGE[o.sap_tier]?.className ?? ""}`}>
                                    {TIER_BADGE[o.sap_tier]?.label ?? `Tier ${o.sap_tier}`}
                                  </span>
                                )}
                                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-white/5 text-gray-400 border border-white/10">
                                  {o.sap_module || "Otro"}
                                </span>
                              </div>
                            </td>
                            <td className="px-6 py-4 text-gray-300">{o.location || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Pendientes / Enviadas */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-medium text-gray-200">Pendientes de respuesta / Enviadas</h2>
                <span className="text-sm font-mono text-amber-400 bg-amber-400/10 px-3 py-1 rounded-lg border border-amber-400/20">
                  {sapTracked.length} con candidatura
                </span>
              </div>
              {sapTracked.length === 0 ? (
                <div className="glass-card p-10 text-center border-dashed border-white/10 text-sm text-gray-500">
                  Ninguna de estas ofertas tiene aún candidatura registrada.
                </div>
              ) : (
                <div className="glass-card overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5 tracking-wider">
                        <tr>
                          <th className="px-6 py-4 font-semibold">Oferta</th>
                          <th className="px-6 py-4 font-semibold">Empresa</th>
                          <th className="px-6 py-4 font-semibold">Tier / Módulo</th>
                          <th className="px-6 py-4 font-semibold">Estado</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {sapTracked.map((o, idx) => {
                          const app = applications.find(a => a.job_offer_id === o.id);
                          return (
                            <tr key={o.id} onClick={() => app && setSelectedApplication(app)} className="hover:bg-white/[0.02] transition-colors cursor-pointer stagger-row" style={{ animationDelay: `${idx * 0.03}s` }}>
                              <td className="px-6 py-4 font-semibold text-gray-200">{o.title}</td>
                              <td className="px-6 py-4 text-gray-400 font-medium">{o.company_name || "—"}</td>
                              <td className="px-6 py-4">
                                <div className="flex gap-2">
                                  {o.sap_tier != null && (
                                    <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md ${TIER_BADGE[o.sap_tier]?.className ?? ""}`}>
                                      {TIER_BADGE[o.sap_tier]?.label ?? `Tier ${o.sap_tier}`}
                                    </span>
                                  )}
                                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-white/5 text-gray-400 border border-white/10">
                                    {o.sap_module || "Otro"}
                                  </span>
                                </div>
                              </td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-1 rounded-md text-[10px] uppercase tracking-wider font-bold ${STATUS_COLORS[app?.status ?? ""] || "bg-gray-500/10 text-gray-400 border border-gray-500/20"}`}>
                                  {app?.status ?? "sent"}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
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
                    <tr key={c.id} onClick={() => setSelectedCompany(c)} className="hover:bg-white/[0.03] cursor-pointer transition-colors stagger-row" style={{ animationDelay: `${idx * 0.02}s` }}>
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
                      <tr key={ct.id} onClick={() => setSelectedContact(ct)} className="hover:bg-white/[0.03] cursor-pointer transition-colors align-top stagger-row" style={{ animationDelay: `${idx * 0.02}s` }}>
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
                <p className="text-sm text-gray-500">Marca ofertas como enviadas o usa el motor de candidaturas.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-400 uppercase bg-black/40 border-b border-white/5 tracking-wider">
                    <tr>
                      <th className="px-6 py-4 font-semibold">Oferta</th>
                      <th className="px-6 py-4 font-semibold">Empresa</th>
                      <th className="px-6 py-4 font-semibold">Ubicación</th>
                      <th className="px-6 py-4 font-semibold">Estado</th>
                      <th className="px-6 py-4 font-semibold text-right">Score / Fecha</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {applications.map((a, idx) => (
                      <tr
                        key={a.id}
                        onClick={() => setSelectedApplication(a)}
                        className="hover:bg-white/[0.03] cursor-pointer transition-colors stagger-row"
                        style={{ animationDelay: `${idx * 0.02}s` }}
                      >
                        <td className="px-6 py-4">
                          <div className="flex flex-col gap-1">
                            <span className="font-semibold text-gray-200 hover:text-indigo-400 transition-colors">
                              {a.job_title || "Candidatura espontánea"}
                            </span>
                            {a.offer_source && (
                              <span className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded w-fit ${SOURCE_COLORS[a.offer_source] || SOURCE_COLORS.seed}`}>
                                {a.offer_source}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-gray-400 font-medium">{a.company_name}</td>
                        <td className="px-6 py-4 text-gray-400">{a.offer_location || "—"}</td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 rounded-md text-[10px] uppercase tracking-wider font-bold ${STATUS_COLORS[a.status] || "bg-gray-500/10 text-gray-400 border border-gray-500/20"}`}>
                            {a.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex flex-col items-end gap-1">
                            {a.relevance_score != null && (
                              <span className={`px-2 py-0.5 rounded text-xs font-bold border ${a.relevance_score >= 0.8 ? "bg-green-500/10 text-green-400 border-green-500/20" : a.relevance_score >= 0.65 ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" : "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}>
                                {(a.relevance_score * 100).toFixed(0)}%
                              </span>
                            )}
                            <span className="text-xs text-gray-500 font-mono">
                              {a.sent_at ? new Date(a.sent_at).toLocaleDateString("es-ES") : "—"}
                            </span>
                          </div>
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

      {/* Company Detail Modal */}
      {selectedCompany && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedCompany(null)} />
          <div className="relative w-full max-w-md bg-[#16161f] border border-white/10 rounded-2xl shadow-[0_0_40px_rgba(0,0,0,0.5)] overflow-hidden">
            <div className="p-6 border-b border-white/5 bg-white/5 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold text-white mb-1">{selectedCompany.name}</h2>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">{selectedCompany.sector}</span>
              </div>
              <button onClick={() => setSelectedCompany(null)} className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div className="p-6 grid grid-cols-2 gap-3 text-sm">
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">País</div>
                <div className="text-gray-300">{selectedCompany.country || "—"}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Modalidad</div>
                <div className="text-gray-300">{selectedCompany.remote_policy || "—"}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Ofertas</div>
                <div className="text-gray-300 font-mono font-bold">{selectedCompany.offer_count}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Enviadas</div>
                <div className={`font-mono font-bold ${selectedCompany.application_count > 0 ? "text-emerald-400" : "text-gray-500"}`}>{selectedCompany.application_count}</div>
              </div>
            </div>
            <div className="px-6 pb-6 flex gap-2">
              {selectedCompany.website && (
                <a href={selectedCompany.website} target="_blank" rel="noopener noreferrer" className="flex-1 text-center px-4 py-2 text-sm font-medium text-gray-300 bg-white/5 hover:bg-white/10 rounded-xl transition-colors">Web</a>
              )}
              {selectedCompany.careers_url && (
                <a href={selectedCompany.careers_url} target="_blank" rel="noopener noreferrer" className="flex-1 text-center px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-colors flex items-center justify-center gap-1">Empleos <ChevronRight className="w-4 h-4"/></a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Contact Detail Modal */}
      {selectedContact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedContact(null)} />
          <div className="relative w-full max-w-lg bg-[#16161f] border border-white/10 rounded-2xl shadow-[0_0_40px_rgba(0,0,0,0.5)] overflow-hidden">
            <div className="p-6 border-b border-white/5 bg-white/5 flex items-start justify-between">
              <div>
                <div className="font-mono text-indigo-400 font-semibold mb-1">{selectedContact.value}</div>
                <p className="text-sm text-gray-400">{selectedContact.company_name || "Empresa desconocida"}</p>
              </div>
              <button onClick={() => setSelectedContact(null)} className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div className="p-6 flex flex-col gap-4">
              <div className="flex gap-2">
                <span className="bg-white/5 text-gray-400 border border-white/10 px-2 py-1 rounded text-[10px] uppercase font-bold tracking-wider">{selectedContact.type || "email"}</span>
                {selectedContact.method && <span className="bg-white/5 text-gray-400 border border-white/10 px-2 py-1 rounded text-[10px] uppercase font-bold tracking-wider">{selectedContact.method}</span>}
              </div>
              {selectedContact.offers.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">Ofertas asociadas</div>
                  <div className="flex flex-col gap-2">
                    {selectedContact.offers.map(o => (
                      <div key={o.id} className="flex items-center justify-between gap-3 bg-white/5 rounded-lg px-3 py-2">
                        {o.url ? (
                          <a href={o.url} target="_blank" rel="noopener noreferrer" className="text-sm text-gray-300 hover:text-indigo-400 truncate font-medium flex-1">{o.title}</a>
                        ) : (
                          <span className="text-sm text-gray-300 truncate font-medium flex-1">{o.title}</span>
                        )}
                        <span className="text-xs text-gray-500 shrink-0">{o.location || "—"}</span>
                        <span className={`text-[10px] font-bold tracking-wider px-2 py-0.5 rounded shrink-0 border ${o.relevance_score >= 0.8 ? "bg-green-500/10 text-green-400 border-green-500/20" : "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}>
                          {(o.relevance_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {selectedContact.company_website && (
              <div className="px-6 pb-6">
                <a href={selectedContact.company_website} target="_blank" rel="noopener noreferrer" className="w-full text-center block px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-colors">Ver empresa</a>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Application Detail Modal */}
      {selectedApplication && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 animate-fade-in">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedApplication(null)} />
          <div className="relative w-full max-w-lg bg-[#16161f] border border-white/10 rounded-2xl shadow-[0_0_40px_rgba(0,0,0,0.5)] overflow-hidden">
            <div className="p-6 border-b border-white/5 bg-white/5 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold text-white mb-1">{selectedApplication.job_title || "Candidatura espontánea"}</h2>
                <p className="text-sm text-indigo-400 font-medium">{selectedApplication.company_name}</p>
              </div>
              <button onClick={() => setSelectedApplication(null)} className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
              </button>
            </div>
            <div className="p-6 flex flex-col gap-4">
              <div className="flex flex-wrap gap-2">
                <span className={`px-2 py-1 rounded-md text-[10px] uppercase tracking-wider font-bold ${STATUS_COLORS[selectedApplication.status] || "bg-gray-500/10 text-gray-400 border border-gray-500/20"}`}>
                  {selectedApplication.status}
                </span>
                {selectedApplication.offer_source && (
                  <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded ${SOURCE_COLORS[selectedApplication.offer_source] || SOURCE_COLORS.seed}`}>
                    {selectedApplication.offer_source}
                  </span>
                )}
                {selectedApplication.relevance_score != null && (
                  <span className={`px-2 py-1 rounded text-xs font-bold border ${selectedApplication.relevance_score >= 0.8 ? "bg-green-500/10 text-green-400 border-green-500/20" : selectedApplication.relevance_score >= 0.65 ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" : "bg-gray-500/10 text-gray-400 border-gray-500/20"}`}>
                    {(selectedApplication.relevance_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Ubicación</div>
                  <div className="text-gray-300">{selectedApplication.offer_location || "—"}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Enviada</div>
                  <div className="text-gray-300 font-mono">{selectedApplication.sent_at ? new Date(selectedApplication.sent_at).toLocaleDateString("es-ES") : "—"}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Método</div>
                  <div className="text-gray-300 capitalize">{selectedApplication.method}</div>
                </div>
              </div>
            </div>
            <div className="p-5 border-t border-white/5 bg-black/20 flex justify-between gap-3">
              {selectedApplication.job_offer_id && (
                <button
                  onClick={async () => {
                    const offer = offers.find(o => o.id === selectedApplication.job_offer_id);
                    if (offer) {
                      await handleToggleSent(offer);
                    } else {
                      await unmarkOfferSent(selectedApplication.job_offer_id!);
                      setApplications(prev => prev.filter(a => a.id !== selectedApplication.id));
                    }
                    setSelectedApplication(null);
                  }}
                  className="px-4 py-2 text-sm font-medium text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-xl transition-colors"
                >
                  Desmarcar como enviada
                </button>
              )}
              <div className="flex gap-2 ml-auto">
                <button onClick={() => setSelectedApplication(null)} className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-colors">
                  Cerrar
                </button>
                {selectedApplication.offer_url && (
                  <a href={selectedApplication.offer_url} target="_blank" rel="noopener noreferrer" className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-all flex items-center gap-2">
                    Ver oferta <ChevronRight className="w-4 h-4" />
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
