import React, { useState, useEffect } from 'react';
import { RetentionAPI } from '../../api/retention';
import { StudentRetentionStatus, ExportJob } from '../../types/retention';

export const StudentPrivacyPage: React.FC = () => {
  const [retentionStatus, setRetentionStatus] = useState<StudentRetentionStatus | null>(null);
  const [exportJobs, setExportJobs] = useState<ExportJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [status, jobs] = await Promise.all([
        RetentionAPI.getStudentRetentionStatus(),
        RetentionAPI.getStudentExportJobs(),
      ]);
      setRetentionStatus(status);
      setExportJobs(jobs);
    } catch (err: any) {
      setError(err?.error?.message || err?.message || 'Failed to load privacy status.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRequestExport = async (attemptId?: string) => {
    try {
      setRequesting(true);
      setError(null);
      await RetentionAPI.createStudentExportJob(attemptId);
      setSuccessMessage('Data Subject Access Request (DSAR) queued. Your archive is being compiled and encrypted with AES-256-GCM.');
      await loadData();
    } catch (err: any) {
      setError(err?.error?.message || err?.message || 'Failed to create export request.');
    } finally {
      setRequesting(false);
    }
  };

  const handleDownload = async (job: ExportJob) => {
    try {
      setDownloadingId(job.id);
      const blob = await RetentionAPI.downloadExportArchive(job.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `codeguard_dsar_export_${job.id.substring(0, 8)}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(err?.error?.message || err?.message || 'Failed to download archive.');
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Your Privacy & Personal Data</h1>
        <p className="text-sm text-slate-400 mt-1">
          Review institutional data retention policies, monitor your assessment telemetry lifecycle, and request encrypted personal data exports (DSAR).
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm flex justify-between items-center">
          <span>{successMessage}</span>
          <button onClick={() => setSuccessMessage(null)} className="text-xs text-emerald-400 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Policy Notice Card */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-brand-400 text-lg">🛡</span>
          <h2 className="text-base font-semibold text-white">Data Retention Policy & Principles</h2>
        </div>
        <p className="text-sm text-slate-400 leading-relaxed">
          Pursuant to institutional academic governance and global privacy standards (GDPR/FERPA), detailed examination telemetry
          (including your selected answers, submitted source code, and proctoring events) is automatically scheduled for permanent scrubbing{' '}
          <strong className="text-white">{retentionStatus?.default_policy_days || 30} days</strong> following assessment completion.
        </p>
        <p className="text-xs text-slate-500 leading-relaxed">
          Official academic transcripts, final scores, percentages, and pass/fail credentials are permanently preserved in the Historical Result Summary ledger and are never deleted.
        </p>
      </div>

      {/* Assessment Lifecycle Table */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-base font-semibold text-white">Your Assessment Data Lifecycles</h2>
        </div>
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950 text-xs uppercase text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th className="px-4 py-3">Assessment Title</th>
                <th className="px-4 py-3">Submitted At</th>
                <th className="px-4 py-3">Data Status</th>
                <th className="px-4 py-3">Retention Window</th>
                <th className="px-4 py-3 text-right">Data Export</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-xs">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    Loading your retention status...
                  </td>
                </tr>
              ) : !retentionStatus?.attempts?.length ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                    Zero completed assessments found.
                  </td>
                </tr>
              ) : (
                retentionStatus.attempts.map((att) => (
                  <tr key={att.attempt_id} className="hover:bg-slate-800/20">
                    <td className="px-4 py-3 font-medium text-white">{att.assessment_title}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {att.submitted_at ? new Date(att.submitted_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                          att.purge_state === 'PURGED'
                            ? 'bg-slate-800 text-slate-400'
                            : att.purge_state === 'DEFERRED_HOLD'
                            ? 'bg-indigo-500/20 text-indigo-300'
                            : 'bg-emerald-500/20 text-emerald-400'
                        }`}
                      >
                        {att.purge_state === 'PURGED' ? 'PURGED (SCRUBBED)' : att.purge_state}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {att.purge_state === 'PURGED' ? (
                        <span className="text-slate-500 italic">Detailed data purged</span>
                      ) : att.days_remaining_until_purge !== null ? (
                        <span className="font-semibold text-amber-400">
                          {att.days_remaining_until_purge} days remaining
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleRequestExport(att.attempt_id)}
                        disabled={requesting}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-brand-400 text-xs rounded border border-brand-500/20 transition-all disabled:opacity-50"
                      >
                        Export Data
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* DSAR Export Requests Section */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-base font-semibold text-white">Your Personal Data Exports (DSAR)</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Personal archives are encrypted at rest using AES-256-GCM and retained for exactly 7 days before automated deletion.
            </p>
          </div>
          <button
            onClick={() => handleRequestExport()}
            disabled={requesting}
            className="px-3.5 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold shadow-md transition-all disabled:opacity-50"
          >
            {requesting ? 'Queueing...' : '+ Request Full Account Export'}
          </button>
        </div>

        <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950 text-xs uppercase text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th className="px-4 py-3">Scope / Target</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Encryption</th>
                <th className="px-4 py-3">Archive TTL</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-xs font-mono">
              {exportJobs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-500 font-sans">
                    Zero data export requests. Click &ldquo;Request Full Account Export&rdquo; to download your personal data bundle.
                  </td>
                </tr>
              ) : (
                exportJobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/20">
                    <td className="px-4 py-3 font-sans text-white">
                      {job.assessment_title || 'Complete Account Data'}
                      <div className="text-[10px] text-slate-500 font-mono">{job.id.substring(0, 16)}...</div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] ${
                          job.status === 'READY'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : job.status === 'EXPIRED'
                            ? 'bg-slate-800 text-slate-500'
                            : job.status === 'FAILED'
                            ? 'bg-rose-500/20 text-rose-400'
                            : 'bg-amber-500/20 text-amber-400'
                        }`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {job.encryption_algorithm} ({job.encryption_key_version})
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {job.expires_at ? (
                        new Date(job.expires_at) > new Date() ? (
                          `Expires ${new Date(job.expires_at).toLocaleDateString()}`
                        ) : (
                          <span className="text-slate-500">Expired</span>
                        )
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-sans">
                      {job.status === 'READY' ? (
                        <button
                          onClick={() => handleDownload(job)}
                          disabled={downloadingId === job.id}
                          className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition-all"
                        >
                          {downloadingId === job.id ? 'Decrypting...' : 'Download ZIP'}
                        </button>
                      ) : job.status === 'EXPIRED' ? (
                        <span className="text-slate-600 text-xs italic">Unlinked</span>
                      ) : (
                        <span className="text-amber-400 text-xs animate-pulse">Processing...</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
