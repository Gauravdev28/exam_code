import React, { useState, useEffect } from 'react';
import { RetentionAPI } from '../../api/retention';
import {
  RetentionMetrics,
  RetentionPolicy,
  LegalHold,
  RetentionTombstone,
  PurgePreviewResponse,
  PurgeExecutionSummary,
} from '../../types/retention';

export const AdminRetentionDashboardPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'operations' | 'policies' | 'holds' | 'tombstones'>('operations');
  const [metrics, setMetrics] = useState<RetentionMetrics | null>(null);
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [holds, setHolds] = useState<LegalHold[]>([]);
  const [tombstones, setTombstones] = useState<RetentionTombstone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Purge Preview & Modal State
  const [previewData, setPreviewData] = useState<PurgePreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [executingPurge, setExecutingPurge] = useState(false);
  const [purgeSummary, setPurgeSummary] = useState<PurgeExecutionSummary | null>(null);
  const [countdown, setCountdown] = useState<number>(300);

  // Policy Modal
  const [showPolicyModal, setShowPolicyModal] = useState(false);
  const [policyForm, setPolicyForm] = useState({
    name: '',
    scope: 'INSTITUTION' as 'INSTITUTION' | 'ASSESSMENT',
    assessment: '',
    detailed_data_ttl_days: 30,
    proctoring_evidence_ttl_days: 30,
    report_retention_ttl_days: 365,
  });

  // Legal Hold Modal
  const [showHoldModal, setShowHoldModal] = useState(false);
  const [holdForm, setHoldForm] = useState({
    title: '',
    case_reference: '',
    reason: '',
    scope: 'ATTEMPT' as 'ATTEMPT' | 'STUDENT' | 'ASSESSMENT',
    attempt: '',
    student: '',
    assessment: '',
  });

  // Release Hold Modal
  const [releasingHoldId, setReleasingHoldId] = useState<string | null>(null);
  const [releaseReason, setReleaseReason] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [m, p, h, t] = await Promise.all([
        RetentionAPI.getMetrics(),
        RetentionAPI.getPolicies(),
        RetentionAPI.getLegalHolds({ status: 'ACTIVE' }),
        RetentionAPI.getTombstones(),
      ]);
      setMetrics(m);
      setPolicies(p);
      setHolds(h.results || []);
      setTombstones(t.results || []);
    } catch (err: any) {
      setError(err?.error?.message || err?.message || 'Failed to load retention data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Preview countdown timer
  useEffect(() => {
    let timer: any;
    if (previewData && countdown > 0) {
      timer = setInterval(() => setCountdown((c) => c - 1), 1000);
    } else if (countdown === 0 && previewData) {
      setPreviewData(null);
      alert('Purge preview token has expired. Please generate a new preview.');
    }
    return () => clearInterval(timer);
  }, [previewData, countdown]);

  const handleGeneratePreview = async () => {
    try {
      setPreviewLoading(true);
      setPurgeSummary(null);
      const preview = await RetentionAPI.previewPurge();
      setPreviewData(preview);
      setCountdown(preview.valid_for_seconds || 300);
    } catch (err: any) {
      alert(err?.error?.message || err?.message || 'Failed to generate preview.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleExecutePurge = async () => {
    if (!previewData) return;
    if (!window.confirm('CRITICAL ACTION: This will permanently delete student answers, code submissions, and proctoring telemetry. This action is cryptographically sealed and IRREVERSIBLE. Proceed?')) {
      return;
    }

    try {
      setExecutingPurge(true);
      const summary = await RetentionAPI.executePurge(previewData.preview_token);
      setPurgeSummary(summary);
      setPreviewData(null);
      await loadData();
    } catch (err: any) {
      alert(err?.error?.message || err?.message || 'Purge execution failed.');
    } finally {
      setExecutingPurge(false);
    }
  };

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await RetentionAPI.createPolicy({
        ...policyForm,
        assessment: policyForm.scope === 'ASSESSMENT' ? policyForm.assessment : null,
      });
      setShowPolicyModal(false);
      await loadData();
    } catch (err: any) {
      alert(err?.error?.message || err?.message || 'Failed to create policy.');
    }
  };

  const handleCreateHold = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await RetentionAPI.createLegalHold({
        ...holdForm,
        attempt: holdForm.scope === 'ATTEMPT' ? holdForm.attempt : undefined,
        student: holdForm.scope === 'STUDENT' ? holdForm.student : undefined,
        assessment: holdForm.scope === 'ASSESSMENT' ? holdForm.assessment : undefined,
      });
      setShowHoldModal(false);
      await loadData();
    } catch (err: any) {
      alert(err?.error?.message || err?.message || 'Failed to place hold.');
    }
  };

  const handleReleaseHold = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!releasingHoldId || !releaseReason) return;
    try {
      await RetentionAPI.releaseLegalHold(releasingHoldId, releaseReason);
      setReleasingHoldId(null);
      setReleaseReason('');
      await loadData();
    } catch (err: any) {
      alert(err?.error?.message || err?.message || 'Failed to release hold.');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Data Retention & Privacy Compliance</h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Automated Engine Active (02:00 UTC)
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Automated TTL lifecycle, scoped legal hold freezing, physical disk sanitization, and GDPR/FERPA DSAR pipelines.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => handleGeneratePreview()}
            disabled={previewLoading}
            className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-rose-900/20 transition-all flex items-center gap-2"
          >
            {previewLoading ? 'Generating Preview...' : 'Dry-Run Purge Preview'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
          {error}
        </div>
      )}

      {/* Metrics Banner */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 my-8">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs text-slate-400 font-medium">Reclaimed Storage</span>
            <div className="text-xl font-bold text-emerald-400 mt-1">{metrics.confirmed_mb_reclaimed} MB</div>
            <span className="text-[10px] text-slate-500">Confirmed unlinked</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs text-slate-400 font-medium">Due for Purge Today</span>
            <div className="text-xl font-bold text-amber-400 mt-1">{metrics.due_today_count}</div>
            <span className="text-[10px] text-slate-500">Expired attempts</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs text-slate-400 font-medium">Upcoming (7 Days)</span>
            <div className="text-xl font-bold text-sky-400 mt-1">{metrics.upcoming_purges_7d_count}</div>
            <span className="text-[10px] text-slate-500">Scheduled pipeline</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs text-slate-400 font-medium">Active Legal Holds</span>
            <div className="text-xl font-bold text-indigo-400 mt-1">{metrics.active_legal_holds_count}</div>
            <span className="text-[10px] text-slate-500">Frozen against purge</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs text-slate-400 font-medium">Sealed Tombstones</span>
            <div className="text-xl font-bold text-purple-400 mt-1">{metrics.total_tombstones_count}</div>
            <span className="text-[10px] text-slate-500">HMAC-SHA256 audits</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
            <span className="text-xs text-slate-400 font-medium">Active Policies</span>
            <div className="text-xl font-bold text-slate-200 mt-1">{metrics.active_policies_count}</div>
            <span className="text-[10px] text-slate-500">Configured rules</span>
          </div>
        </div>
      )}

      {/* Execution Summary Notification */}
      {purgeSummary && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm flex items-center justify-between">
          <div>
            <span className="font-semibold">Purge Execution Succeeded:</span> Evaluated {purgeSummary.evaluated_count} attempts.
            Purged: <span className="font-bold text-emerald-400">{purgeSummary.purged_count}</span> |
            Deferred Holds: <span className="font-bold text-amber-400">{purgeSummary.deferred_hold_count}</span> |
            Deferred Exports: <span className="font-bold text-sky-400">{purgeSummary.deferred_export_count}</span>
          </div>
          <button onClick={() => setPurgeSummary(null)} className="text-xs text-emerald-400 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-800 mb-6">
        {[
          { id: 'operations', label: 'Purge Operations & Candidates' },
          { id: 'policies', label: 'Retention Policies' },
          { id: 'holds', label: 'Legal Holds & Freezes' },
          { id: 'tombstones', label: 'Immutable Tombstones' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-brand-500 text-brand-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Operations */}
      {activeTab === 'operations' && (
        <div className="space-y-6">
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
            <h3 className="text-base font-semibold text-white mb-2">Automated Retention Engine Status</h3>
            <p className="text-sm text-slate-400">
              Candidate test attempts whose detailed data retention window has elapsed are processed nightly at 02:00 UTC.
              Scores, rankings, pass/fail status, and official completion certificates are permanently preserved in the Historical Result Summary ledger.
            </p>
            <div className="mt-4 flex gap-4">
              <button
                onClick={() => handleGeneratePreview()}
                disabled={previewLoading}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-all"
              >
                {previewLoading ? 'Inspecting Database...' : 'Run Purge Dry-Run Preview'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Policies */}
      {activeTab === 'policies' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-base font-semibold text-white">Configured Policies</h3>
            <button
              onClick={() => setShowPolicyModal(true)}
              className="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-medium"
            >
              + Create Policy
            </button>
          </div>
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950 text-xs uppercase text-slate-400 border-b border-slate-800 font-mono">
                <tr>
                  <th className="px-4 py-3">Policy Name</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Scope</th>
                  <th className="px-4 py-3">Detailed TTL</th>
                  <th className="px-4 py-3">Proctoring TTL</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {policies.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-800/20">
                    <td className="px-4 py-3 font-medium text-white">{p.name}</td>
                    <td className="px-4 py-3 font-mono text-xs">v{p.version}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-300 font-mono">
                        {p.scope}
                      </span>
                    </td>
                    <td className="px-4 py-3">{p.detailed_data_ttl_days} Days</td>
                    <td className="px-4 py-3">{p.proctoring_evidence_ttl_days} Days</td>
                    <td className="px-4 py-3">
                      <span className="text-emerald-400 text-xs">● Active</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Legal Holds */}
      {activeTab === 'holds' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-base font-semibold text-white">Active Legal Holds</h3>
            <button
              onClick={() => setShowHoldModal(true)}
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
            >
              + Place Legal Hold
            </button>
          </div>
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950 text-xs uppercase text-slate-400 border-b border-slate-800 font-mono">
                <tr>
                  <th className="px-4 py-3">Title / Reference</th>
                  <th className="px-4 py-3">Scope</th>
                  <th className="px-4 py-3">Reason</th>
                  <th className="px-4 py-3">Placed By</th>
                  <th className="px-4 py-3">Placed At</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {holds.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                      Zero active legal holds. All eligible records follow standard policy TTL.
                    </td>
                  </tr>
                ) : (
                  holds.map((h) => (
                    <tr key={h.id} className="hover:bg-slate-800/20">
                      <td className="px-4 py-3">
                        <div className="font-medium text-white">{h.title}</div>
                        <div className="text-xs text-slate-400 font-mono">{h.case_reference}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs bg-indigo-500/20 text-indigo-300 font-mono">
                          {h.scope}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs max-w-xs truncate">{h.reason}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{h.placed_by_email}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{new Date(h.placed_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setReleasingHoldId(h.id)}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-rose-300 text-xs rounded border border-rose-500/20"
                        >
                          Release Hold
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Tombstones */}
      {activeTab === 'tombstones' && (
        <div className="space-y-6">
          <h3 className="text-base font-semibold text-white">Immutable Retention Tombstones</h3>
          <p className="text-xs text-slate-400">
            Cryptographically sealed audit records proving completion of database scrubbing and 100% physical disk unlinking.
          </p>
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950 text-xs uppercase text-slate-400 border-b border-slate-800 font-mono">
                <tr>
                  <th className="px-4 py-3">Student EUID</th>
                  <th className="px-4 py-3">Assessment Title</th>
                  <th className="px-4 py-3">Purged At</th>
                  <th className="px-4 py-3">Reclaimed</th>
                  <th className="px-4 py-3">SHA-256 Audit Signature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                {tombstones.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/20">
                    <td className="px-4 py-3 text-white font-semibold">{t.student_euid}</td>
                    <td className="px-4 py-3 font-sans text-slate-300">{t.assessment_title_snapshot}</td>
                    <td className="px-4 py-3 text-slate-400">{new Date(t.purged_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-emerald-400">{(t.confirmed_bytes_reclaimed / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-3 text-slate-400 truncate max-w-xs" title={t.sha256_audit_proof}>
                      {t.sha256_audit_proof.substring(0, 16)}...
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Purge Preview Modal */}
      {previewData && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-rose-500/30 rounded-xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span className="text-rose-500">⚠</span> Authoritative Purge Preview
                </h3>
                <span className="text-xs text-slate-400">
                  Signed Preview Token expires in: <strong className="text-amber-400 font-mono">{countdown}s</strong>
                </span>
              </div>
              <button onClick={() => setPreviewData(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-xs text-rose-300">
              Permanent Deletion: Executing this action scrubs candidate student answers, source code, and proctoring telemetry. Official test results will be sealed into HistoricalResultSummary with details_purged=true.
            </div>

            <div className="text-sm text-slate-300">
              Eligible Attempts for Deletion: <strong className="text-white">{previewData.eligible_count}</strong> of {previewData.total_candidates} evaluated.
            </div>

            <div className="max-h-60 overflow-y-auto border border-slate-800 rounded-lg divide-y divide-slate-800 text-xs">
              {previewData.candidates.map((c) => (
                <div key={c.attempt_id} className="p-3 flex justify-between items-center">
                  <div>
                    <div className="font-semibold text-white">{c.assessment_title}</div>
                    <div className="text-slate-400 font-mono">EUID: {c.student_euid}</div>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${c.is_eligible ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                    {c.is_eligible ? 'ELIGIBLE' : c.current_purge_state}
                  </span>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                onClick={() => setPreviewData(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleExecutePurge}
                disabled={executingPurge || previewData.eligible_count === 0}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 disabled:bg-rose-900/50 text-white rounded-lg text-sm font-semibold shadow-lg shadow-rose-900/30"
              >
                {executingPurge ? 'Scrubbing Database & Queueing Cleanups...' : 'Execute Irreversible Purge'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Place Legal Hold Modal */}
      {showHoldModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <form onSubmit={handleCreateHold} className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white">Place New Legal Hold</h3>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-slate-400 text-xs mb-1">Title</label>
                <input
                  type="text"
                  required
                  value={holdForm.title}
                  onChange={(e) => setHoldForm({ ...holdForm, title: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                  placeholder="e.g. Academic Integrity Investigation"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Case Reference</label>
                <input
                  type="text"
                  required
                  value={holdForm.case_reference}
                  onChange={(e) => setHoldForm({ ...holdForm, case_reference: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                  placeholder="e.g. DISCIPLINE-2026-0042"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Scope</label>
                <select
                  value={holdForm.scope}
                  onChange={(e) => setHoldForm({ ...holdForm, scope: e.target.value as any })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                >
                  <option value="ATTEMPT">Attempt Scoped</option>
                  <option value="STUDENT">Student Scoped</option>
                  <option value="ASSESSMENT">Assessment Scoped</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">
                  Target UUID ({holdForm.scope})
                </label>
                <input
                  type="text"
                  required
                  value={holdForm.scope === 'ATTEMPT' ? holdForm.attempt : holdForm.scope === 'STUDENT' ? holdForm.student : holdForm.assessment}
                  onChange={(e) => {
                    if (holdForm.scope === 'ATTEMPT') setHoldForm({ ...holdForm, attempt: e.target.value });
                    else if (holdForm.scope === 'STUDENT') setHoldForm({ ...holdForm, student: e.target.value });
                    else setHoldForm({ ...holdForm, assessment: e.target.value });
                  }}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs"
                  placeholder="Target UUID..."
                />
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Formal Justification</label>
                <textarea
                  required
                  value={holdForm.reason}
                  onChange={(e) => setHoldForm({ ...holdForm, reason: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs"
                  rows={3}
                  placeholder="Detailed rationale for evidentiary freeze..."
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowHoldModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold"
              >
                Place Legal Hold
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Release Legal Hold Modal */}
      {releasingHoldId && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <form onSubmit={handleReleaseHold} className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white">Release Legal Hold</h3>
            <p className="text-xs text-slate-400">
              Releasing this hold will return all affected attempts to standard automated retention scheduling.
            </p>
            <div>
              <label className="block text-slate-400 text-xs mb-1">Release Justification</label>
              <textarea
                required
                value={releaseReason}
                onChange={(e) => setReleaseReason(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-xs"
                rows={3}
                placeholder="Reason investigation was closed or resolved..."
              />
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setReleasingHoldId(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-sm font-semibold"
              >
                Confirm Release
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Create Policy Modal */}
      {showPolicyModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <form onSubmit={handleCreatePolicy} className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white">Create Retention Policy</h3>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-slate-400 text-xs mb-1">Policy Name</label>
                <input
                  type="text"
                  required
                  value={policyForm.name}
                  onChange={(e) => setPolicyForm({ ...policyForm, name: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                  placeholder="e.g. Standard 60-Day Examination Policy"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Scope</label>
                <select
                  value={policyForm.scope}
                  onChange={(e) => setPolicyForm({ ...policyForm, scope: e.target.value as any })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                >
                  <option value="INSTITUTION">Institution Wide</option>
                  <option value="ASSESSMENT">Assessment Scoped</option>
                </select>
              </div>
              {policyForm.scope === 'ASSESSMENT' && (
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Assessment UUID</label>
                  <input
                    type="text"
                    required
                    value={policyForm.assessment}
                    onChange={(e) => setPolicyForm({ ...policyForm, assessment: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono text-xs"
                    placeholder="Assessment UUID..."
                  />
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Detailed Data TTL (Days)</label>
                  <input
                    type="number"
                    min={1}
                    max={3650}
                    required
                    value={policyForm.detailed_data_ttl_days}
                    onChange={(e) => setPolicyForm({ ...policyForm, detailed_data_ttl_days: parseInt(e.target.value) || 30 })}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Proctoring Evidence TTL (Days)</label>
                  <input
                    type="number"
                    min={1}
                    max={3650}
                    required
                    value={policyForm.proctoring_evidence_ttl_days}
                    onChange={(e) => setPolicyForm({ ...policyForm, proctoring_evidence_ttl_days: parseInt(e.target.value) || 30 })}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowPolicyModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-semibold"
              >
                Save Policy
              </button>
            </div>
          </form>
        </div>
      )}

      {loading && (
        <div className="fixed bottom-4 right-4 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-xs text-slate-400 shadow-xl flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-brand-400 animate-ping" />
          Synchronizing metrics...
        </div>
      )}
    </div>
  );
};
