import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { getStudentAssessments } from '../../api/assessments';
import { ResultsAPI } from '../../api/results';
import { StudentAssessmentItem } from '../../types/assessment';
import { AssessmentResult } from '../../types/results';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  FileCode,
  Clock,
  Calendar,
  CheckCircle2,
  Award,
  Play,
  ArrowRight,
  BookOpen
} from 'lucide-react';

export const StudentDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [assessments, setAssessments] = useState<StudentAssessmentItem[]>([]);
  const [results, setResults] = useState<AssessmentResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [assessmentRes, resultsRes] = await Promise.allSettled([
        getStudentAssessments(),
        ResultsAPI.getStudentResults(1),
      ]);

      if (assessmentRes.status === 'fulfilled' && assessmentRes.value.data) {
        setAssessments(assessmentRes.value.data);
      }

      if (resultsRes.status === 'fulfilled' && resultsRes.value?.results) {
        setResults(resultsRes.value.results);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const getStatus = (item: StudentAssessmentItem): 'IN_PROGRESS' | 'COMPLETED' | 'AVAILABLE' => {
    if (item.active_attempt_id) return 'IN_PROGRESS';
    if (item.attempts_used >= item.attempt_limit && item.attempt_limit > 0) return 'COMPLETED';
    return 'AVAILABLE';
  };

  const activeAssessments = assessments.filter(
    (a) => getStatus(a) === 'AVAILABLE' || getStatus(a) === 'IN_PROGRESS'
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Student Navigation Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Student Workspace</h1>
            <p className="text-xs text-slate-500">Manage your examinations, live test rooms, and score reports</p>
          </div>
        </div>

        {/* Quick Nav Tabs */}
        <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200 shadow-sm text-xs font-medium">
          <Link to="/student" className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
            Dashboard
          </Link>
          <Link to="/student/assessments" className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors">
            My Assessments
          </Link>
          <Link to="/student/privacy" className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors">
            Privacy & Rights
          </Link>
          <Link to="/student/profile" className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors">
            Profile
          </Link>
        </div>
      </div>

      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-white border border-slate-200 p-8 shadow-sm">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <Badge variant="success" dot size="md">
                STUDENT
              </Badge>
              {user?.student_profile?.roll_number && (
                <Badge variant="neutral">
                  ROLL: {user.student_profile.roll_number}
                </Badge>
              )}
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 font-sans">
              Welcome back, {user?.email}
            </h2>
            <p className="text-xs text-slate-500 font-mono">
              EUID: {user?.student_profile?.euid || user?.id}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link to="/student/assessments">
              <Button variant="primary" size="md" className="flex items-center gap-2">
                <span>View All Exams</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Candidate Overview Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
            <FileCode className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900 font-sans">{activeAssessments.length}</div>
            <div className="text-xs text-slate-500">Available Exams</div>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 flex items-center justify-center">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900 font-sans">{results.length}</div>
            <div className="text-xs text-slate-500">Completed Assessments</div>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900 font-sans">
              {results.filter((r) => r.is_passed).length}
            </div>
            <div className="text-xs text-slate-500">Passed Assessments</div>
          </div>
        </Card>
      </div>

      {/* Active / Assigned Assessments */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900">Your Scheduled Examinations</h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-mono border border-emerald-200">
              {assessments.length}
            </span>
          </div>
          <Link to="/student/assessments" className="text-xs font-medium text-emerald-700 hover:text-emerald-800 flex items-center gap-1">
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {isLoading ? (
          <div className="p-12 rounded-xl bg-white border border-slate-200 text-center text-xs text-slate-500 shadow-sm">
            Loading scheduled examinations...
          </div>
        ) : assessments.length === 0 ? (
          <Card className="p-8 text-center space-y-3">
            <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-500 mx-auto flex items-center justify-center">
              <FileCode className="w-5 h-5" />
            </div>
            <h4 className="text-sm font-semibold text-slate-900">No Assigned Assessments</h4>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              You currently have no pending assessments assigned to your candidate profile. 
              Assessments will appear here once scheduled by your instructor or institution.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {assessments.map((item) => {
              const status = getStatus(item);
              return (
                <Card key={item.id} className="p-6 space-y-4 hover:border-emerald-300 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <h4 className="text-base font-bold text-slate-900">{item.title}</h4>
                      <p className="text-xs text-slate-600 line-clamp-2">{item.description}</p>
                    </div>
                    <Badge
                      variant={
                        status === 'IN_PROGRESS'
                          ? 'warning'
                          : status === 'COMPLETED'
                          ? 'success'
                          : 'info'
                      }
                      size="sm"
                    >
                      {status.replace('_', ' ')}
                    </Badge>
                  </div>

                  <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 font-mono pt-2 border-t border-slate-100">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>{item.duration_minutes} Mins</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>{new Date(item.start_datetime).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="pt-2">
                    {status === 'IN_PROGRESS' ? (
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 text-white"
                        onClick={() => navigate(`/student/room/${item.active_attempt_id}`)}
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Resume In-Progress Exam</span>
                      </Button>
                    ) : status === 'COMPLETED' ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        className="w-full flex items-center justify-center gap-2"
                        onClick={() => navigate('/student/assessments')}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>View Submission Status</span>
                      </Button>
                    ) : (
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full flex items-center justify-center gap-2"
                        onClick={() => navigate('/student/assessments')}
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Enter Assessment Room</span>
                      </Button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent Finalized Results Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900">Recent Assessment Results</h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono border border-slate-200">
              {results.length}
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 rounded-xl bg-white border border-slate-200 text-center text-xs text-slate-500 shadow-sm">
            Loading examination results...
          </div>
        ) : results.length === 0 ? (
          <Card className="p-6 text-center space-y-2">
            <p className="text-xs text-slate-500">
              No finalized results published yet. Results become accessible after institutional evaluation release.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {results.slice(0, 3).map((res) => (
              <div key={res.id} className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <div className="text-sm font-semibold text-slate-900">{res.assessment_title}</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Score: <strong className="text-slate-800">{res.total_score_earned}</strong> / {res.total_possible_score} ({res.percentage}%)
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={res.is_passed ? 'success' : 'danger'} size="sm">
                    {res.is_passed ? 'PASSED' : 'NOT PASSED'}
                  </Badge>
                  <Link to={`/student/results/${res.id}`}>
                    <Button variant="outline" size="sm">
                      View Scorecard
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default StudentDashboardPage;
