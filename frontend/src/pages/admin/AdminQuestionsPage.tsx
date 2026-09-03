import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getQuestions, archiveQuestion, createNewVersion } from '../../api/questions';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { QuestionPreviewModal } from '../../components/admin/QuestionPreviewModal';
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

  // Preview Modal State
  const [previewQuestionId, setPreviewQuestionId] = useState<string | null>(null);
  const [previewVersionNumber, setPreviewVersionNumber] = useState<number | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

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

  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-7xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-900 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
              <HelpCircle className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Question Bank</h1>
              <p className="text-sm text-slate-400">
                Manage, version, and configure academic assessment questions across 6 core types
              </p>
            </div>
          </div>
        </div>

        <Link to="/admin/questions/create">
          <Button variant="primary" size="md">
            <Plus className="w-4 h-4 mr-2" />
            Create Question
          </Button>
        </Link>
      </div>

      {/* Tabs & Filters Bar */}
      <Card className="p-4 space-y-4 border-slate-800/80 bg-slate-950/60">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-900 pb-4">
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
                placeholder="Search title, prompt, tags..."
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

        {/* Dropdown Filters */}
        <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-slate-500">Filter By:</span>
          </div>

          <select
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 focus:ring-1 focus:ring-brand-500"
          >
            <option value="">All Question Types</option>
            <option value="MCQ">MCQ</option>
            <option value="MULTI_SELECT">Multi-Select</option>
            <option value="TRUE_FALSE">True / False</option>
            <option value="SHORT_ANSWER">Short Answer</option>
            <option value="CODING">Coding Problem</option>
            <option value="SQL">SQL Query</option>
          </select>

          <select
            value={selectedDifficulty}
            onChange={(e) => {
              setSelectedDifficulty(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 focus:ring-1 focus:ring-brand-500"
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
              className="text-brand-400 hover:underline text-xs"
            >
              Reset Filters
            </button>
          )}
        </div>
      </Card>

      {/* Error Notice */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-3 text-red-300 text-sm">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Questions Roster Table */}
      <Card className="overflow-hidden border-slate-800/80">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400 font-mono">Querying question catalog...</p>
          </div>
        ) : questions.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <p className="text-slate-400 text-sm">No questions found matching the selected criteria.</p>
            <Link to="/admin/questions/create">
              <Button variant="secondary" size="sm">
                Create First Question
              </Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Question Title & Prompt</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Difficulty</th>
                  <th className="px-4 py-3">Points</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {questions.map((q) => {
                  const targetVer = q.latest_version;
                  const vNum = targetVer?.version_number || 1;
                  const isDraft = targetVer?.status === 'DRAFT';
                  const isPublished = targetVer?.status === 'PUBLISHED';

                  return (
                    <tr key={q.id} className="hover:bg-slate-900/40 transition-colors">
                      <td className="px-4 py-3.5 max-w-xs sm:max-w-sm">
                        <div className="font-sans font-bold text-slate-100 truncate text-sm">
                          {targetVer?.title || '(Untitled Question)'}
                        </div>
                        {targetVer?.tags && targetVer.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {targetVer.tags.slice(0, 3).map((t) => (
                              <span key={t.id} className="text-[10px] text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded">
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
                      <td className="px-4 py-3.5 font-bold text-brand-400">
                        {targetVer?.points ?? '—'} pts
                      </td>
                      <td className="px-4 py-3.5 text-slate-300">
                        <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 font-bold">
                          v{vNum}
                        </span>
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
                      <td className="px-4 py-3.5 text-slate-400 text-[11px]">
                        {new Date(q.updated_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-1 whitespace-nowrap">
                        {/* Preview */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenPreview(q.id, vNum)}
                          title="Preview Question"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </Button>

                        {/* Edit Draft or View Published */}
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
                            title="Create New Version from this Published Question"
                          >
                            <GitBranch className="w-3.5 h-3.5 mr-1" />
                            New Ver
                          </Button>
                        )}

                        {/* Archive */}
                        {q.status !== 'ARCHIVED' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleArchive(q.id)}
                            title="Archive Question"
                          >
                            <Archive className="w-3.5 h-3.5 text-slate-500 hover:text-red-400" />
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

      {/* Preview Modal */}
      <QuestionPreviewModal
        questionId={previewQuestionId}
        versionNumber={previewVersionNumber}
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
      />
    </div>
  );
};

export default AdminQuestionsPage;
