import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { InvigilationAPI } from '../../api/invigilation';
import { ProctorAssignment } from '../../types/invigilation';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  Shield,
  Users,
  AlertTriangle,
  Eye,
  Radio
} from 'lucide-react';

export const ProctorDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [assignments, setAssignments] = useState<ProctorAssignment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    loadAssignedAssessments();
  }, []);

  const loadAssignedAssessments = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await InvigilationAPI.getAssignedAssessments();
      setAssignments(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setErrorMessage(err?.error?.message || err.message || 'Failed to load assigned invigilation cohorts.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Proctor Navigation Shell Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Proctor Invigilation Console</h1>
            <p className="text-xs text-slate-500">Live supervision, triage queues, and intervention controls</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 bg-white p-1 rounded-xl border border-slate-200 shadow-sm text-xs font-medium">
          <Link to="/proctor" className="px-3 py-1.5 rounded-lg bg-amber-50 text-amber-800 font-semibold border border-amber-200">
            Live Assessments
          </Link>
          <span className="px-3 py-1.5 rounded-lg text-slate-400 cursor-not-allowed">
            Interventions
          </span>
          <span className="px-3 py-1.5 rounded-lg text-slate-400 cursor-not-allowed">
            Chat Logs
          </span>
        </div>
      </div>

      {/* Proctor Identity & Status Card */}
      <div className="rounded-2xl bg-white border border-slate-200 p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-800 flex items-center justify-center font-bold text-xl">
            <Shield className="w-6 h-6 stroke-[2.2]" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">{user?.email}</h2>
              <Badge variant="warning" size="sm">PROCTOR</Badge>
            </div>
            <p className="text-xs text-slate-500 font-mono">
              Authorized Invigilator &bull; Assessment-Scoped Access
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={loadAssignedAssessments} isLoading={isLoading}>
            Refresh Cohorts
          </Button>
        </div>
      </div>

      {/* Error Notice if any */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Assigned Cohorts Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900">Assigned Examination Cohorts</h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono border border-slate-200">
              {assignments.length}
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="p-12 rounded-2xl bg-white border border-slate-200 text-center text-xs text-slate-500 shadow-sm">
            Connecting to invigilation roster service...
          </div>
        ) : assignments.length === 0 ? (
          <Card className="p-10 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mx-auto">
              <Users className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-slate-900">No Active Assessment Assignments</h4>
            <p className="text-xs text-slate-600 max-w-md mx-auto leading-relaxed">
              You are currently not assigned to any active examination cohorts. 
              An administrator must grant an explicit assessment-scoped ProctorAssignment before candidates become visible in your triage queue.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {assignments.map((assignment) => (
              <Card key={assignment.id} className="p-6 space-y-5 hover:border-amber-400 transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <h4 className="text-base font-bold text-slate-900">{assignment.assessment_title}</h4>
                    <p className="text-[11px] text-slate-500 font-mono">ID: {assignment.assessment}</p>
                  </div>
                  <Badge variant="warning" size="sm">ACTIVE</Badge>
                </div>

                <div className="space-y-2 pt-3 border-t border-slate-100 text-xs text-slate-600 font-mono">
                  <div className="flex items-center justify-between">
                    <span>Max Candidates:</span>
                    <strong className="text-slate-800">{assignment.max_candidates}</strong>
                  </div>
                  {assignment.notes && (
                    <div className="text-[11px] text-slate-500 italic truncate">
                      Notes: {assignment.notes}
                    </div>
                  )}
                </div>

                <div className="pt-2">
                  <Button
                    variant="primary"
                    size="md"
                    className="w-full flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 text-white font-semibold"
                    onClick={() => navigate(`/proctor/console/${assignment.assessment}`)}
                  >
                    <Eye className="w-4 h-4" />
                    <span>Launch Live Triage Console</span>
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProctorDashboardPage;
