"use client";

import { useEffect, useState } from "react";
import { Building2, Briefcase, Send, Users, RefreshCw, Play, Check } from "lucide-react";
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
}

interface Contact {
  id: string;
  value: string;
  type: string | null;
  method: string | null;
  company_name: string | null;
  company_website: string | null;
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
  sent: "bg-blue-100 text-blue-800",
  replied: "bg-yellow-100 text-yellow-800",
  interview: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  pending: "bg-gray-100 text-gray-700",
  withdrawn: "bg-gray-100 text-gray-500",
};

function StatCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: number; color: string }) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-2xl font-bold text-gray-900">{value}</div>
        <div className="text-sm text-gray-500">{label}</div>
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
  const [tab, setTab] = useState<"companies" | "offers" | "contacts" | "applications" | "pending">("offers");
  const [countryFilter, setCountryFilter] = useState("ES");
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState("");

  const load = async () => {
    const [s, c, o, ct, a, p] = await Promise.all([
      fetchStats(),
      fetchCompanies({ country: countryFilter || undefined }),
      fetchOffers(true),
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

  useEffect(() => { load(); }, [countryFilter]);

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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Job Hunter Spain</h1>
            <p className="text-sm text-gray-500">Automatización de candidaturas tech</p>
          </div>
          <div className="flex items-center gap-3">
            {actionMsg && (
              <span className="text-sm text-blue-600 font-medium animate-pulse bg-blue-50 px-3 py-1.5 rounded-lg">{actionMsg}</span>
            )}
            <div className="flex items-center gap-1.5 bg-gray-100 p-1 rounded-xl">
              <button
                onClick={() => handleScrape("seed")}
                disabled={loading}
                title="Recargar empresas seed"
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-600 hover:bg-white hover:text-gray-900 hover:shadow-sm rounded-lg transition-all disabled:opacity-40"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Seed
              </button>
              <button
                onClick={() => handleScrape("tecnoempleo")}
                disabled={loading}
                title="Scraping de nuevas ofertas en Tecnoempleo"
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-600 hover:bg-white hover:text-gray-900 hover:shadow-sm rounded-lg transition-all disabled:opacity-40"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Tecnoempleo
              </button>
              <button
                onClick={() => handleScrape("contacts")}
                disabled={loading}
                title="Extraer emails de contacto de webs de empresas"
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-600 hover:bg-white hover:text-gray-900 hover:shadow-sm rounded-lg transition-all disabled:opacity-40"
              >
                <Users className="w-3.5 h-3.5" /> Contactos
              </button>
            </div>
            <button
              onClick={handleApply}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-xl shadow-sm hover:shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              title="Genera borradores para revisar antes de enviar"
            >
              <Play className="w-4 h-4 fill-white" /> Generar borradores
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard icon={Building2} label="Empresas" value={stats.companies} color="bg-blue-50 text-blue-600" />
            <StatCard icon={Briefcase} label="Ofertas" value={stats.job_offers} color="bg-purple-50 text-purple-600" />
            <StatCard icon={Briefcase} label="Relevantes" value={stats.relevant_offers} color="bg-green-50 text-green-600" />
            <StatCard icon={Send} label="Enviadas" value={stats.applications_sent} color="bg-orange-50 text-orange-600" />
            <StatCard icon={Users} label="Contactos" value={stats.contacts_found} color="bg-teal-50 text-teal-600" />
          </div>
        )}

        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
          <button onClick={() => setTab("offers")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "offers" ? "bg-white shadow-sm font-medium" : "text-gray-600 hover:text-gray-900"}`}>
            Ofertas relevantes ({offers.length})
          </button>
          <button onClick={() => setTab("companies")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "companies" ? "bg-white shadow-sm font-medium" : "text-gray-600 hover:text-gray-900"}`}>
            Empresas ({companies.length})
          </button>
          <button onClick={() => setTab("contacts")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "contacts" ? "bg-white shadow-sm font-medium" : "text-gray-600 hover:text-gray-900"}`}>
            Contactos ({contacts.length})
          </button>
          <button onClick={() => setTab("applications")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "applications" ? "bg-white shadow-sm font-medium" : "text-gray-600 hover:text-gray-900"}`}>
            Candidaturas ({applications.length})
          </button>
          <button onClick={() => setTab("pending")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "pending" ? "bg-white shadow-sm font-medium" : "text-gray-600 hover:text-gray-900"}`}>
            Pendientes ({pendingApps.length}){pendingApps.length > 0 && <span className="ml-1.5 w-2 h-2 rounded-full bg-amber-400 inline-block" />}
          </button>
        </div>

        {tab === "offers" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600 uppercase text-xs tracking-wide">
                  <tr>
                    <th className="text-left px-4 py-3">Oferta</th>
                    <th className="text-left px-4 py-3">Empresa</th>
                    <th className="text-left px-4 py-3">Ubicación</th>
                    <th className="text-right px-4 py-3">Score</th>
                    <th className="text-left px-4 py-3">Link</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {offers.map((o) => (
                    <tr key={o.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-gray-900 max-w-xs">
                        {o.url ? (
                          <a href={o.url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600 hover:underline">{o.title}</a>
                        ) : o.title}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{o.company_name || "—"}</td>
                      <td className="px-4 py-3 text-gray-500">{o.location || "—"}</td>
                      <td className="px-4 py-3 text-right">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${o.relevance_score >= 0.8 ? "bg-green-100 text-green-700" : o.relevance_score >= 0.65 ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-600"}`}>
                          {(o.relevance_score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {o.url && (
                          <a href={o.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">Ver →</a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "companies" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex items-center gap-3">
              <span className="text-sm font-medium text-gray-700">País:</span>
              <select
                value={countryFilter}
                onChange={(e) => setCountryFilter(e.target.value)}
                className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Todos</option>
                <option value="ES">España</option>
                <option value="US">USA</option>
                <option value="UK">UK</option>
              </select>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600 uppercase text-xs tracking-wide">
                  <tr>
                    <th className="text-left px-4 py-3">Empresa</th>
                    <th className="text-left px-4 py-3">Sector</th>
                    <th className="text-left px-4 py-3">País</th>
                    <th className="text-right px-4 py-3">Ofertas</th>
                    <th className="text-right px-4 py-3">Enviadas</th>
                    <th className="text-left px-4 py-3">Empleos</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {companies.map((c) => (
                    <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                      <td className="px-4 py-3">
                        <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full text-xs">{c.sector}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{c.country}</td>
                      <td className="px-4 py-3 text-right text-gray-700 tabular-nums">{c.offer_count}</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        <span className={c.application_count > 0 ? "text-green-600 font-medium" : "text-gray-400"}>
                          {c.application_count}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {c.careers_url && (
                          <a href={c.careers_url} target="_blank" rel="noopener noreferrer"
                            className="text-blue-600 hover:underline text-xs">Ver →</a>
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
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            {contacts.length === 0 ? (
              <div className="p-12 text-center text-gray-400">
                <Users className="w-8 h-8 mx-auto mb-3 opacity-30" />
                <p className="font-medium">Sin contactos aún</p>
                <p className="text-sm mt-1">Pulsa el botón &quot;Contactos&quot; para extraer emails de las webs de empresas</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600 uppercase text-xs tracking-wide">
                    <tr>
                      <th className="text-left px-4 py-3">Contacto</th>
                      <th className="text-left px-4 py-3">Tipo</th>
                      <th className="text-left px-4 py-3">Empresa</th>
                      <th className="text-left px-4 py-3">Método</th>
                      <th className="text-left px-4 py-3">Web</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {contacts.map((ct) => (
                      <tr key={ct.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-mono text-xs text-blue-700">{ct.value}</td>
                        <td className="px-4 py-3">
                          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">{ct.type || "email"}</span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{ct.company_name || "—"}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">{ct.method || "—"}</td>
                        <td className="px-4 py-3">
                          {ct.company_website && (
                            <a href={ct.company_website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">Ver →</a>
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
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            {applications.length === 0 ? (
              <div className="p-12 text-center text-gray-400">
                <Send className="w-8 h-8 mx-auto mb-3 opacity-30" />
                <p className="font-medium">Aún no hay candidaturas enviadas</p>
                <p className="text-sm mt-1">Extrae contactos y pulsa &quot;Enviar candidaturas&quot;</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600 uppercase text-xs tracking-wide">
                    <tr>
                      <th className="text-left px-4 py-3">Empresa</th>
                      <th className="text-left px-4 py-3">Puesto</th>
                      <th className="text-left px-4 py-3">Estado</th>
                      <th className="text-left px-4 py-3">Método</th>
                      <th className="text-left px-4 py-3">Fecha</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {applications.map((a) => (
                      <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-medium text-gray-900">{a.company_name}</td>
                        <td className="px-4 py-3 text-gray-600">{a.job_title || "Candidatura espontánea"}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[a.status] || "bg-gray-100 text-gray-600"}`}>
                            {a.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-500 capitalize">{a.method}</td>
                        <td className="px-4 py-3 text-gray-500">
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
        {tab === "pending" && (
          <div className="space-y-4">
            {pendingApps.length === 0 ? (
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
                <Check className="w-8 h-8 mx-auto mb-3 opacity-30" />
                <p className="font-medium">No hay candidaturas pendientes de revisión</p>
                <p className="text-sm mt-1">Pulsa &quot;Generar borradores&quot; para crear candidaturas desde las ofertas relevantes</p>
              </div>
            ) : (
              <>
                <p className="text-sm text-gray-500">{pendingApps.length} candidatura{pendingApps.length !== 1 ? "s" : ""} esperando aprobación</p>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {pendingApps.map((a) => (
                    <PendingCard key={a.id} app={a} onAction={load} />
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
