import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Award,
  Users,
  BarChart3,
  FileSpreadsheet,
  Download,
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  ArrowLeft,
  Loader2,
  Send,
  HelpCircle,
  AlertCircle,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { Tabs, TabItem } from '../../components/common/Tabs';
import { Card } from '../../components/common/Card';
import { ResultsAPI } from '../../api/results';
import {
  AssessmentResult,
  AssessmentAnalytics,
  QuestionAnalyticsItem,
  ReportJob,
} from '../../types/results';

export const AdminAssessmentResultsPage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'roster' | 'analytics' | 'questions' | 'reports'>('roster');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Roster State
  const [results, setResults] = useState<AssessmentResult[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [passFilter, setPassFilter] = useState<string>('all');

  // Analytics State
  const [analytics, setAnalytics] = useState<AssessmentAnalytics | null>(null);
  const [questions, setQuestions] = useState<QuestionAnalyticsItem[]>([]);

  // Action State
  const [releasing, setReleasing] = useState(false);
  const [reportFormat, setReportFormat] = useState<'PDF' | 'XLSX' | 'CSV'>('PDF');
  const [reportType, setReportType] = useState<'ASSESSMENT_SUMMARY' | 'ASSESSMENT_ROSTER'>('ASSESSMENT_SUMMARY');
  const [reportJob, setReportJob] = useState<ReportJob | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);

  useEffect(() => {
    if (assessmentId) {
      loadTabData();
    }
  }, [assessmentId, activeTab, page, passFilter]);

  const loadTabData = async () => {
    if (!assessmentId) return;
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'roster') {
        const params: any = { page };
        if (search.trim()) params.search = search.trim();
        if (passFilter === 'pass') params.is_passed = true;
        if (passFilter === 'fail') params.is_passed = false;
        const res = await ResultsAPI.getAdminAssessmentResults(assessmentId, params);
        setResults(res.results);
        setTotalCount(res.count);
      } else if (activeTab === 'analytics') {
        const data = await ResultsAPI.getAdminAssessmentAnalytics(assessmentId);
        setAnalytics(data);
      } else if (activeTab === 'questions') {
        const data = await ResultsAPI.getAdminQuestionAnalytics(assessmentId);
        setQuestions(data);
      }
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || "Failed to load results data.");
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadTabData();
  };

  const handleReleaseResults = async () => {
    if (!assessmentId || !confirm("Are you sure you want to release results to all candidates?")) return;
    setReleasing(true);
    try {
      const res = await ResultsAPI.releaseAdminAssessmentResults(assessmentId);
      alert(`Successfully released ${res.released_count} results to candidates.`);
      loadTabData();
    } catch (err: any) {
      alert(err?.response?.data?.message || "Failed to release results.");
    } finally {
      setReleasing(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!assessmentId) return;
    setGeneratingReport(true);
    try {
      const job = await ResultsAPI.createAdminReport(assessmentId, reportType, reportFormat);
      setReportJob(job);

      const pollInterval = setInterval(async () => {
        try {
          const updatedJob = await ResultsAPI.getAdminReportStatus(job.id);
          setReportJob(updatedJob);
          if (updatedJob.status === 'COMPLETED' || updatedJob.status === 'FAILED') {
            clearInterval(pollInterval);
            setGeneratingReport(false);
            if (updatedJob.status === 'COMPLETED' && updatedJob.download_url) {
              window.open(updatedJob.download_url, '_blank');
            }
          }
        } catch {
          clearInterval(pollInterval);
          setGeneratingReport(false);
        }
      }, 1500);
    } catch (err: any) {
      setGeneratingReport(false);
      alert(err?.response?.data?.message || "Failed to request report generation.");
    }
  };

  const resultTabs: TabItem<'roster' | 'analytics' | 'questions' | 'reports'>[] = [
    { id: 'roster', label: 'Candidate Roster', icon: Users },
    { id: 'analytics', label: 'Cohort Analytics', icon: BarChart3 },
    { id: 'questions', label: 'Question Item Analysis', icon: HelpCircle },
    { id: 'reports', label: 'Reports & Export', icon: FileSpreadsheet },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <button
            onClick={() => navigate('/admin/assessments')}
            className="flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-800 mb-2 transition"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Assessments
          </button>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-3">
            <Award className="w-8 h-8 text-emerald-600" /> Assessment Results & Analytics
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReleaseResults}
            disabled={releasing}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold text-xs sm:text-sm rounded-lg shadow-sm transition"
          >
            {releasing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Release Results
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-3 text-sm">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Tab Navigation */}
      <Tabs
        tabs={resultTabs}
        activeTab={activeTab}
        onChange={(t) => {
          setActiveTab(t as any);
          setPage(1);
        }}
      />

      {/* Tab 1: Candidate Roster */}
      {activeTab === 'roster' && (
        <div className="space-y-6">
          {/* Filter Bar */}
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 w-full sm:w-80">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search EUID, roll #, email..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-white border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <button type="submit" className="px-3 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg">
                  Search
                </button>
              </form>

              <div className="flex items-center gap-3 w-full sm:w-auto">
                <span className="text-xs text-slate-600 font-semibold">Verdict:</span>
                <select
                  value={passFilter}
                  onChange={(e) => setPassFilter(e.target.value)}
                  className="bg-white border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
                >
                  <option value="all">All Verdicts</option>
                  <option value="pass">Passed Only</option>
                  <option value="fail">Failed Only</option>
                </select>
              </div>
            </div>
          </Card>

          {/* Table */}
          {loading ? (
            <div className="flex justify-center p-12">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
            </div>
          ) : results.length === 0 ? (
            <div className="text-center p-12 bg-white rounded-xl border border-slate-200 text-slate-500">
              No student results found matching criteria.
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200/90 overflow-hidden shadow-sm">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <th className="py-3.5 px-4">Candidate</th>
                    <th className="py-3.5 px-4">EUID / Roll</th>
                    <th className="py-3.5 px-4">Score</th>
                    <th className="py-3.5 px-4">Percentage</th>
                    <th className="py-3.5 px-4">Verdict</th>
                    <th className="py-3.5 px-4">Proctoring Risk</th>
                    <th className="py-3.5 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {results.map((r) => {
                    const isPass = r.is_passed;
                    const proct = r.proctoring_summary;

                    return (
                      <tr key={r.id} className="hover:bg-slate-50/80 transition">
                        <td className="py-3.5 px-4 font-medium text-slate-900">
                          {r.student?.email || 'N/A'}
                        </td>
                        <td className="py-3.5 px-4 text-slate-500 font-mono text-xs">
                          {r.student?.euid || 'N/A'} &bull; {r.student?.roll_number || 'N/A'}
                        </td>
                        <td className="py-3.5 px-4 font-bold text-slate-900">
                          {r.total_score_earned} <span className="text-xs text-slate-400 font-normal">/ {r.total_possible_score}</span>
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-emerald-700">
                          {r.percentage}%
                        </td>
                        <td className="py-3.5 px-4">
                          {isPass !== null && (
                            <span
                              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold ${
                                isPass
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-rose-50 text-rose-700 border border-rose-200'
                              }`}
                            >
                              {isPass ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                              {isPass ? 'PASS' : 'FAIL'}
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          {proct ? (
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${
                                proct.risk_band === 'CRITICAL' || proct.risk_band === 'HIGH'
                                  ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                  : proct.risk_band === 'MEDIUM'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-slate-100 text-slate-700 border border-slate-200'
                              }`}
                            >
                              <ShieldAlert className="w-3 h-3" /> {proct.risk_band} ({proct.risk_score})
                            </span>
                          ) : (
                            <span className="text-slate-400 text-xs">N/A</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          {r.is_released ? (
                            <span className="text-xs font-semibold text-emerald-700">Released</span>
                          ) : (
                            <span className="text-xs font-semibold text-amber-700">Unreleased</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Pagination */}
              <div className="flex items-center justify-between p-4 border-t border-slate-200 bg-white text-xs text-slate-600">
                <div>Total Candidates: {totalCount}</div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 bg-slate-100 border border-slate-200 hover:bg-slate-200 disabled:opacity-50 text-slate-700 font-medium rounded-lg"
                  >
                    Previous
                  </button>
                  <span className="font-semibold text-slate-800">Page {page}</span>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={results.length < 20}
                    className="px-3 py-1.5 bg-slate-100 border border-slate-200 hover:bg-slate-200 disabled:opacity-50 text-slate-700 font-medium rounded-lg"
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Cohort Analytics */}
      {activeTab === 'analytics' && analytics && (
        <div className="space-y-8">
          {/* KPI Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="p-5">
              <div className="text-xs text-slate-600 font-semibold">Completion Rate</div>
              <div className="text-2xl font-black text-slate-900 mt-1">
                {analytics.cohort_metrics.completion_rate_percentage}%
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {analytics.cohort_metrics.total_completed} / {analytics.cohort_metrics.total_assigned} Students
              </div>
            </Card>

            <Card className="p-5">
              <div className="text-xs text-slate-600 font-semibold">Pass Rate</div>
              <div className="text-2xl font-black text-emerald-700 mt-1">
                {analytics.cohort_metrics.pass_rate_percentage}%
              </div>
              <div className="text-xs text-slate-500 mt-0.5">Threshold met</div>
            </Card>

            <Card className="p-5">
              <div className="text-xs text-slate-600 font-semibold">Cohort Mean Score</div>
              <div className="text-2xl font-black text-emerald-700 mt-1">
                {analytics.score_statistics.mean_score}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">Median: {analytics.score_statistics.median_score}</div>
            </Card>

            <Card className="p-5">
              <div className="text-xs text-slate-600 font-semibold">Standard Deviation</div>
              <div className="text-2xl font-black text-slate-900 mt-1">
                {analytics.score_statistics.standard_deviation}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                Range: {analytics.score_statistics.lowest_score} – {analytics.score_statistics.highest_score}
              </div>
            </Card>
          </div>

          {/* Score Distribution Histogram */}
          <Card className="p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-6">Score Distribution Histogram</h2>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.score_distribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.8} />
                  <XAxis dataKey="bucket" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.75rem', color: '#0f172a' }}
                    labelStyle={{ color: '#0f172a', fontWeight: 'bold' }}
                  />
                  <Bar dataKey="count" fill="#059669" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Proctoring Risk Correlation Safeguard */}
          <Card className="p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-2 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-emerald-600" /> Informational Proctoring Risk Correlation
            </h2>
            <p className="text-xs text-slate-500 mb-4">
              Informational context only. Risk scores represent statistical anomalies, never disciplinary proof.
            </p>

            {analytics.proctoring_risk_correlation.is_available && analytics.proctoring_risk_correlation.distribution ? (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {Object.entries(analytics.proctoring_risk_correlation.distribution).map(([band, val]) => (
                  <div key={band} className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                    <div className="text-xs font-bold text-slate-700">{band}</div>
                    <div className="text-lg font-black text-slate-900 mt-1">{val.count} students</div>
                    <div className="text-xs text-emerald-700 font-semibold mt-0.5">Avg Score: {val.average_score}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-amber-50 p-4 rounded-xl border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
                <span>
                  {analytics.proctoring_risk_correlation.reason ||
                    'Proctoring aggregate distribution withheld to safeguard privacy (requires cohort N ≥ 10).'}
                </span>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Tab 3: Question Item Analysis */}
      {activeTab === 'questions' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200/90 overflow-hidden shadow-sm">
            <table className="w-full text-left border-collapse font-mono">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  <th className="py-3.5 px-4">#</th>
                  <th className="py-3.5 px-4">Title</th>
                  <th className="py-3.5 px-4">Type</th>
                  <th className="py-3.5 px-4">Max Pts</th>
                  <th className="py-3.5 px-4">Difficulty (P)</th>
                  <th className="py-3.5 px-4">Discrimination (D)</th>
                  <th className="py-3.5 px-4">Avg Score</th>
                  <th className="py-3.5 px-4">Correct / Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {questions.map((q) => (
                  <tr key={q.snapshot_question_id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3.5 px-4 font-bold text-slate-500">{q.order}</td>
                    <td className="py-3.5 px-4 font-semibold text-slate-900 font-sans">{q.title}</td>
                    <td className="py-3.5 px-4 text-xs font-mono text-slate-600">{q.question_type}</td>
                    <td className="py-3.5 px-4 text-slate-800 font-semibold">{q.max_points}</td>
                    <td className="py-3.5 px-4">
                      <span className="px-2.5 py-0.5 rounded-md text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {q.difficulty_index_p}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      {q.discrimination_index_d !== null ? (
                        <span className="px-2.5 py-0.5 rounded-md text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
                          {q.discrimination_index_d}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">N/A (N&lt;10)</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-900">{q.average_score}</td>
                    <td className="py-3.5 px-4 text-xs text-slate-600">
                      {q.breakdown.correct} / {q.breakdown.total_responses}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Reports & Export */}
      {activeTab === 'reports' && (
        <Card className="max-w-2xl p-8 space-y-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Generate Official Assessment Reports</h2>
            <p className="text-sm text-slate-500 mt-1">
              Asynchronously export candidate rosters, statistical summaries, or item analyses.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-2">Report Scope</label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value as any)}
                className="w-full bg-white border border-slate-300 text-slate-900 text-sm rounded-lg p-3 outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
              >
                <option value="ASSESSMENT_SUMMARY">Assessment Executive Summary</option>
                <option value="ASSESSMENT_ROSTER">Full Candidate Gradebook Roster</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-2">Export Format</label>
              <select
                value={reportFormat}
                onChange={(e) => setReportFormat(e.target.value as any)}
                className="w-full bg-white border border-slate-300 text-slate-900 text-sm rounded-lg p-3 outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
              >
                <option value="PDF">PDF Vector Document</option>
                <option value="XLSX">Excel Spreadsheet (.xlsx)</option>
                <option value="CSV">Controlled CSV Export (.csv)</option>
              </select>
            </div>

            <button
              onClick={handleGenerateReport}
              disabled={generatingReport}
              className="w-full flex items-center justify-center gap-2 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold text-sm rounded-lg shadow-sm transition"
            >
              {generatingReport ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" /> Generating Asynchronous Report...
                </>
              ) : (
                <>
                  <Download className="w-5 h-5" /> Generate & Download Report
                </>
              )}
            </button>
          </div>

          {reportJob && (
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1">
              <div className="text-slate-600">Job ID: <span className="font-mono text-slate-900">{reportJob.id}</span></div>
              <div className="text-slate-600">
                Status:{' '}
                <span className={`font-semibold ${reportJob.status === 'COMPLETED' ? 'text-emerald-700' : 'text-amber-700'}`}>
                  {reportJob.status}
                </span>
              </div>
              {reportJob.sha256_hash && (
                <div className="text-slate-600 font-mono truncate">SHA-256: {reportJob.sha256_hash}</div>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
};
