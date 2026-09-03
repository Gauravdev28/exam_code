import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getAdminProctoringSessions,
  getAdminProctoringSessionDetail,
  updateAdminProctoringReview,
  getEvidenceUrl,
} from '../../api/proctoring';
import {
  AdminProctoringSessionSummary,
  AdminProctoringSessionDetail,
  RiskBand,
  ReviewStatus,
} from '../../types/proctoring';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  ShieldAlert,
  ShieldCheck,
  Search,
  AlertTriangle,
  Eye,
  XCircle,
  Clock,
  ArrowLeft,
  Camera,
  Activity,
} from 'lucide-react';

export const AdminProctoringDashboardPage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId: string }>();

  const [sessions, setSessions] = useState<AdminProctoringSessionSummary[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [reviewFilter, setReviewFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Selected session for detail/timeline modal
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<AdminProctoringSessionDetail | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [reviewDecision, setReviewDecision] = useState<string>('REVIEWED_CLEAN');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const fetchSessions = useCallback(async () => {
    if (!assessmentId) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const params: any = {};
      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (riskFilter !== 'ALL') params.risk_band = riskFilter;
      if (reviewFilter !== 'ALL') params.review_status = reviewFilter;

      const data = await getAdminProctoringSessions(assessmentId, params);
      setSessions(data.results || []);
      setTotalCount(data.count || 0);
    } catch (err: any) {
      setErrorMessage(err.error?.message || 'Failed to fetch proctoring sessions.');
    } finally {
      setIsLoading(false);
    }
  }, [assessmentId, searchQuery, riskFilter, reviewFilter]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleOpenDetail = async (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setIsDetailLoading(true);
    try {
      const detail = await getAdminProctoringSessionDetail(sessionId);
      setSessionDetail(detail);
      if (detail.review) {
        setReviewDecision(detail.review.decision);
        setReviewNotes(detail.review.notes || '');
      } else {
        setReviewDecision('REVIEWED_CLEAN');
        setReviewNotes('');
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || 'Failed to load session details.');
    } finally {
      setIsDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedSessionId(null);
    setSessionDetail(null);
  };

  const handleSaveReview = async () => {
    if (!selectedSessionId) return;
    setIsSubmittingReview(true);
    try {
      await updateAdminProctoringReview(selectedSessionId, reviewDecision, reviewNotes);
      // Refresh current detail and list
      const updated = await getAdminProctoringSessionDetail(selectedSessionId);
      setSessionDetail(updated);
      fetchSessions();
    } catch (err: any) {
      alert(err.error?.message || 'Failed to update review decision.');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const getRiskBandBadge = (band: RiskBand, score: string) => {
    switch (band) {
      case 'CRITICAL':
        return <Badge variant="danger" className="font-semibold">CRITICAL ({score})</Badge>;
      case 'HIGH':
        return <Badge variant="warning" className="bg-orange-950 text-orange-400 border-orange-800 font-semibold">HIGH ({score})</Badge>;
      case 'MEDIUM':
        return <Badge variant="warning" className="font-semibold">MEDIUM ({score})</Badge>;
      case 'LOW':
        return <Badge variant="neutral" className="bg-yellow-950 text-yellow-400 border-yellow-800">LOW ({score})</Badge>;
      default:
        return <Badge variant="success">NORMAL ({score})</Badge>;
    }
  };

  const getReviewStatusBadge = (status: ReviewStatus) => {
    switch (status) {
      case 'REVIEWED':
        return <Badge variant="success">Reviewed</Badge>;
      case 'DISMISSED':
        return <Badge variant="neutral">Dismissed</Badge>;
      case 'ESCALATED':
        return <Badge variant="danger">Escalated</Badge>;
      case 'UNDER_REVIEW':
        return <Badge variant="warning">Under Review</Badge>;
      default:
        return <Badge variant="neutral" className="bg-slate-800 text-slate-400">Unreviewed</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Link
            to="/admin/assessments"
            className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors mb-2"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Assessments
          </Link>
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-7 h-7 text-indigo-400" />
            <h1 className="text-2xl font-bold text-white tracking-tight">
              AI Proctoring & Anomaly Review Dashboard
            </h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Real-time suspicious telemetry ledger, multi-modal risk scoring, and administrative audit review.
          </p>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <Card className="p-4 bg-slate-900/60 border-slate-800">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
            <input
              type="text"
              placeholder="Search by name, email, or EUID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Risk Bands</option>
              <option value="CRITICAL">Critical Risk (81-100)</option>
              <option value="HIGH">High Risk (61-80)</option>
              <option value="MEDIUM">Medium Risk (41-60)</option>
              <option value="LOW">Low Risk (21-40)</option>
              <option value="NORMAL">Normal (0-20)</option>
            </select>
          </div>

          <div>
            <select
              value={reviewFilter}
              onChange={(e) => setReviewFilter(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Review Statuses</option>
              <option value="UNREVIEWED">Unreviewed</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="REVIEWED">Reviewed - Clean</option>
              <option value="DISMISSED">Dismissed False Positive</option>
              <option value="ESCALATED">Escalated for Inquiry</option>
            </select>
          </div>

          <div className="flex items-center justify-end">
            <span className="text-sm text-slate-400 font-mono">
              Total Sessions: <span className="text-slate-200 font-semibold">{totalCount}</span>
            </span>
          </div>
        </div>
      </Card>

      {/* Sessions Table */}
      <Card className="overflow-hidden border-slate-800 bg-slate-900/40">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 flex flex-col items-center gap-3">
            <Activity className="w-8 h-8 text-indigo-400 animate-spin" />
            <p className="text-sm">Loading proctoring sessions...</p>
          </div>
        ) : errorMessage ? (
          <div className="p-8 text-center text-red-400 flex flex-col items-center gap-2">
            <AlertTriangle className="w-8 h-8" />
            <p className="text-sm">{errorMessage}</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-12 text-center text-slate-400 flex flex-col items-center gap-2">
            <ShieldCheck className="w-10 h-10 text-slate-600" />
            <p className="text-base font-medium text-slate-300">No proctoring sessions found.</p>
            <p className="text-sm text-slate-500">No student attempts match the active filter criteria.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/80 text-xs font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3.5">Student / EUID</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Risk Score / Band</th>
                  <th className="px-6 py-3.5 text-center">Events</th>
                  <th className="px-6 py-3.5 text-center">Warnings</th>
                  <th className="px-6 py-3.5">Review Status</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {sessions.map((s) => (
                  <tr key={s.session_id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-white">{s.student.full_name}</span>
                        <span className="text-xs text-slate-400">{s.student.email}</span>
                        <span className="text-xs font-mono text-indigo-400 mt-0.5">{s.student.euid || 'NO-EUID'}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={s.status === 'ACTIVE' ? 'success' : s.status === 'DEGRADED' ? 'warning' : 'neutral'}>
                        {s.status}
                      </Badge>
                    </td>
                    <td className="px-6 py-4">
                      {getRiskBandBadge(s.risk_band, s.risk_score)}
                    </td>
                    <td className="px-6 py-4 text-center font-mono">
                      {s.total_events_count}
                    </td>
                    <td className="px-6 py-4 text-center font-mono">
                      {s.total_warnings_count}
                    </td>
                    <td className="px-6 py-4">
                      {getReviewStatusBadge(s.review_status)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleOpenDetail(s.session_id)}
                        className="inline-flex items-center gap-1.5"
                      >
                        <Eye className="w-3.5 h-3.5" /> Inspect Timeline
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Detail & Timeline Modal */}
      {selectedSessionId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
              <div className="flex items-center gap-3">
                <ShieldAlert className="w-6 h-6 text-indigo-400" />
                <div>
                  <h3 className="text-lg font-bold text-white">
                    Proctoring Timeline & Evidence Review
                  </h3>
                  {sessionDetail && (
                    <p className="text-xs text-slate-400 mt-0.5">
                      Student: <span className="text-slate-200 font-semibold">{sessionDetail.student.full_name}</span> ({sessionDetail.student.euid}) | Attempt: {sessionDetail.attempt_id}
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={handleCloseDetail}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1">
              {isDetailLoading || !sessionDetail ? (
                <div className="p-12 text-center text-slate-400 flex flex-col items-center gap-3">
                  <Activity className="w-8 h-8 text-indigo-400 animate-spin" />
                  <p className="text-sm">Loading detailed event timeline and evidence...</p>
                </div>
              ) : (
                <>
                  {/* Summary Bar */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-950/60 border border-slate-800 rounded-lg">
                    <div>
                      <span className="text-xs text-slate-400 uppercase">Risk Score</span>
                      <div className="mt-1">{getRiskBandBadge(sessionDetail.risk_band, sessionDetail.risk_score)}</div>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase">Review Status</span>
                      <div className="mt-1">{getReviewStatusBadge(sessionDetail.review_status)}</div>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase">Total Events</span>
                      <div className="text-lg font-bold text-slate-200 mt-0.5 font-mono">{sessionDetail.total_events_count}</div>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase">Warnings Issued</span>
                      <div className="text-lg font-bold text-slate-200 mt-0.5 font-mono">{sessionDetail.total_warnings_count}</div>
                    </div>
                  </div>

                  {/* Chronological Event Timeline */}
                  <div>
                    <h4 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-3 flex items-center gap-2">
                      <Clock className="w-4 h-4 text-indigo-400" /> Chronological Telemetry Ledger
                    </h4>

                    {sessionDetail.events.length === 0 ? (
                      <p className="text-sm text-slate-500 italic p-4 bg-slate-950/40 rounded-lg border border-slate-800/60">
                        No suspicious events recorded for this session.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {sessionDetail.events.map((ev) => (
                          <div
                            key={ev.id}
                            className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-lg flex flex-col gap-2"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant={
                                    ev.severity === 'CRITICAL'
                                      ? 'danger'
                                      : ev.severity === 'HIGH'
                                      ? 'warning'
                                      : 'neutral'
                                  }
                                >
                                  {ev.event_type}
                                </Badge>
                                <span className="text-xs font-mono text-slate-400">
                                  [{ev.source}] Delta: +{ev.risk_delta}
                                </span>
                              </div>
                              <span className="text-xs text-slate-500 font-mono">
                                {new Date(ev.server_received_at).toLocaleTimeString()}
                              </span>
                            </div>

                            <div className="text-xs text-slate-400 grid grid-cols-2 sm:grid-cols-3 gap-2 mt-1">
                              <div>
                                <span className="text-slate-500">Confidence:</span> {(ev.confidence * 100).toFixed(0)}%
                              </div>
                              <div>
                                <span className="text-slate-500">Model:</span> {ev.model_name || 'N/A'} ({ev.model_version || 'V1'})
                              </div>
                              <div>
                                <span className="text-slate-500">Policy:</span> {ev.inference_policy_version}
                              </div>
                            </div>

                            {/* Keyframe Evidence Media Preview */}
                            {ev.evidence_id && (
                              <div className="mt-3 p-3 bg-slate-900/80 border border-slate-800 rounded-lg">
                                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-2">
                                  <Camera className="w-3.5 h-3.5 text-indigo-400" /> Captured Keyframe Evidence
                                </span>
                                <div className="max-w-xs rounded-lg overflow-hidden border border-slate-700 bg-black">
                                  <img
                                    src={getEvidenceUrl(ev.evidence_id)}
                                    alt="Proctoring Anomaly Keyframe"
                                    className="w-full h-auto object-cover"
                                    onError={(e) => {
                                      // Fallback for mocked test environments
                                      (e.target as HTMLElement).style.display = 'none';
                                    }}
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Administrative Review Action Form */}
                  <div className="p-5 bg-slate-950/80 border border-indigo-900/40 rounded-xl space-y-4">
                    <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" /> Authoritative Human Review Verdict
                    </h4>
                    <p className="text-xs text-slate-400">
                      Proctoring scores are probabilistic indicators. Assign authoritative institutional review determinations below.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 uppercase mb-1">
                          Review Decision
                        </label>
                        <select
                          value={reviewDecision}
                          onChange={(e) => setReviewDecision(e.target.value)}
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                        >
                          <option value="REVIEWED_CLEAN">Reviewed - Clean / Normal</option>
                          <option value="SUSPICIOUS_CONFIRMED">Suspicious Behavior Confirmed</option>
                          <option value="DISMISSED_FALSE_POSITIVE">Dismissed as False Positive</option>
                          <option value="REQUIRES_FURTHER_INSPECTION">Requires Further Inspection</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 uppercase mb-1">
                        Administrative Audit Notes
                      </label>
                      <textarea
                        rows={3}
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        placeholder="Document observations, rationale, or interview outcomes..."
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                      <Button
                        variant="primary"
                        onClick={handleSaveReview}
                        disabled={isSubmittingReview}
                      >
                        {isSubmittingReview ? 'Saving...' : 'Save Review Decision'}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
