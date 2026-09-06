import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getAdminAssessments, archiveAssessment, publishAssessment } from '../../api/assessments';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { PageHeader } from '../../components/common/PageHeader';
import { Tabs, TabItem } from '../../components/common/Tabs';
import { AssessmentAssignmentsModal } from './AssessmentAssignmentsModal';
import {
  FileText,
  Plus,
  Search,
  Users,
  Edit,
  Archive,
  AlertCircle,
  Calendar,
  Clock,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Award,
  CheckCircle2,
  ClipboardList,
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

  const [publishingId, setPublishingId] = useState<string | null>(null);

  const handlePublishFromList = async (a: AssessmentAdminItem) => {
    if (
      !window.confirm(
        `Are you sure you want to publish "${a.title}"? Once published, the assessment and its question snapshot will become permanently immutable.`
      )
    ) {
      return;
    }
    setPublishingId(a.id);
    setErrorMessage(null);
    try {
      await publishAssessment(a.id);
      fetchAssessments();
    } catch (err: any) {
      const details = err.error?.details;
      let detailedMsg = err.error?.message;
      if (details && typeof details === 'object') {
        const fieldMsgs = Object.entries(details).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        if (fieldMsgs.length > 0) detailedMsg = fieldMsgs.join(' | ');
      }
      setErrorMessage(detailedMsg || err.message || 'Failed to publish assessment.');
    } finally {
      setPublishingId(null);
    }
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  const statusTabs: TabItem<'ALL' | 'PUBLISHED' | 'DRAFT' | 'ARCHIVED'>[] = [
    { id: 'ALL', label: 'ALL' },
    { id: 'PUBLISHED', label: 'PUBLISHED' },
    { id: 'DRAFT', label: 'DRAFTS' },
    { id: 'ARCHIVED', label: 'ARCHIVED' },
  ];

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-7xl">
      {/* Top Header */}
      <PageHeader
        icon={<FileText className="w-6 h-6" />}
        title="Assessments & Exams"
        description="Design, schedule, assign, and publish technical evaluations from the Question Bank"
        actions={
          <Link to="/admin/assessments/create">
            <Button variant="primary" size="md">
              <Plus className="w-4 h-4 mr-2" />
              Create Assessment
            </Button>
          </Link>
        }
      />

      {/* Tabs & Search Bar */}
      <Card className="p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Status Tabs */}
          <Tabs
            variant="pills"
            tabs={statusTabs}
            activeTab={activeTab}
            onChange={(tab) => {
              setActiveTab(tab);
              setCurrentPage(1);
            }}
          />

          {/* Search Input */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full sm:w-auto">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search assessment title, description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3.5 py-2 rounded-lg bg-white border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
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
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Assessment Roster Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-500 font-mono">Loading assessment catalog...</p>
          </div>
        ) : assessments.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <p className="text-slate-500 text-sm">No assessments found matching criteria.</p>
            <Link to="/admin/assessments/create">
              <Button variant="secondary" size="sm">
                Create First Assessment
              </Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="px-4 py-3.5">Assessment Title</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">Schedule Window</th>
                  <th className="px-4 py-3.5">Duration</th>
                  <th className="px-4 py-3.5">Questions</th>
                  <th className="px-4 py-3.5">Points</th>
                  <th className="px-4 py-3.5">Assigned Students</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {assessments.map((a) => {
                  const isDraft = a.status === 'DRAFT';
                  const isPublished = a.status === 'PUBLISHED';

                  return (
                    <tr key={a.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3.5 max-w-xs">
                        <div className="font-sans font-bold text-slate-900 text-sm truncate">
                          {a.title}
                        </div>
                        <div className="text-[10px] text-slate-500">
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
                      <td className="px-4 py-3.5 text-[11px] text-slate-600">
                        <div className="flex items-center gap-1 text-slate-700">
                          <Calendar className="w-3.5 h-3.5 text-emerald-600" />
                          <span>{new Date(a.start_datetime).toLocaleDateString()}</span>
                        </div>
                        <div className="text-[10px] text-slate-400">
                          to {new Date(a.end_datetime).toLocaleDateString()}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="flex items-center gap-1 text-slate-700 font-medium">
                          <Clock className="w-3.5 h-3.5 text-amber-600" />
                          {a.duration_minutes}m
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-slate-900 font-bold">
                        {a.question_count} Qs
                      </td>
                      <td className="px-4 py-3.5 font-bold text-emerald-700">
                        {a.total_points} pts
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => {
                            setSelectedAssessmentForAssign(a);
                            setIsAssignModalOpen(true);
                          }}
                          className="flex flex-col items-start gap-0.5 px-2.5 py-1.5 rounded-lg bg-purple-50 border border-purple-200 text-purple-700 hover:bg-purple-100 text-xs font-medium transition-colors"
                        >
                          <div className="flex items-center gap-1.5">
                            <Users className="w-3.5 h-3.5 text-purple-600" />
                            <span className="font-bold">
                              {isDraft
                                ? `${a.eligible_students_count ?? a.assigned_count} Targeted`
                                : `${a.assigned_count} Assigned`}
                            </span>
                          </div>
                          {a.target_sections_summary && a.target_sections_summary !== 'None' ? (
                            <span className="text-[10px] text-purple-800 font-mono font-semibold truncate max-w-[150px]" title={a.target_sections_summary}>
                              {a.target_sections_summary}
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-500 font-mono">
                              Direct / Custom
                            </span>
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-1 whitespace-nowrap">
                        {isPublished && (
                          <>
                            <Link to={`/admin/assessments/${a.id}/results`}>
                              <Button variant="secondary" size="sm" title="Assessment Results & Analytics">
                                <Award className="w-3.5 h-3.5 mr-1 text-amber-600" />
                                Results
                              </Button>
                            </Link>

                            <Link to={`/admin/assessments/${a.id}/proctoring`}>
                              <Button variant="secondary" size="sm" title="AI Proctoring Dashboard">
                                <ShieldAlert className="w-3.5 h-3.5 mr-1 text-indigo-600" />
                                Proctoring
                              </Button>
                            </Link>

                            <Link to={`/admin/assessments/${a.id}/attendance`}>
                              <Button variant="secondary" size="sm" title="Assessment Attendance & Roster">
                                <ClipboardList className="w-3.5 h-3.5 mr-1 text-teal-600" />
                                Attendance
                              </Button>
                            </Link>
                          </>
                        )}

                        <Link to={`/admin/assessments/${a.id}`}>
                          <Button variant="secondary" size="sm" title={isDraft ? "Edit Draft" : "View Assessment"}>
                            <Edit className="w-3.5 h-3.5 mr-1" />
                            {isDraft ? "Edit" : "View"}
                          </Button>
                        </Link>

                        {isDraft && (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handlePublishFromList(a)}
                            isLoading={publishingId === a.id}
                            title="Publish Assessment"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                            Publish
                          </Button>
                        )}

                        {isPublished && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleArchive(a.id)}
                            title="Archive Assessment"
                          >
                            <Archive className="w-3.5 h-3.5 text-slate-500 hover:text-rose-600" />
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
          <div className="p-4 border-t border-slate-200 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-500">
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
              <span className="text-slate-700 font-bold px-2">
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
