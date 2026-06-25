"use client";

import { useState } from "react";
import { Check, X, FileText } from "lucide-react";
import { approveApplication, rejectApplication, updateCoverLetter, type PendingApplication } from "@/lib/api";

interface PendingCardProps {
  app: PendingApplication;
  onAction: () => void;
}

const PROFILE_BADGE: Record<string, { label: string; className: string }> = {
  sap:           { label: "SAP",    className: "bg-blue-100 text-blue-700" },
  ia_dev:        { label: "IA/Dev", className: "bg-purple-100 text-purple-700" },
  manual_review: { label: "Revisar",className: "bg-yellow-100 text-yellow-700" },
};

export function PendingCard({ app, onAction }: PendingCardProps) {
  const currentLetter = app.cover_letter_edited ?? app.cover_letter_used ?? "";
  const [body, setBody] = useState(currentLetter);
  const [saved, setSaved] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setBusy(true);
    try {
      await updateCoverLetter(app.id, body);
      setSaved(true);
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async () => {
    setError(null);
    if (!saved) await handleSave();
    setBusy(true);
    try {
      const result = await approveApplication(app.id);
      if (!result.success) {
        setError("Error al enviar. Revisa el límite diario o la conexión SMTP.");
        return;
      }
      onAction();
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    setBusy(true);
    try {
      await rejectApplication(app.id);
      onAction();
    } finally {
      setBusy(false);
    }
  };

  const badge = PROFILE_BADGE[app.cv_profile ?? "ia_dev"] ?? PROFILE_BADGE["ia_dev"];
  const cvFile = app.cv_profile === "sap" ? "cv_sap.pdf" : "cv_ia.pdf";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900">{app.company_name ?? "—"}</p>
          <p className="text-sm text-gray-500">{app.job_title ?? "Candidatura espontánea"}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.className}`}>
            {badge.label}
          </span>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-mono">
            {cvFile}
          </span>
        </div>
      </div>

      <div className="text-xs text-gray-400 flex items-center gap-1.5">
        <FileText className="w-3 h-3 flex-shrink-0" />
        <span className="font-mono truncate">{app.contact_value ?? "—"}</span>
      </div>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Carta de presentación
          </span>
          {!saved && (
            <button
              onClick={handleSave}
              disabled={busy}
              className="text-xs text-blue-600 hover:underline disabled:opacity-40"
            >
              Guardar cambios
            </button>
          )}
          {saved && body !== currentLetter && (
            <span className="text-xs text-green-600">Guardado</span>
          )}
        </div>
        <textarea
          value={body}
          onChange={(e) => { setBody(e.target.value); setSaved(false); }}
          rows={10}
          disabled={busy}
          className="w-full text-xs font-mono text-gray-700 border border-gray-200 rounded-lg p-3 resize-y focus:outline-none focus:ring-2 focus:ring-blue-400 bg-gray-50 disabled:opacity-60"
        />
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button
          onClick={handleReject}
          disabled={busy}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-red-600 border border-red-200 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
        >
          <X className="w-4 h-4" /> Rechazar
        </button>
        <button
          onClick={handleApprove}
          disabled={busy}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-green-600 hover:bg-green-700 text-white rounded-lg shadow-sm transition-colors disabled:opacity-40"
        >
          <Check className="w-4 h-4" /> {busy ? "Enviando…" : "Aprobar y enviar"}
        </button>
      </div>
    </div>
  );
}
