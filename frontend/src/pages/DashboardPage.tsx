import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { AdminAPI } from '../api/admin';
import { AdminDashboardOverview } from '../types/admin';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import {
  Shield,
  FileCode,
  Plus,
  Users,
  Calendar,
  Clock,
  ArrowRight,
  Code2,
  UserPlus,
  ShieldCheck,
  Award
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [overview, setOverview] = useState<AdminDashboardOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadOverview();
  }, []);

  const loadOverview = async () => {
    setIsLoading(true);
    try {
      const data = await AdminAPI.getOverview();
      setOverview(data);
    } catch {
      setOverview({
        metrics: {
          active_assessments: 0,
          upcoming_assessments: 0,
          completed_assessments: 0,
          total_students: 0,
        },
        recent_assessments: [],
        upcoming_assessments: [],
        recent_activity: [],
      });
    } finally {
      setIsLoading(false);
    }
  };

  const displayName = user?.display_name || user?.first_name || (user?.email ? user.email.split('@')[0] : 'Administrator');
  const adminId = user?.admin_id || '';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Welcome & Identity Card */}
      <div className="rounded-2xl bg-white border border-slate-200 p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-semibold">
                <Shield className="w-3.5 h-3.5 text-emerald-600" />
                Admin
              </span>
              <span className="px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-mono font-medium border border-slate-200">
                Admin ID: {adminId}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
              Welcome back, {displayName}
            </h1>
            <p className="text-sm text-slate-600 max-w-2xl leading-relaxed">
              Manage your assessments, candidates, results, and examination operations from one place.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link to="/admin/assessments/create">
              <Button variant="primary" size="md" className="flex items-center gap-1.5">
                <Plus className="w-4 h-4" />
                <span>Create Assessment</span>
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Operational Overview Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
            <FileCode className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900 font-sans">
              {isLoading ? '-' : overview?.metrics.active_assessments ?? 0}
            </div>
            <div className="text-xs text-slate-500 font-medium">Active Assessments</div>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900 font-sans">
              {isLoading ? '-' : overview?.metrics.total_students ?? 0}
            </div>
            <div className="text-xs text-slate-500 font-medium">Total Students</div>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900 font-sans">
              {isLoading ? '-' : overview?.metrics.upcoming_assessments ?? 0}
            </div>
            <div className="text-xs text-slate-500 font-medium">Upcoming Assessments</div>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 flex items-center justify-center">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-900 font-sans">
              {isLoading ? '-' : overview?.metrics.completed_assessments ?? 0}
            </div>
            <div className="text-xs text-slate-500 font-medium">Completed Assessments</div>
          </div>
        </Card>
      </div>

      {/* Quick Action Shortcuts */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link to="/admin/assessments/create">
            <Card className="p-4 flex items-center gap-3 hover:border-emerald-300 transition-colors group">
              <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center group-hover:bg-emerald-100 transition-colors">
                <Plus className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                  Create Assessment
                </div>
                <div className="text-xs text-slate-500">Author & schedule exam</div>
              </div>
            </Card>
          </Link>

          <Link to="/admin/questions/create?type=CODING">
            <Card className="p-4 flex items-center gap-3 hover:border-emerald-300 transition-colors group">
              <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center group-hover:bg-emerald-100 transition-colors">
                <Code2 className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                  Add Coding Question
                </div>
                <div className="text-xs text-slate-500">Single-page authoring workspace</div>
              </div>
            </Card>
          </Link>

          <Link to="/admin/students">
            <Card className="p-4 flex items-center gap-3 hover:border-emerald-300 transition-colors group">
              <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                <UserPlus className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 group-hover:text-blue-800 transition-colors">
                  Add Student
                </div>
                <div className="text-xs text-slate-500">Register candidates or CSV</div>
              </div>
            </Card>
          </Link>

          <Link to="/admin/administrators">
            <Card className="p-4 flex items-center gap-3 hover:border-emerald-300 transition-colors group">
              <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center group-hover:bg-purple-100 transition-colors">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 group-hover:text-purple-800 transition-colors">
                  Manage Administrators
                </div>
                <div className="text-xs text-slate-500">View and manage admin accounts</div>
              </div>
            </Card>
          </Link>
        </div>
      </div>

      {/* Main Content Grid: Recent Assessments & Upcoming Examinations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left 2 Columns: Recent Assessments */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900">Recent Assessments</h2>
            <Link to="/admin/assessments" className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 flex items-center gap-1">
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <Card className="p-0 overflow-hidden shadow-sm">
            {isLoading ? (
              <div className="p-8 text-center text-xs text-slate-500">Loading assessments...</div>
            ) : !overview?.recent_assessments || overview.recent_assessments.length === 0 ? (
              <div className="p-10 text-center space-y-3">
                <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
                  <FileCode className="w-5 h-5" />
                </div>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  No assessments authored yet. Click 'Create Assessment' above to get started.
                </p>
                <Link to="/admin/assessments/create">
                  <Button variant="secondary" size="sm">
                    Create First Assessment
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="px-5 py-3">Assessment</th>
                      <th className="px-5 py-3">Date Window</th>
                      <th className="px-5 py-3">Candidates</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {overview.recent_assessments.map((a) => (
                      <tr key={a.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-5 py-3.5 font-semibold text-slate-900 max-w-[220px] truncate">
                          {a.title}
                        </td>
                        <td className="px-5 py-3.5 text-slate-500 font-mono">
                          {a.start_datetime ? new Date(a.start_datetime).toLocaleDateString() : 'Unscheduled'}
                        </td>
                        <td className="px-5 py-3.5 text-slate-700 font-mono">
                          {a.candidates_count} assigned
                        </td>
                        <td className="px-5 py-3.5">
                          <Badge
                            variant={
                              a.status === 'PUBLISHED'
                                ? 'success'
                                : a.status === 'DRAFT'
                                ? 'warning'
                                : 'neutral'
                            }
                            size="sm"
                          >
                            {a.status}
                          </Badge>
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <Link
                            to={`/admin/assessments/${a.id}`}
                            className="text-emerald-700 hover:text-emerald-800 font-semibold"
                          >
                            Manage
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        {/* Right 1 Column: Upcoming Examinations & Question Bank Shortcuts */}
        <div className="space-y-6">
          {/* Upcoming Examinations */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-900">Upcoming Examinations</h2>
              <span className="text-[11px] font-mono text-slate-500">
                {overview?.upcoming_assessments?.length || 0} Scheduled
              </span>
            </div>
            <Card className="p-4 space-y-3 shadow-sm">
              {isLoading ? (
                <div className="p-4 text-center text-xs text-slate-500">Loading schedule...</div>
              ) : !overview?.upcoming_assessments || overview.upcoming_assessments.length === 0 ? (
                <div className="text-center py-6 space-y-2">
                  <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
                    <Calendar className="w-4 h-4" />
                  </div>
                  <p className="text-xs text-slate-500">
                    No upcoming examinations scheduled.
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {overview.upcoming_assessments.map((u) => (
                    <div
                      key={u.id}
                      className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-slate-300 transition-colors flex items-start justify-between gap-3"
                    >
                      <div className="space-y-1 min-w-0">
                        <div className="text-xs font-bold text-slate-900 leading-snug truncate">{u.title}</div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-2 font-mono">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-slate-400" />
                            {u.duration_minutes}m
                          </span>
                          <span>&bull;</span>
                          <span>{u.start_datetime ? new Date(u.start_datetime).toLocaleDateString() : 'TBD'}</span>
                        </div>
                      </div>
                      <Badge variant="info" size="sm">
                        {u.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Quick Problem Authoring & Import */}
          <div className="space-y-3">
            <h2 className="text-base font-bold text-slate-900">Question Authoring</h2>
            <Card className="p-4 space-y-3 shadow-sm bg-gradient-to-br from-slate-50 to-white border-slate-200">
              <p className="text-xs text-slate-600 leading-relaxed">
                Author sandboxed coding challenges or import authorized problems into the CODEGUARD question bank.
              </p>
              <div className="flex flex-col gap-2 pt-1">
                <Link to="/admin/questions/create?type=CODING" className="w-full">
                  <Button variant="primary" size="sm" className="w-full justify-center">
                    <Code2 className="w-3.5 h-3.5 mr-1.5" />
                    New Coding Question
                  </Button>
                </Link>
                <Link to="/admin/questions" className="w-full">
                  <Button variant="secondary" size="sm" className="w-full justify-center">
                    <span>Open Question Bank</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Button>
                </Link>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
