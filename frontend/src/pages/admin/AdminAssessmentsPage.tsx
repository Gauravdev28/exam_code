import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getAdminAssessments, archiveAssessment, deleteAssessment } from '../../api/assessments';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { AssessmentAssignmentsModal } from './AssessmentAssignmentsModal';
import {
  FileText,
  Plus,
  Search,
  Users,
  Edit,
  Archive,
  Trash2,
  AlertCircle,
  Calendar,
  Clock,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Award,
} from 'lucide-react';
import { AssessmentAdminItem } from '../../types/assessment';

export const AdminAssessmentsPage: React.FC = () => {
  const [assessments, setAssessments] = useState<AssessmentAdminItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'ALL' | 'PUBLISHED' | 'DRAFT' | 'ARCHIVED'>('ALL');

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Assignments modal state
  const [selectedAssessmentForAssign, setSelectedAssessmentForAssign] = useState<AssessmentAdminItem | null>(null);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);

  const fetchAssessments = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const filters: any = {
        page: currentPage,
        page_size: pageSize,
      };

      if (searchQuery.trim()) filters.search = searchQuery.trim();
      if (activeTab !== 'ALL') filters.status = activeTab;

      const res = await getAdminAssessments(filters);
      if (res.data) {
        setAssessments(res.data.results);
        setTotalCount(res.data.count);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load assessments.');
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, searchQuery, activeTab]);

  useEffect(() => {
    fetchAssessments();
  }, [fetchAssessments]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchAssessments();
  };

  const handleArchive = async (aId: string) => {
    if (!window.confirm('Are you sure you want to archive this assessment?')) return;
    try {
      await archiveAssessment(aId);
      fetchAssessments();
    } catch (err: any) {
      alert(err.error?.message || 'Failed to archive assessment.');
    }
  };

  const handleDelete = async (aId: string) => {
    if (!window.confirm('Are you sure you want to delete this draft assessment?')) return;
    try {
      await deleteAssessment(aId);
      fetchAssessments();
    } catch (err: any) {
      alert(err.error?.message || 'Failed to delete assessment.');
    }
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-7xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-900 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Assessments & Exams</h1>
              <p className="text-sm text-slate-400">
                Design, schedule, assign, and publish technical evaluations from the Question Bank
              </p>
            </div>
          </div>
        </div>

        <Link to="/admin/assessments/create">
          <Button variant="primary" size="md">
            <Plus className="w-4 h-4 mr-2" />
            Create Assessment
          </Button>
        </Link>
      </div>

      {/* Tabs & Search Bar */}
      <Card className="p-4 space-y-4 border-slate-800/80 bg-slate-950/60">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Status Tabs */}
          <div className="flex items-center gap-2">
            {(['ALL', 'PUBLISHED', 'DRAFT', 'ARCHIVED'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => {
                  setActiveTab(tab);
                  setCurrentPage(1);
                }}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                  activeTab === tab
                    ? 'bg-brand-500/20 text-brand-300 border border-brand-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                {tab === 'DRAFT' ? 'DRAFTS' : tab}
              </button>
            ))}
          </div>

          {/* Search Input */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full sm:w-auto">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search assessment title, description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm">
              Search
            </Button>
          </form>
        </div>
      </Card>

      {/* Error Notice */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-3 text-red-300 text-sm">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Assessment Roster Table */}
      <Card className="overflow-hidden border-slate-800/80">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400 font-mono">Loading assessment catalog...</p>
          </div>
        ) : assessments.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <p className="text-slate-400 text-sm">No assessments found matching criteria.</p>
            <Link to="/admin/assessments/create">
              <Button variant="secondary" size="sm">
                Create First Assessment
              </Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Assessment Title</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Schedule Window</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Questions</th>
                  <th className="px-4 py-3">Points</th>
                  <th className="px-4 py-3">Assigned Students</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {assessments.map((a) => {
                  const isDraft = a.status === 'DRAFT';
                  const isPublished = a.status === 'PUBLISHED';

                  return (
                    <tr key={a.id} className="hover:bg-slate-900/40 transition-colors">
                      <td className="px-4 py-3.5 max-w-xs">
                        <div className="font-sans font-bold text-slate-100 text-sm truncate">
                          {a.title}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          Created by: {a.created_by_email || 'Admin'}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <Badge
                          variant={
                            a.status === 'PUBLISHED'
                              ? 'success'
                              : a.status === 'DRAFT'
                              ? 'warning'
                              : 'neutral'
                          }
                        >
                          {a.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3.5 text-[11px] text-slate-300">
                        <div className="flex items-center gap-1 text-slate-400">
                          <Calendar className="w-3.5 h-3.5 text-brand-400" />
                          <span>{new Date(a.start_datetime).toLocaleDateString()}</span>
                        </div>
                        <div className="text-[10px] text-slate-500">
                          to {new Date(a.end_datetime).toLocaleDateString()}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="flex items-center gap-1 text-slate-300">
                          <Clock className="w-3.5 h-3.5 text-amber-400" />
                          {a.duration_minutes}m
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-slate-200 font-bold">
                        {a.question_count} Qs
                      </td>
                      <td className="px-4 py-3.5 font-bold text-brand-400">
                        {a.total_points} pts
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => {
                            setSelectedAssessmentForAssign(a);
                            setIsAssignModalOpen(true);
                          }}
                          className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800/80 border border-slate-700 text-purple-300 hover:bg-slate-800 text-xs"
                        >
                          <Users className="w-3.5 h-3.5 text-purple-400" />
                          <span>{a.assigned_count} Assigned</span>
                        </button>
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-1 whitespace-nowrap">
                        <Link to={`/admin/assessments/${a.id}/results`}>
                          <Button variant="secondary" size="sm" title="Assessment Results & Analytics">
                            <Award className="w-3.5 h-3.5 mr-1 text-amber-400" />
                            Results
                          </Button>
                        </Link>

                        <Link to={`/admin/assessments/${a.id}/proctoring`}>
                          <Button variant="secondary" size="sm" title="AI Proctoring Dashboard">
                            <ShieldAlert className="w-3.5 h-3.5 mr-1 text-indigo-400" />
                            Proctoring
                          </Button>
                        </Link>

                        <Link to={`/admin/assessments/${a.id}`}>
                          <Button variant="secondary" size="sm" title={isDraft ? "Edit Draft" : "View Assessment"}>
                            <Edit className="w-3.5 h-3.5 mr-1" />
                            {isDraft ? "Edit" : "View"}
                          </Button>
                        </Link>

                        {isPublished && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleArchive(a.id)}
                            title="Archive Assessment"
                          >
                            <Archive className="w-3.5 h-3.5 text-slate-500 hover:text-red-400" />
                          </Button>
                        )}

                        {isDraft && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(a.id)}
                            title="Delete Draft"
                          >
                            <Trash2 className="w-3.5 h-3.5 text-slate-500 hover:text-red-400" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-400">
              Showing {(currentPage - 1) * pageSize + 1} to{' '}
              {Math.min(currentPage * pageSize, totalCount)} of {totalCount} assessments
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                Previous
              </Button>
              <span className="text-slate-300 font-bold px-2">
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
                <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Assignment Management Modal */}
      {selectedAssessmentForAssign && (
        <AssessmentAssignmentsModal
          assessmentId={selectedAssessmentForAssign.id}
          assessmentTitle={selectedAssessmentForAssign.title}
          isOpen={isAssignModalOpen}
          onClose={() => {
            setIsAssignModalOpen(false);
            setSelectedAssessmentForAssign(null);
          }}
          onAssignmentsUpdated={fetchAssessments}
        />
      )}
    </div>
  );
};

export default AdminAssessmentsPage;
