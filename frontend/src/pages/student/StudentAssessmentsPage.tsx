import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getStudentAssessments, startAssessmentAttempt } from '../../api/assessments';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  FileText,
  Clock,
  Calendar,
  AlertCircle,
  Play,
  CheckCircle2,
  Award,
} from 'lucide-react';
import { StudentAssessmentItem } from '../../types/assessment';

export const StudentAssessmentsPage: React.FC = () => {
  const navigate = useNavigate();
  const [assessments, setAssessments] = useState<StudentAssessmentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStartingId, setIsStartingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    loadAssessments();
  }, []);

  const loadAssessments = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await getStudentAssessments();
      if (res.data) {
        setAssessments(res.data);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load assigned assessments.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartAttempt = async (aId: string, activeAttemptId?: string | null) => {
    if (activeAttemptId) {
      navigate(`/student/room/${activeAttemptId}`);
      return;
    }

    if (!window.confirm('Are you ready to start this assessment? Your timer will begin immediately upon starting.')) {
      return;
    }

    setIsStartingId(aId);
    setErrorMessage(null);
    try {
      const res = await startAssessmentAttempt(aId);
      if (res.data?.attempt_id) {
        navigate(`/student/room/${res.data.attempt_id}`);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to start assessment attempt.');
    } finally {
      setIsStartingId(null);
    }
  };

  const now = new Date();

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-slate-200 pb-6">
        <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
          <FileText className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">My Assigned Assessments</h1>
          <p className="text-sm text-slate-600">
            View available technical assessments, scheduled deadlines, and take your exams
          </p>
        </div>
      </div>

      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-sm font-mono">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {isLoading ? (
        <div className="py-16 flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-500 font-mono">Loading assigned assessments...</p>
        </div>
      ) : assessments.length === 0 ? (
        <Card className="p-12 text-center space-y-3 border-slate-200 bg-white shadow-sm">
          <FileText className="w-10 h-10 text-slate-400 mx-auto" />
          <p className="text-slate-600 text-sm">You do not have any assessments assigned at this time.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {assessments.map((a) => {
            const startDate = new Date(a.start_datetime);
            const endDate = new Date(a.end_datetime);
            const isUpcoming = now < startDate;
            const isExpired = now >= endDate;
            const isActive = !isUpcoming && !isExpired;
            const hasAttemptsLeft = a.attempts_used < a.attempt_limit;
            const hasActiveAttempt = Boolean(a.active_attempt_id);

            return (
              <Card
                key={a.id}
                className="p-6 flex flex-col justify-between space-y-6 border-slate-200 bg-white shadow-sm hover:border-emerald-300 transition-colors"
              >
                <div className="space-y-4">
                  {/* Status Badges */}
                  <div className="flex items-center justify-between">
                    <Badge
                      variant={
                        hasActiveAttempt
                          ? 'warning'
                          : isActive && hasAttemptsLeft
                          ? 'success'
                          : isUpcoming
                          ? 'info'
                          : 'neutral'
                      }
                    >
                      {hasActiveAttempt
                        ? 'IN PROGRESS'
                        : isActive && hasAttemptsLeft
                        ? 'AVAILABLE NOW'
                        : isUpcoming
                        ? 'UPCOMING'
                        : 'EXPIRED / COMPLETED'}
                    </Badge>

                    <span className="text-xs font-mono font-bold text-emerald-700">
                      {a.total_points} Points
                    </span>
                  </div>

                  {/* Title & Description */}
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">{a.title}</h3>
                    <p className="text-xs text-slate-600 mt-1 line-clamp-2">{a.description}</p>
                  </div>

                  {/* Meta Details */}
                  <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-amber-600" />
                      <span>Duration: <strong>{a.duration_minutes}m</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-purple-600" />
                      <span>Attempts: <strong>{a.attempts_used}/{a.attempt_limit}</strong></span>
                    </div>
                    <div className="col-span-2 flex items-center gap-1.5 text-[11px] text-slate-500 border-t border-slate-200 pt-2 mt-1">
                      <Calendar className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Window: {startDate.toLocaleDateString()} – {endDate.toLocaleDateString()}</span>
                    </div>
                  </div>

                  {a.instructions && (
                    <p className="text-xs text-slate-500 italic">
                      <strong>Instructions:</strong> {a.instructions}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="pt-2 border-t border-slate-100 flex justify-end">
                  {hasActiveAttempt ? (
                    <Button
                      variant="primary"
                      size="md"
                      className="w-full bg-amber-600 hover:bg-amber-700 text-white"
                      onClick={() => handleStartAttempt(a.id, a.active_attempt_id)}
                    >
                      <Play className="w-4 h-4 mr-2" />
                      Resume Test Attempt
                    </Button>
                  ) : isActive && hasAttemptsLeft ? (
                    <Button
                      variant="primary"
                      size="md"
                      className="w-full"
                      isLoading={isStartingId === a.id}
                      onClick={() => handleStartAttempt(a.id)}
                    >
                      <Play className="w-4 h-4 mr-2" />
                      Start Assessment
                    </Button>
                  ) : isUpcoming ? (
                    <Button variant="secondary" size="md" className="w-full" disabled>
                      <Clock className="w-4 h-4 mr-2" />
                      Starts {startDate.toLocaleDateString()}
                    </Button>
                  ) : a.attempts_used > 0 ? (
                    <Button
                      variant="secondary"
                      size="md"
                      className="w-full text-emerald-700 border-emerald-200 hover:bg-emerald-50"
                      onClick={() => navigate(`/student/results/${a.id}`)}
                    >
                      <Award className="w-4 h-4 mr-2" />
                      View Results & Scorecard
                    </Button>
                  ) : (
                    <Button variant="ghost" size="md" className="w-full" disabled>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Assessment Completed
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default StudentAssessmentsPage;
