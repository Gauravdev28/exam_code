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
import { PageHeader } from '../../components/common/PageHeader';
import { Tabs, TabItem } from '../../components/common/Tabs';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { ShieldCheck } from 'lucide-react';

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

  const retentionTabs: TabItem<'operations' | 'policies' | 'holds' | 'tombstones'>[] = [
    { id: 'operations', label: 'Purge Operations & Candidates' },
    { id: 'policies', label: 'Retention Policies' },
    { id: 'holds', label: 'Legal Holds & Freezes' },
    { id: 'tombstones', label: 'Immutable Tombstones' },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <PageHeader
        icon={<ShieldCheck className="w-6 h-6" />}
        title="Data Retention & Privacy Compliance"
        badge={<Badge variant="success" size="sm">Automated Engine Active (02:00 UTC)</Badge>}
        description="Automated TTL lifecycle, scoped legal hold freezing, physical disk sanitization, and GDPR/FERPA DSAR pipelines."
        actions={
          <button
            onClick={() => handleGeneratePreview()}
            disabled={previewLoading}
            className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs sm:text-sm font-semibold shadow-sm transition-all flex items-center gap-2"
          >
            {previewLoading ? 'Generating Preview...' : 'Dry-Run Purge Preview'}
          </button>
        }
      />

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm">
          {error}
        </div>
      )}

      {/* Metrics Banner */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <Card className="p-4">
            <span className="text-xs text-slate-600 font-semibold block">Reclaimed Storage</span>
            <div className="text-xl font-bold text-emerald-700 mt-1">{metrics.confirmed_mb_reclaimed} MB</div>
            <span className="text-[10px] text-slate-500 font-medium">Confirmed unlinked</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-600 font-semibold block">Due for Purge Today</span>
            <div className="text-xl font-bold text-amber-700 mt-1">{metrics.due_today_count}</div>
            <span className="text-[10px] text-slate-500 font-medium">Expired attempts</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-600 font-semibold block">Upcoming (7 Days)</span>
            <div className="text-xl font-bold text-sky-700 mt-1">{metrics.upcoming_purges_7d_count}</div>
            <span className="text-[10px] text-slate-500 font-medium">Scheduled pipeline</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-600 font-semibold block">Active Legal Holds</span>
            <div className="text-xl font-bold text-indigo-700 mt-1">{metrics.active_legal_holds_count}</div>
            <span className="text-[10px] text-slate-500 font-medium">Frozen against purge</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-600 font-semibold block">Sealed Tombstones</span>
            <div className="text-xl font-bold text-purple-700 mt-1">{metrics.total_tombstones_count}</div>
            <span className="text-[10px] text-slate-500 font-medium">HMAC-SHA256 audits</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs text-slate-600 font-semibold block">Active Policies</span>
            <div className="text-xl font-bold text-slate-900 mt-1">{metrics.active_policies_count}</div>
            <span className="text-[10px] text-slate-500 font-medium">Configured rules</span>
          </Card>
        </div>
      )}

      {/* Execution Summary Notification */}
      {purgeSummary && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between">
          <div>
            <span className="font-semibold">Purge Execution Succeeded:</span> Evaluated {purgeSummary.evaluated_count} attempts.
            Purged: <span className="font-bold text-emerald-700">{purgeSummary.purged_count}</span> |
            Deferred Holds: <span className="font-bold text-amber-700">{purgeSummary.deferred_hold_count}</span> |
            Deferred Exports: <span className="font-bold text-sky-700">{purgeSummary.deferred_export_count}</span>
          </div>
          <button onClick={() => setPurgeSummary(null)} className="text-xs text-emerald-700 font-semibold hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <Tabs
        tabs={retentionTabs}
        activeTab={activeTab}
        onChange={(tab) => setActiveTab(tab as any)}
      />

      {/* Tab 1: Operations */}
      {activeTab === 'operations' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="text-base font-bold text-slate-900 mb-2">Automated Retention Engine Status</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Candidate test attempts whose detailed data retention window has elapsed are processed nightly at 02:00 UTC.
              Scores, rankings, pass/fail status, and official completion certificates are permanently preserved in the Historical Result Summary ledger.
            </p>
            <div className="mt-4 flex gap-4">
              <button
                onClick={() => handleGeneratePreview()}
                disabled={previewLoading}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-800 rounded-lg text-xs sm:text-sm font-semibold transition-all"
              >
                {previewLoading ? 'Inspecting Database...' : 'Run Purge Dry-Run Preview'}
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* Tab 2: Policies */}
      {activeTab === 'policies' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-base font-bold text-slate-900">Configured Policies</h3>
            <button
              onClick={() => setShowPolicyModal(true)}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs sm:text-sm font-semibold shadow-sm"
            >
              + Create Policy
            </button>
          </div>
          <Card className="overflow-hidden p-0">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600 border-b border-slate-200 font-mono font-semibold">
                <tr>
                  <th className="px-4 py-3">Policy Name</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Scope</th>
                  <th className="px-4 py-3">Detailed TTL</th>
                  <th className="px-4 py-3">Proctoring TTL</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {policies.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-semibold text-slate-900">{p.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-600">v{p.version}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-700 border border-slate-200 font-mono">
                        {p.scope}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-800 font-medium">{p.detailed_data_ttl_days} Days</td>
                    <td className="px-4 py-3 text-slate-800 font-medium">{p.proctoring_evidence_ttl_days} Days</td>
                    <td className="px-4 py-3">
                      <span className="text-emerald-700 font-semibold text-xs">● Active</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}

      {/* Tab 3: Legal Holds */}
      {activeTab === 'holds' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-base font-bold text-slate-900">Active Legal Holds</h3>
            <button
              onClick={() => setShowHoldModal(true)}
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs sm:text-sm font-semibold shadow-sm"
            >
              + Place Legal Hold
            </button>
          </div>
          <Card className="overflow-hidden p-0">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600 border-b border-slate-200 font-mono font-semibold">
                <tr>
                  <th className="px-4 py-3">Title / Reference</th>
                  <th className="px-4 py-3">Scope</th>
                  <th className="px-4 py-3">Reason</th>
                  <th className="px-4 py-3">Placed By</th>
                  <th className="px-4 py-3">Placed At</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {holds.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                      Zero active legal holds. All eligible records follow standard policy TTL.
                    </td>
                  </tr>
                ) : (
                  holds.map((h) => (
                    <tr key={h.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{h.title}</div>
                        <div className="text-xs text-slate-500 font-mono">{h.case_reference}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono">
                          {h.scope}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs max-w-xs truncate text-slate-700">{h.reason}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{h.placed_by_email}</td>
                      <td className="px-4 py-3 text-xs text-slate-500">{new Date(h.placed_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setReleasingHoldId(h.id)}
                          className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs rounded border border-rose-200 font-semibold"
                        >
                          Release Hold
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </Card>
        </div>
      )}

      {/* Tab 4: Tombstones */}
      {activeTab === 'tombstones' && (
        <div className="space-y-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">Immutable Retention Tombstones</h3>
            <p className="text-xs text-slate-500 mt-1">
              Cryptographically sealed audit records proving completion of database scrubbing and 100% physical disk unlinking.
            </p>
          </div>
          <Card className="overflow-hidden p-0">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase text-slate-600 border-b border-slate-200 font-mono font-semibold">
                <tr>
                  <th className="px-4 py-3">Student EUID</th>
                  <th className="px-4 py-3">Assessment Title</th>
                  <th className="px-4 py-3">Purged At</th>
                  <th className="px-4 py-3">Reclaimed</th>
                  <th className="px-4 py-3">SHA-256 Audit Signature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-xs">
                {tombstones.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 text-slate-900 font-semibold">{t.student_euid}</td>
                    <td className="px-4 py-3 font-sans text-slate-800">{t.assessment_title_snapshot}</td>
                    <td className="px-4 py-3 text-slate-500">{new Date(t.purged_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-emerald-700 font-semibold">{(t.confirmed_bytes_reclaimed / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-3 text-slate-500 truncate max-w-xs" title={t.sha256_audit_proof}>
                      {t.sha256_audit_proof.substring(0, 16)}...
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}

      {/* Purge Preview Modal */}
      {previewData && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-200 pb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <span className="text-rose-600">⚠</span> Authoritative Purge Preview
                </h3>
                <span className="text-xs text-slate-500">
                  Signed Preview Token expires in: <strong className="text-amber-700 font-mono">{countdown}s</strong>
                </span>
              </div>
              <button onClick={() => setPreviewData(null)} className="text-slate-400 hover:text-slate-700 font-bold">✕</button>
            </div>

            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800">
              Permanent Deletion: Executing this action scrubs candidate student answers, source code, and proctoring telemetry. Official test results will be sealed into HistoricalResultSummary with details_purged=true.
            </div>

            <div className="text-sm text-slate-700">
              Eligible Attempts for Deletion: <strong className="text-slate-900">{previewData.eligible_count}</strong> of {previewData.total_candidates} evaluated.
            </div>

            <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-xl divide-y divide-slate-100 text-xs">
              {previewData.candidates.map((c) => (
                <div key={c.attempt_id} className="p-3 flex justify-between items-center">
                  <div>
                    <div className="font-semibold text-slate-900">{c.assessment_title}</div>
                    <div className="text-slate-500 font-mono">EUID: {c.student_euid}</div>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${c.is_eligible ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
                    {c.is_eligible ? 'ELIGIBLE' : c.current_purge_state}
                  </span>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
              <button
                onClick={() => setPreviewData(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleExecutePurge}
                disabled={executingPurge || previewData.eligible_count === 0}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-sm"
              >
                {executingPurge ? 'Scrubbing Database & Queueing Cleanups...' : 'Execute Irreversible Purge'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Place Legal Hold Modal */}
      {showHoldModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleCreateHold} className="bg-white border border-slate-200 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-slate-900">Place New Legal Hold</h3>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-slate-700 font-semibold text-xs mb-1">Title</label>
                <input
                  type="text"
                  required
                  value={holdForm.title}
                  onChange={(e) => setHoldForm({ ...holdForm, title: e.target.value })}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                  placeholder="e.g. Academic Integrity Investigation"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold text-xs mb-1">Case Reference</label>
                <input
                  type="text"
                  required
                  value={holdForm.case_reference}
                  onChange={(e) => setHoldForm({ ...holdForm, case_reference: e.target.value })}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                  placeholder="e.g. DISCIPLINE-2026-0042"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold text-xs mb-1">Scope</label>
                <select
                  value={holdForm.scope}
                  onChange={(e) => setHoldForm({ ...holdForm, scope: e.target.value as any })}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500 font-medium"
                >
                  <option value="ATTEMPT">Attempt Scoped</option>
                  <option value="STUDENT">Student Scoped</option>
                  <option value="ASSESSMENT">Assessment Scoped</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-700 font-semibold text-xs mb-1">
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
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                  placeholder="Target UUID..."
                />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold text-xs mb-1">Formal Justification</label>
                <textarea
                  required
                  value={holdForm.reason}
                  onChange={(e) => setHoldForm({ ...holdForm, reason: e.target.value })}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                  rows={3}
                  placeholder="Detailed rationale for evidentiary freeze..."
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setShowHoldModal(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm"
              >
                Place Legal Hold
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Release Legal Hold Modal */}
      {releasingHoldId && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleReleaseHold} className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-slate-900">Release Legal Hold</h3>
            <p className="text-xs text-slate-500">
              Releasing this hold will return all affected attempts to standard automated retention scheduling.
            </p>
            <div>
              <label className="block text-slate-700 font-semibold text-xs mb-1">Release Justification</label>
              <textarea
                required
                value={releaseReason}
                onChange={(e) => setReleaseReason(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                rows={3}
                placeholder="Reason investigation was closed or resolved..."
              />
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setReleasingHoldId(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-sm"
              >
                Confirm Release
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Create Policy Modal */}
      {showPolicyModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={handleCreatePolicy} className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-slate-900">Create Retention Policy</h3>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-slate-700 font-semibold text-xs mb-1">Policy Name</label>
                <input
                  type="text"
                  required
                  value={policyForm.name}
                  onChange={(e) => setPolicyForm({ ...policyForm, name: e.target.value })}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                  placeholder="e.g. Standard 60-Day Examination Policy"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold text-xs mb-1">Scope</label>
                <select
                  value={policyForm.scope}
                  onChange={(e) => setPolicyForm({ ...policyForm, scope: e.target.value as any })}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500 font-medium"
                >
                  <option value="INSTITUTION">Institution Wide</option>
                  <option value="ASSESSMENT">Assessment Scoped</option>
                </select>
              </div>
              {policyForm.scope === 'ASSESSMENT' && (
                <div>
                  <label className="block text-slate-700 font-semibold text-xs mb-1">Assessment UUID</label>
                  <input
                    type="text"
                    required
                    value={policyForm.assessment}
                    onChange={(e) => setPolicyForm({ ...policyForm, assessment: e.target.value })}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                    placeholder="Assessment UUID..."
                  />
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold text-xs mb-1">Detailed Data TTL (Days)</label>
                  <input
                    type="number"
                    min={1}
                    max={3650}
                    required
                    value={policyForm.detailed_data_ttl_days}
                    onChange={(e) => setPolicyForm({ ...policyForm, detailed_data_ttl_days: parseInt(e.target.value) || 30 })}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold text-xs mb-1">Proctoring Evidence TTL (Days)</label>
                  <input
                    type="number"
                    min={1}
                    max={3650}
                    required
                    value={policyForm.proctoring_evidence_ttl_days}
                    onChange={(e) => setPolicyForm({ ...policyForm, proctoring_evidence_ttl_days: parseInt(e.target.value) || 30 })}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setShowPolicyModal(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm"
              >
                Save Policy
              </button>
            </div>
          </form>
        </div>
      )}

      {loading && (
        <div className="fixed bottom-4 right-4 bg-white border border-slate-200 px-3 py-1.5 rounded-lg text-xs text-slate-700 shadow-xl flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
          Synchronizing metrics...
        </div>
      )}
    </div>
  );
};
