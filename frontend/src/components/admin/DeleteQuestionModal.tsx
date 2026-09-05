import React, { useEffect, useState } from 'react';
import { getQuestionUsage, archiveQuestion, deleteDraftQuestion, QuestionUsageInfo } from '../../api/questions';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { AlertTriangle, Trash2, Archive, X, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { QuestionItem } from '../../types/question';

interface DeleteQuestionModalProps {
  question: QuestionItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (action: 'deleted' | 'archived') => void;
}

export const DeleteQuestionModal: React.FC<DeleteQuestionModalProps> = ({
  question,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [usage, setUsage] = useState<QuestionUsageInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !question) {
      setUsage(null);
      setErrorMessage(null);
      return;
    }

    const loadUsage = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const res = await getQuestionUsage(question.id);
        if (res.data) {
          setUsage(res.data);
        }
      } catch (err: any) {
        setErrorMessage(err.error?.message || err.message || 'Failed to check question dependencies.');
      } finally {
        setIsLoading(false);
      }
    };

    loadUsage();
  }, [isOpen, question]);

  if (!isOpen || !question) return null;

  const targetVer = question.latest_version;
  const isDeletable = usage?.is_deletable ?? false;

  const handleDeletePermanent = async () => {
    setIsProcessing(true);
    setErrorMessage(null);
    try {
      await deleteDraftQuestion(question.id);
      onSuccess('deleted');
      onClose();
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to delete draft question.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleArchiveInstead = async () => {
    setIsProcessing(true);
    setErrorMessage(null);
    try {
      await archiveQuestion(question.id);
      onSuccess('archived');
      onClose();
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to archive question.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden text-slate-900">
        {/* Header */}
        <div className={`px-6 py-4 flex items-center justify-between text-white ${
          isDeletable ? 'bg-rose-600' : 'bg-slate-900'
        }`}>
          <div className="flex items-center gap-2.5">
            {isDeletable ? (
              <Trash2 className="h-5 w-5" />
            ) : (
              <ShieldAlert className="h-5 w-5 text-amber-400" />
            )}
            <h3 id="delete-modal-title" className="text-base font-bold">
              {isDeletable ? 'Delete Draft Question' : 'Question Deletion Protected'}
            </h3>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="text-white/80 hover:text-white p-1 rounded-lg hover:bg-white/10 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Question Summary */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Question Details
              </span>
              <div className="flex items-center gap-1.5">
                <Badge variant="info">{question.question_type}</Badge>
                <span className="text-xs px-2 py-0.5 rounded bg-white border border-slate-200 font-bold font-mono">
                  v{targetVer?.version_number || 1}
                </span>
                <Badge variant={targetVer?.status === 'PUBLISHED' ? 'success' : 'warning'}>
                  {targetVer?.status || 'DRAFT'}
                </Badge>
              </div>
            </div>
            <p className="text-sm font-bold text-slate-900 line-clamp-2">
              {targetVer?.title || '(Untitled Question)'}
            </p>
          </div>

          {errorMessage && (
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {isLoading ? (
            <div className="py-6 flex flex-col items-center justify-center space-y-2 text-slate-500 text-xs font-mono">
              <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
              <span>Inspecting historical dependencies...</span>
            </div>
          ) : usage && (
            <div className="space-y-4">
              {/* Dependency Breakdown */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Assessments:</span>
                  <strong className={usage.assessments_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.assessments_count}
                  </strong>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Snapshots:</span>
                  <strong className={usage.snapshots_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.snapshots_count}
                  </strong>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Candidate Answers:</span>
                  <strong className={usage.answers_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.answers_count}
                  </strong>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-100/70 border border-slate-200 flex justify-between items-center">
                  <span className="text-slate-600">Legal Holds:</span>
                  <strong className={usage.legal_holds_count > 0 ? 'text-rose-600' : 'text-slate-700'}>
                    {usage.legal_holds_count}
                  </strong>
                </div>
              </div>

              {/* Status Explanation */}
              {isDeletable ? (
                <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-start gap-2.5">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-bold">Safe to Delete</p>
                    <p className="text-slate-600">
                      This question is an unreferenced DRAFT. Deleting it will permanently remove it from the question bank.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-2">
                  <div className="flex items-center gap-2 font-bold text-amber-800">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                    <span>Hard Deletion Blocked</span>
                  </div>
                  <p className="text-slate-700 leading-relaxed">
                    This question has historical references or has been published. Hard deleting would corrupt assessment history and examination audits.
                  </p>
                  {usage.reasons && usage.reasons.length > 0 && (
                    <ul className="list-disc list-inside space-y-0.5 text-slate-600 pl-1">
                      {usage.reasons.map((r, idx) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  )}
                  <p className="text-slate-700 font-semibold pt-1">
                    You may <strong>Archive</strong> this question instead to hide it from new assessments while preserving historical integrity.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <Button
              variant="secondary"
              size="md"
              onClick={onClose}
              disabled={isProcessing}
            >
              Cancel
            </Button>

            {isDeletable ? (
              <Button
                variant="danger"
                size="md"
                onClick={handleDeletePermanent}
                disabled={isProcessing || isLoading}
                className="bg-rose-600 hover:bg-rose-700 text-white"
              >
                <Trash2 className="w-4 h-4 mr-1.5" />
                {isProcessing ? 'Deleting...' : 'Delete Permanently'}
              </Button>
            ) : (
              <Button
                variant="primary"
                size="md"
                onClick={handleArchiveInstead}
                disabled={isProcessing || isLoading || question.status === 'ARCHIVED'}
                className="bg-slate-900 hover:bg-slate-800 text-white"
              >
                <Archive className="w-4 h-4 mr-1.5 text-amber-400" />
                {isProcessing ? 'Archiving...' : 'Archive Question Instead'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
