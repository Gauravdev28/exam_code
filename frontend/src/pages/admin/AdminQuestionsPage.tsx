import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  getQuestions,
  archiveQuestion,
  createNewVersion,
  createQuestion,
  getQuestionVersionDetail,
} from '../../api/questions';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { PageHeader } from '../../components/common/PageHeader';
import { Tabs, TabItem } from '../../components/common/Tabs';
import { QuestionPreviewModal } from '../../components/admin/QuestionPreviewModal';
import { ImportQuestionsSpreadsheetModal } from '../../components/admin/ImportQuestionsSpreadsheetModal';
import { ExtractQuestionImageModal } from '../../components/admin/ExtractQuestionImageModal';
import { CreateQuestionModal } from '../../components/admin/CreateQuestionModal';
import { DeleteQuestionModal } from '../../components/admin/DeleteQuestionModal';
import {
  HelpCircle,
  Plus,
  Search,
  Eye,
  Edit,
  GitBranch,
  Archive,
  AlertCircle,
  Filter,
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  Image as ImageIcon,
  Copy,
  Trash2,
} from 'lucide-react';
import { QuestionItem } from '../../types/question';

export const AdminQuestionsPage: React.FC = () => {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'ALL' | 'PUBLISHED' | 'DRAFT' | 'ARCHIVED'>('ALL');
  const [selectedType, setSelectedType] = useState('');
  const [selectedDifficulty, setSelectedDifficulty] = useState('');

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals state
  const [previewQuestionId, setPreviewQuestionId] = useState<string | null>(null);
  const [previewVersionNumber, setPreviewVersionNumber] = useState<number | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isExtractModalOpen, setIsExtractModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [deleteTargetQuestion, setDeleteTargetQuestion] = useState<QuestionItem | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const fetchQuestions = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const filters: any = {
        page: currentPage,
        page_size: pageSize,
      };

      if (searchQuery.trim()) filters.search = searchQuery.trim();
      if (selectedType) filters.type = selectedType;
      if (selectedDifficulty) filters.difficulty = selectedDifficulty;

      if (activeTab === 'PUBLISHED') filters.version_status = 'PUBLISHED';
      else if (activeTab === 'DRAFT') filters.version_status = 'DRAFT';
      else if (activeTab === 'ARCHIVED') filters.status = 'ARCHIVED';

      const res = await getQuestions(filters);
      if (res.data) {
        setQuestions(res.data.results);
        setTotalCount(res.data.count);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load question bank.');
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, searchQuery, activeTab, selectedType, selectedDifficulty]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchQuestions();
  };

  const handleOpenPreview = (qId: string, vNum: number) => {
    setPreviewQuestionId(qId);
    setPreviewVersionNumber(vNum);
    setIsPreviewOpen(true);
  };

  const handleArchive = async (qId: string) => {
    if (!window.confirm('Are you sure you want to archive this question?')) return;
    try {
      await archiveQuestion(qId);
      fetchQuestions();
    } catch (err: any) {
      alert(err.error?.message || 'Failed to archive question.');
    }
  };

  const handleCreateNewVersion = async (qId: string) => {
    try {
      const res = await createNewVersion(qId);
      if (res.data) {
        navigate(`/admin/questions/${qId}/versions/${res.data.version_number}`);
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to create new draft version.');
    }
  };

  const handleDuplicate = async (q: QuestionItem) => {
    const targetVer = q.latest_version;
    if (!targetVer) return;
    try {
      const detailRes = await getQuestionVersionDetail(q.id, targetVer.version_number);
      const d = detailRes.data;
      if (!d) return;

      const res = await createQuestion({
        question_type: q.question_type,
        title: `Copy of ${d.title}`,
        description: d.description || '',
        instructions: d.instructions || '',
        points: d.points || 10,
        difficulty: d.difficulty || 'MEDIUM',
        tags: d.tags ? d.tags.map((t: any) => t.name || t) : [],
        type_config: d.type_config || {},
        coding_config: d.coding_config || {},
        test_cases: d.coding_config?.test_cases || [],
        sql_config: d.sql_config || {},
      });
      if (res.data) {
        fetchQuestions();
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to duplicate question.');
    }
  };

  const handleOpenDeleteModal = (q: QuestionItem) => {
    setDeleteTargetQuestion(q);
    setIsDeleteModalOpen(true);
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
        icon={<HelpCircle className="w-6 h-6" />}
        title="Question Bank"
        description="Manage, version, and configure academic assessment questions across 6 core types"
        actions={
          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              variant="secondary"
              size="md"
              onClick={() => setIsImportModalOpen(true)}
              className="text-slate-800 bg-white hover:bg-slate-50 border-slate-300 font-semibold"
            >
              <FileSpreadsheet className="w-4 h-4 mr-1.5 text-purple-600" />
              Import Excel / CSV
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => setIsExtractModalOpen(true)}
              className="text-slate-800 bg-white hover:bg-slate-50 border-slate-300 font-semibold"
            >
              <ImageIcon className="w-4 h-4 mr-1.5 text-blue-600" />
              Extract from Image
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={() => setIsCreateModalOpen(true)}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Create Question
            </Button>
          </div>
        }
      />

      {/* Tabs & Filters Bar */}
      <Card className="p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
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
                placeholder="Search title, prompt, tags..."
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

        {/* Dropdown Filters */}
        <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-slate-600 font-semibold">Filter By:</span>
          </div>

          <select
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 text-xs"
          >
            <option value="">All Question Types</option>
            <option value="CODING">Coding</option>
            <option value="MCQ">MCQ</option>
            <option value="MULTI_SELECT">Multi-Select</option>
            <option value="TRUE_FALSE">True / False</option>
            <option value="SHORT_ANSWER">Short Answer</option>
            <option value="SQL">SQL</option>
          </select>

          <select
            value={selectedDifficulty}
            onChange={(e) => {
              setSelectedDifficulty(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 text-xs"
          >
            <option value="">All Difficulties</option>
            <option value="EASY">Easy</option>
            <option value="MEDIUM">Medium</option>
            <option value="HARD">Hard</option>
          </select>

          {(selectedType || selectedDifficulty || searchQuery) && (
            <button
              onClick={() => {
                setSelectedType('');
                setSelectedDifficulty('');
                setSearchQuery('');
                setCurrentPage(1);
              }}
              className="text-emerald-700 hover:text-emerald-800 hover:underline text-xs font-semibold"
            >
              Reset Filters
            </button>
          )}
        </div>
      </Card>

      {/* Error Notice */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Questions Roster Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-500 font-mono">Querying question catalog...</p>
          </div>
        ) : questions.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <p className="text-slate-500 text-sm">No questions found matching the selected criteria.</p>
            <Button variant="secondary" size="sm" onClick={() => setIsCreateModalOpen(true)}>
              Create First Question
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="px-4 py-3.5">Question & Version</th>
                  <th className="px-4 py-3.5">Type</th>
                  <th className="px-4 py-3.5">Difficulty</th>
                  <th className="px-4 py-3.5">Points</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">Updated</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {questions.map((q) => {
                  const targetVer = q.latest_version;
                  const vNum = targetVer?.version_number || 1;
                  const isDraft = targetVer?.status === 'DRAFT';
                  const isPublished = targetVer?.status === 'PUBLISHED';

                  return (
                    <tr key={q.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3.5 max-w-xs sm:max-w-sm">
                        <div className="font-sans font-bold text-slate-900 truncate text-sm">
                          {targetVer?.title || '(Untitled Question)'}
                        </div>
                        {/* Clear Question vs QuestionVersion Display */}
                        <div className="flex items-center gap-2 mt-1 font-mono text-[11px]">
                          <span className="font-bold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                            v{vNum}
                          </span>
                          <span className="text-slate-400">—</span>
                          <span className={isPublished ? 'text-emerald-700 font-bold' : 'text-amber-700 font-bold'}>
                            {targetVer?.status || 'DRAFT'}
                          </span>
                        </div>
                        {targetVer?.tags && targetVer.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {targetVer.tags.slice(0, 3).map((t) => (
                              <span key={t.id} className="text-[10px] text-slate-600 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded">
                                #{t.name}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        <Badge variant="info">{q.question_type}</Badge>
                      </td>
                      <td className="px-4 py-3.5">
                        {targetVer ? (
                          <Badge
                            variant={
                              targetVer.difficulty === 'EASY'
                                ? 'success'
                                : targetVer.difficulty === 'MEDIUM'
                                ? 'warning'
                                : 'danger'
                            }
                          >
                            {targetVer.difficulty}
                          </Badge>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="px-4 py-3.5 font-bold text-emerald-700">
                        {targetVer?.points ?? '—'} pts
                      </td>
                      <td className="px-4 py-3.5">
                        <Badge
                          variant={
                            q.status === 'ARCHIVED'
                              ? 'neutral'
                              : isPublished
                              ? 'success'
                              : isDraft
                              ? 'warning'
                              : 'neutral'
                          }
                        >
                          {q.status === 'ARCHIVED' ? 'ARCHIVED' : targetVer?.status || 'ACTIVE'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3.5 text-slate-500 text-[11px]">
                        {new Date(q.updated_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-1 whitespace-nowrap">
                        {/* View / Preview */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenPreview(q.id, vNum)}
                          title="Preview Question as Candidate"
                        >
                          <Eye className="w-3.5 h-3.5 text-blue-600" />
                        </Button>

                        {/* Edit: If draft, opens draft; if published, creates or opens draft vN */}
                        {isDraft ? (
                          <Link to={`/admin/questions/${q.id}/versions/${vNum}`}>
                            <Button variant="secondary" size="sm" title="Edit Draft Version">
                              <Edit className="w-3.5 h-3.5 mr-1" />
                              Edit
                            </Button>
                          </Link>
                        ) : (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleCreateNewVersion(q.id)}
                            title="Branch or Open Sequential Draft Version"
                          >
                            <GitBranch className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                            Edit
                          </Button>
                        )}

                        {/* Duplicate */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDuplicate(q)}
                          title="Duplicate Question as New Draft"
                        >
                          <Copy className="w-3.5 h-3.5 text-slate-600" />
                        </Button>

                        {/* Archive */}
                        {q.status !== 'ARCHIVED' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleArchive(q.id)}
                            title="Archive Question"
                          >
                            <Archive className="w-3.5 h-3.5 text-slate-500 hover:text-amber-600" />
                          </Button>
                        )}

                        {/* Delete */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenDeleteModal(q)}
                          title="Delete Question (Checks References)"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-slate-400 hover:text-rose-600" />
                        </Button>
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
              {Math.min(currentPage * pageSize, totalCount)} of {totalCount} questions
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

      {/* Modals */}
      <CreateQuestionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />

      <DeleteQuestionModal
        question={deleteTargetQuestion}
        isOpen={isDeleteModalOpen}
        onClose={() => {
          setIsDeleteModalOpen(false);
          setDeleteTargetQuestion(null);
        }}
        onSuccess={() => {
          fetchQuestions();
        }}
      />

      <QuestionPreviewModal
        questionId={previewQuestionId}
        versionNumber={previewVersionNumber}
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
      />

      <ImportQuestionsSpreadsheetModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={() => {
          fetchQuestions();
        }}
      />

      <ExtractQuestionImageModal
        isOpen={isExtractModalOpen}
        onClose={() => setIsExtractModalOpen(false)}
        onSuccess={() => {
          fetchQuestions();
        }}
      />
    </div>
  );
};

export default AdminQuestionsPage;
