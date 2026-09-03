import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Award,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Download,
  AlertCircle,
  ArrowLeft,
  Loader2,
} from 'lucide-react';
import { ResultsAPI } from '../../api/results';
import { AssessmentResult, QuestionResult, ReportJob } from '../../types/results';

export const StudentResultPage: React.FC = () => {
  const { attemptId, resultId } = useParams<{ attemptId?: string; resultId?: string }>();
  const navigate = useNavigate();

  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Report generation state
  const [reportFormat, setReportFormat] = useState<'PDF' | 'XLSX' | 'CSV'>('PDF');
  const [reportJob, setReportJob] = useState<ReportJob | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);

  useEffect(() => {
    fetchResult();
  }, [attemptId, resultId]);

  const fetchResult = async () => {
    setLoading(true);
    setError(null);
    try {
      let data: AssessmentResult;
      if (attemptId) {
        data = await ResultsAPI.getStudentAttemptResult(attemptId);
      } else if (resultId) {
        data = await ResultsAPI.getStudentResultDetail(resultId);
      } else {
        throw new Error("No attempt or result ID specified.");
      }
      setResult(data);
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || "Failed to load assessment result.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!result) return;
    setGeneratingReport(true);
    try {
      const job = await ResultsAPI.createStudentReport(result.assessment_id, reportFormat);
      setReportJob(job);

      // Poll until ready
      const pollInterval = setInterval(async () => {
        try {
          const updatedJob = await ResultsAPI.getStudentReportStatus(job.id);
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

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-brand-400" />
        <p className="text-slate-400 font-medium">Finalizing score and assembling scorecard...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="max-w-2xl mx-auto mt-12 p-8 bg-slate-900/60 border border-slate-800 rounded-2xl text-center">
        <AlertCircle className="w-12 h-12 text-rose-400 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">Result Unavailable</h2>
        <p className="text-slate-400 mb-6">{error || "The result could not be retrieved at this time."}</p>
        <Link
          to="/student/assessments"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-xl transition"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Assessments
        </Link>
      </div>
    );
  }

  const isPassed = result.is_passed;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Back Button */}
      <button
        onClick={() => navigate('/student/assessments')}
        className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 mb-6 transition"
      >
        <ArrowLeft className="w-4 h-4" /> Back to My Assessments
      </button>

      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 border border-slate-800/80 p-8 mb-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20 mb-3">
              <Award className="w-3.5 h-3.5" /> Official Result Projection
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">{result.assessment_title}</h1>
            <p className="text-slate-400 text-sm mt-1">
              Finalized on {new Date(result.finalized_at).toLocaleString()} • Duration: {Math.round(result.time_spent_seconds / 60)} mins
            </p>
          </div>

          {/* Verdict Pill */}
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-4xl font-black text-white tracking-tight">
                {result.total_score_earned}
                <span className="text-lg text-slate-400 font-normal"> / {result.total_possible_score}</span>
              </div>
              <div className="text-sm font-semibold text-brand-400">{result.percentage}% Score</div>
            </div>

            {isPassed !== null && (
              <div
                className={`px-5 py-3 rounded-2xl flex items-center gap-2 font-bold text-base shadow-lg ${
                  isPassed
                    ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-400'
                    : 'bg-rose-500/15 border border-rose-500/30 text-rose-400'
                }`}
              >
                {isPassed ? <CheckCircle2 className="w-6 h-6" /> : <XCircle className="w-6 h-6" />}
                {isPassed ? 'PASSED' : 'FAILED'}
              </div>
            )}
          </div>
        </div>

        {/* Metrics Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-slate-800/80">
          <div className="bg-slate-950/40 rounded-xl p-3.5 border border-slate-800/50">
            <div className="text-xs text-slate-400">Answered Questions</div>
            <div className="text-lg font-bold text-slate-200 mt-0.5">
              {result.answered_questions} / {result.total_questions}
            </div>
          </div>
          <div className="bg-slate-950/40 rounded-xl p-3.5 border border-slate-800/50">
            <div className="text-xs text-emerald-400/90 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" /> Correct
            </div>
            <div className="text-lg font-bold text-emerald-400 mt-0.5">{result.correct_questions}</div>
          </div>
          <div className="bg-slate-950/40 rounded-xl p-3.5 border border-slate-800/50">
            <div className="text-xs text-amber-400/90 flex items-center gap-1.5">
              <HelpCircle className="w-3.5 h-3.5" /> Partially Correct
            </div>
            <div className="text-lg font-bold text-amber-400 mt-0.5">{result.partially_correct_questions}</div>
          </div>
          <div className="bg-slate-950/40 rounded-xl p-3.5 border border-slate-800/50">
            <div className="text-xs text-rose-400/90 flex items-center gap-1.5">
              <XCircle className="w-3.5 h-3.5" /> Incorrect / Skipped
            </div>
            <div className="text-lg font-bold text-rose-400 mt-0.5">
              {result.incorrect_questions + result.skipped_questions}
            </div>
          </div>
        </div>
      </div>

      {/* Action Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/50 border border-slate-800/80 p-4 rounded-2xl mb-8">
        <div className="text-sm text-slate-300 font-medium">Download Official Scorecard Report:</div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <select
            value={reportFormat}
            onChange={(e) => setReportFormat(e.target.value as any)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 outline-none focus:border-brand-500 transition"
          >
            <option value="PDF">PDF Scorecard</option>
            <option value="XLSX">Excel Workbook</option>
            <option value="CSV">Controlled CSV</option>
          </select>

          <button
            onClick={handleGenerateReport}
            disabled={generatingReport}
            className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-5 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-slate-800 text-white font-semibold text-sm rounded-xl shadow-lg transition"
          >
            {generatingReport ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Generating...
              </>
            ) : (
              <>
                <Download className="w-4 h-4" /> Download Report
              </>
            )}
          </button>
        </div>
      </div>

      {reportJob && (
        <div className="mb-8 p-4 bg-slate-900/60 rounded-2xl border border-slate-800 text-xs flex items-center justify-between">
          <div>
            <span className="text-slate-400">Report Status: </span>
            <span className={`font-semibold ${reportJob.status === 'COMPLETED' ? 'text-emerald-400' : 'text-amber-400'}`}>
              {reportJob.status}
            </span>
            {reportJob.sha256_hash && (
              <span className="text-slate-400 ml-4 font-mono">
                SHA-256: {reportJob.sha256_hash.substring(0, 16)}...
              </span>
            )}
          </div>
          {reportJob.download_url && (
            <a
              href={reportJob.download_url}
              target="_blank"
              rel="noreferrer"
              className="text-brand-400 font-semibold hover:underline"
            >
              Direct Link
            </a>
          )}
        </div>
      )}

      {/* Question Breakdown Section */}
      {result.question_results && result.question_results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-bold text-white tracking-tight mb-4">Question Performance Breakdown</h2>

          {result.question_results.map((qr: QuestionResult) => {
            const isCorrect = qr.is_correct;
            const isPartial = qr.is_partially_correct;
            const isSkipped = qr.is_skipped;

            return (
              <div
                key={qr.id}
                className="bg-slate-900/40 border border-slate-800/70 hover:border-slate-700/80 rounded-2xl p-5 transition"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold px-2.5 py-0.5 rounded-md bg-slate-800 text-slate-300">
                        #{qr.order}
                      </span>
                      <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-slate-800/60 text-slate-400">
                        {qr.question_type}
                      </span>
                      {isCorrect && (
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Correct
                        </span>
                      )}
                      {isPartial && (
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400 flex items-center gap-1">
                          <HelpCircle className="w-3 h-3" /> Partial
                        </span>
                      )}
                      {isSkipped && (
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-slate-700 text-slate-300">
                          Skipped
                        </span>
                      )}
                      {!isCorrect && !isPartial && !isSkipped && (
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-400 flex items-center gap-1">
                          <XCircle className="w-3 h-3" /> Incorrect
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-semibold text-slate-100">{qr.title}</h3>
                  </div>

                  <div className="text-right whitespace-nowrap">
                    <div className="text-lg font-bold text-white">
                      {qr.earned_points}{' '}
                      <span className="text-xs text-slate-400 font-normal">/ {qr.max_points} pts</span>
                    </div>
                  </div>
                </div>

                {/* Coding Details if present */}
                {qr.question_type === 'CODING' && qr.evaluation_details && (
                  <div className="mt-4 pt-3 border-t border-slate-800/60 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="text-slate-400">
                      Verdict:{' '}
                      <span className="font-semibold text-slate-200">
                        {qr.evaluation_details.verdict || 'N/A'}
                      </span>
                    </div>
                    <div className="text-slate-400">
                      Test Cases:{' '}
                      <span className="font-semibold text-slate-200">
                        {qr.evaluation_details.passed_test_cases || 0} / {qr.evaluation_details.total_test_cases || 0}
                      </span>
                    </div>
                    <div className="text-slate-400">
                      Execution Time:{' '}
                      <span className="font-semibold text-slate-200">
                        {qr.evaluation_details.execution_time_ms ? `${qr.evaluation_details.execution_time_ms} ms` : 'N/A'}
                      </span>
                    </div>
                    <div className="text-slate-400">
                      Peak Memory:{' '}
                      <span className="font-semibold text-slate-200">
                        {qr.evaluation_details.memory_used_kb ? `${qr.evaluation_details.memory_used_kb} KB` : 'N/A'}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
