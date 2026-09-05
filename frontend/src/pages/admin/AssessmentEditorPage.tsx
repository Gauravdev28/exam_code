import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  createAssessment,
  getAssessmentDetail,
  updateAssessment,
  publishAssessment,
  addQuestionToAssessment,
  removeQuestionFromAssessment,
} from '../../api/assessments';
import { getQuestions } from '../../api/questions';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  ArrowLeft,
  Save,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  Lock,
  Calendar,
  Clock,
  Shuffle,
  FileText,
  Search,
  X,
} from 'lucide-react';
import {
  AssessmentAdminDetail,
  ResultVisibility,
} from '../../types/assessment';
import { QuestionItem } from '../../types/question';
import { AssessmentAudiencePanel } from '../../components/admin/AssessmentAudiencePanel';

export const AssessmentEditorPage: React.FC = () => {
  const { id: routeAssessmentId } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(routeAssessmentId);

  const [assessment, setAssessment] = useState<AssessmentAdminDetail | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [startDatetime, setStartDatetime] = useState('');
  const [endDatetime, setEndDatetime] = useState('');
  const [durationMinutes, setDurationMinutes] = useState<number>(60);
  const [totalPoints, setTotalPoints] = useState<number>(0);
  const [negativeMarkingEnabled, setNegativeMarkingEnabled] = useState(false);
  const [attemptLimit, setAttemptLimit] = useState<number>(1);
  const [randomizeQuestions, setRandomizeQuestions] = useState(false);
  const [randomizeOptions, setRandomizeOptions] = useState(false);
  const [resultVisibility, setResultVisibility] = useState<ResultVisibility>('AFTER_DEADLINE');
  const [audienceTotalEligible, setAudienceTotalEligible] = useState<number>(0);

  // Question Picker state
  const [isQuestionPickerOpen, setIsQuestionPickerOpen] = useState(false);
  const [availableQuestions, setAvailableQuestions] = useState<QuestionItem[]>([]);
  const [questionSearch, setQuestionSearch] = useState('');
  const [selectedQvId, setSelectedQvId] = useState<string | null>(null);
  const [qPointsInput, setQPointsInput] = useState<number>(10);
  const [qNegEnabledInput, setQNegEnabledInput] = useState(false);
  const [qNegPointsInput, setQNegPointsInput] = useState<number>(0);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const formatForDateTimeLocal = (d: Date): string => {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  useEffect(() => {
    if (isEditing && routeAssessmentId) {
      loadAssessment(routeAssessmentId);
    } else {
      // Default future dates in local time
      const now = new Date();
      const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
      setStartDatetime(formatForDateTimeLocal(now));
      setEndDatetime(formatForDateTimeLocal(nextWeek));
    }
  }, [isEditing, routeAssessmentId]);

  const loadAssessment = async (aId: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await getAssessmentDetail(aId);
      if (res.data) {
        const d = res.data;
        setAssessment(d);
        setTitle(d.title);
        setDescription(d.description);
        setInstructions(d.instructions || '');
        setStartDatetime(formatForDateTimeLocal(new Date(d.start_datetime)));
        setEndDatetime(formatForDateTimeLocal(new Date(d.end_datetime)));
        setDurationMinutes(d.duration_minutes);
        setTotalPoints(d.total_points);
        setNegativeMarkingEnabled(d.negative_marking_enabled);
        setAttemptLimit(d.attempt_limit);
        setRandomizeQuestions(d.randomize_questions);
        setRandomizeOptions(d.randomize_options);
        setResultVisibility(d.result_visibility);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load assessment.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);

    const trimmedTitle = title.trim();
    const trimmedDesc = description.trim();

    if (!trimmedTitle) {
      setErrorMessage('Assessment title cannot be empty.');
      return;
    }

    const startDate = new Date(startDatetime);
    const endDate = new Date(endDatetime);

    if (isNaN(startDate.getTime())) {
      setErrorMessage('Please provide a valid start datetime.');
      return;
    }
    if (isNaN(endDate.getTime())) {
      setErrorMessage('Please provide a valid end / deadline datetime.');
      return;
    }
    if (endDate <= startDate) {
      setErrorMessage('End / Deadline datetime must be strictly after start datetime.');
      return;
    }
    if (durationMinutes < 1) {
      setErrorMessage('Duration must be at least 1 minute.');
      return;
    }

    setIsSaving(true);

    const payload = {
      title: trimmedTitle,
      description: trimmedDesc,
      instructions: instructions.trim(),
      start_datetime: startDate.toISOString(),
      end_datetime: endDate.toISOString(),
      duration_minutes: durationMinutes,
      total_points: totalPoints,
      negative_marking_enabled: negativeMarkingEnabled,
      attempt_limit: attemptLimit,
      randomize_questions: randomizeQuestions,
      randomize_options: randomizeOptions,
      result_visibility: resultVisibility,
    };

    try {
      if (!isEditing) {
        const res = await createAssessment(payload);
        if (res.data) {
          navigate(`/admin/assessments/${res.data.id}`);
        }
      } else {
        const res = await updateAssessment(routeAssessmentId!, payload);
        if (res.data) {
          setAssessment(res.data);
          setSuccessMessage('Assessment details updated successfully.');
        }
      }
    } catch (err: any) {
      const details = err.error?.details;
      let detailedMsg = err.error?.message;
      if (details && typeof details === 'object') {
        const fieldMsgs = Object.entries(details).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        if (fieldMsgs.length > 0) detailedMsg = fieldMsgs.join(' | ');
      }
      setErrorMessage(detailedMsg || err.message || 'Failed to save assessment.');
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!isEditing || !routeAssessmentId) return;
    if (!window.confirm('Are you sure you want to publish this assessment? Once published, the assessment and its question snapshot will become permanently IMMUTABLE.')) {
      return;
    }

    setIsPublishing(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await publishAssessment(routeAssessmentId);
      if (res.data) {
        setAssessment(res.data);
        setSuccessMessage('Assessment published successfully! Snapshot is now frozen.');
      }
    } catch (err: any) {
      const details = err.error?.details;
      let detailedMsg = err.error?.message;
      if (details && typeof details === 'object') {
        const fieldMsgs = Object.entries(details).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        if (fieldMsgs.length > 0) detailedMsg = fieldMsgs.join(' | ');
      }
      setErrorMessage(detailedMsg || err.message || 'Failed to publish assessment.');
    } finally {
      setIsPublishing(false);
    }
  };

  const openQuestionPicker = async () => {
    setIsQuestionPickerOpen(true);
    try {
      const res = await getQuestions({ version_status: 'PUBLISHED', page_size: 50 });
      if (res.data) {
        setAvailableQuestions(res.data.results);
      }
    } catch (err: any) {
      console.error(err);
    }
  };

  const handleAddQuestionToAssessment = async () => {
    if (!routeAssessmentId || !selectedQvId) return;
    try {
      const res = await addQuestionToAssessment(routeAssessmentId, {
        question_version_id: selectedQvId,
        points: qPointsInput,
        negative_marking_enabled: qNegEnabledInput,
        negative_points: qNegPointsInput,
      });
      if (res.data) {
        setAssessment(res.data);
        setIsQuestionPickerOpen(false);
        setSelectedQvId(null);
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to add question to assessment.');
    }
  };

  const handleRemoveQuestion = async (qvId: string) => {
    if (!routeAssessmentId) return;
    try {
      const res = await removeQuestionFromAssessment(routeAssessmentId, qvId);
      if (res.data) {
        setAssessment(res.data);
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to remove question.');
    }
  };

  const isLocked = assessment?.status === 'PUBLISHED' || assessment?.status === 'ARCHIVED';
  const linkedQuestions = assessment?.assessment_questions || [];
  const questionPointsSum = linkedQuestions.reduce((sum, q) => sum + q.points, 0);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-16 flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400 font-mono">Loading assessment configuration...</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-5xl">
      {/* Top Navigation */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <Link
          to="/admin/assessments"
          className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to Assessments
        </Link>

        <div className="flex items-center gap-2">
          {assessment && (
            <Badge
              variant={
                assessment.status === 'PUBLISHED'
                  ? 'success'
                  : assessment.status === 'ARCHIVED'
                  ? 'neutral'
                  : 'warning'
              }
            >
              {assessment.status}
            </Badge>
          )}
          {isLocked && (
            <span className="flex items-center gap-1 text-xs text-amber-700 font-medium">
              <Lock className="w-3.5 h-3.5" /> Locked (Immutable)
            </span>
          )}
        </div>
      </div>

      {/* Notifications */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-3 text-emerald-800 text-sm">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Section 1: Assessment Metadata & Scheduling */}
      <Card className="p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-600" />
            Assessment Configuration & Scheduling
          </h2>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Assessment Title</label>
            <input
              type="text"
              disabled={isLocked}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. CS201 Final Examination / Data Engineering Assessment"
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Description</label>
            <textarea
              rows={3}
              disabled={isLocked}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Summary of assessment objectives..."
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Student Instructions</label>
            <input
              type="text"
              disabled={isLocked}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. Ensure stable internet. Monaco editor supports Python, C++, and Java."
              className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          {/* Scheduling & Timing Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs pt-2">
            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-emerald-600" />
                Start Datetime (UTC)
              </label>
              <input
                type="datetime-local"
                disabled={isLocked}
                value={startDatetime}
                onChange={(e) => setStartDatetime(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-rose-600" />
                End / Deadline (UTC)
              </label>
              <input
                type="datetime-local"
                disabled={isLocked}
                value={endDatetime}
                onChange={(e) => setEndDatetime(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-amber-600" />
                Duration (Minutes)
              </label>
              <input
                type="number"
                min={1}
                disabled={isLocked}
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(parseInt(e.target.value, 10) || 60)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
              />
            </div>
          </div>

          {/* Points & Attempts */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs pt-2">
            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold">Total Points (Must equal Question sum)</label>
              <input
                type="number"
                min={0}
                disabled={isLocked}
                value={totalPoints}
                onChange={(e) => setTotalPoints(parseInt(e.target.value, 10) || 0)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-emerald-700 font-bold font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold">Attempt Limit</label>
              <input
                type="number"
                min={1}
                disabled={isLocked}
                value={attemptLimit}
                onChange={(e) => setAttemptLimit(parseInt(e.target.value, 10) || 1)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-slate-700 font-semibold">Result Visibility</label>
              <select
                disabled={isLocked}
                value={resultVisibility}
                onChange={(e) => setResultVisibility(e.target.value as ResultVisibility)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-medium focus:ring-2 focus:ring-emerald-500"
              >
                <option value="AFTER_DEADLINE">After Deadline</option>
                <option value="IMMEDIATE">Immediate</option>
                <option value="MANUAL">Manual Release</option>
              </select>
            </div>
          </div>

          {/* Randomization & Negative Marking Toggles */}
          <div className="flex flex-wrap items-center gap-6 p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                disabled={isLocked}
                checked={negativeMarkingEnabled}
                onChange={(e) => setNegativeMarkingEnabled(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
              />
              <span>Enable Negative Marking Global Policy</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                disabled={isLocked}
                checked={randomizeQuestions}
                onChange={(e) => setRandomizeQuestions(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
              />
              <span className="flex items-center gap-1">
                <Shuffle className="w-3.5 h-3.5 text-emerald-600" />
                Randomize Question Order
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                disabled={isLocked}
                checked={randomizeOptions}
                onChange={(e) => setRandomizeOptions(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
              />
              <span className="flex items-center gap-1">
                <Shuffle className="w-3.5 h-3.5 text-purple-600" />
                Randomize Options Order
              </span>
            </label>
          </div>
        </div>
      </Card>

      {/* Target Audience & Section Classification */}
      {isEditing && (
        <AssessmentAudiencePanel
          assessmentId={routeAssessmentId || null}
          isLocked={isLocked}
          onValidationChange={(_isValid, count) => setAudienceTotalEligible(count)}
        />
      )}

      {/* Section 2: Assessment Questions List & Point Invariant Check */}
      {isEditing && (
        <Card className="p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                Assessment Questions ({linkedQuestions.length})
              </h2>
              <p className="text-xs text-slate-500">
                Bound to immutable published QuestionVersions
              </p>
            </div>

            {/* Invariant Meter */}
            <div className="flex items-center gap-3 font-mono text-xs">
              <span
                className={`px-3 py-1.5 rounded-lg border font-bold ${
                  questionPointsSum === totalPoints && totalPoints > 0
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                    : 'bg-amber-50 border-amber-200 text-amber-800'
                }`}
              >
                Questions Total: {questionPointsSum} / {totalPoints} pts{' '}
                {totalPoints !== questionPointsSum && `(${totalPoints - questionPointsSum} diff)`}
              </span>

              {!isLocked && (
                <Button type="button" variant="secondary" size="sm" onClick={openQuestionPicker}>
                  <Plus className="w-3.5 h-3.5 mr-1" /> Add Question
                </Button>
              )}
            </div>
          </div>

          {linkedQuestions.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 font-mono">
              No questions linked to this assessment yet. Click "Add Question" to select from published questions.
            </div>
          ) : (
            <div className="space-y-3">
              {linkedQuestions.map((q, idx) => (
                <div
                  key={q.id}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-slate-500 font-mono w-6">#{idx + 1}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-sans font-bold text-slate-900">{q.question_title}</span>
                        <Badge variant="info" size="sm">{q.question_type}</Badge>
                        <Badge variant="neutral" size="sm">v{q.version_number}</Badge>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1 font-mono">
                        <span>Points: <strong className="text-emerald-700">{q.points}</strong></span>
                        {q.negative_marking_enabled && (
                          <span className="text-rose-600">Penalty: -{q.negative_points}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {!isLocked && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveQuestion(q.question_version_id)}
                      className="text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Action Bar */}
      <div className="flex items-center justify-between pt-4 border-t border-slate-200">
        <Button variant="ghost" size="md" onClick={() => navigate('/admin/assessments')}>
          Cancel
        </Button>

        <div className="flex items-center gap-3">
          {!isLocked && (
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={handleSave}
              isLoading={isSaving}
            >
              <Save className="w-4 h-4 mr-2" />
              Save Draft
            </Button>
          )}

          {!isLocked && isEditing && (
            <div className="flex items-center gap-2">
              {audienceTotalEligible === 0 && (
                <span className="text-xs text-amber-700 font-semibold bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-lg">
                  ⚠️ Audience Required
                </span>
              )}
              <Button
                type="button"
                variant="primary"
                size="md"
                onClick={handlePublish}
                isLoading={isPublishing}
                disabled={
                  linkedQuestions.length === 0 ||
                  questionPointsSum !== totalPoints ||
                  audienceTotalEligible === 0
                }
              >
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Publish Assessment
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Question Picker Modal */}
      {isQuestionPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto">
          <Card className="max-w-3xl w-full p-6 space-y-6 border-slate-200 shadow-2xl relative my-8 bg-white">
            <button
              onClick={() => setIsQuestionPickerOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 font-bold"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
              <h3 className="text-base font-bold text-slate-900">Select Published Question</h3>
            </div>

            <div className="space-y-4">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search published questions..."
                  value={questionSearch}
                  onChange={(e) => setQuestionSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-xl divide-y divide-slate-100 text-xs font-mono">
                {availableQuestions
                  .filter((q) => {
                    const title = q.latest_version?.title || '';
                    return title.toLowerCase().includes(questionSearch.toLowerCase());
                  })
                  .map((q) => {
                    const v = q.published_version || q.latest_version;
                    if (!v) return null;
                    const isSelected = selectedQvId === v.id;

                    return (
                      <div
                        key={q.id}
                        onClick={() => {
                          setSelectedQvId(v.id);
                          setQPointsInput(v.points);
                        }}
                        className={`flex items-center justify-between p-3 cursor-pointer transition-colors ${
                          isSelected ? 'bg-emerald-50 border-l-4 border-emerald-600' : 'hover:bg-slate-50'
                        }`}
                      >
                        <div>
                          <div className="font-sans font-bold text-slate-900">{v.title}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="info" size="sm">{q.question_type}</Badge>
                            <span className="text-slate-500">{v.points} pts</span>
                            <Badge variant="neutral" size="sm">v{v.version_number}</Badge>
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>

              {selectedQvId && (
                <div className="grid grid-cols-3 gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs">
                  <div className="space-y-1">
                    <label className="text-slate-700 font-semibold">Points</label>
                    <input
                      type="number"
                      min={1}
                      value={qPointsInput}
                      onChange={(e) => setQPointsInput(parseInt(e.target.value, 10) || 1)}
                      className="w-full p-1.5 rounded bg-white border border-slate-300 text-emerald-700 font-bold"
                    />
                  </div>
                  <div className="space-y-1 col-span-2 flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer text-slate-700 pt-3 font-sans font-semibold">
                      <input
                        type="checkbox"
                        checked={qNegEnabledInput}
                        onChange={(e) => setQNegEnabledInput(e.target.checked)}
                        className="rounded text-emerald-600"
                      />
                      <span>Negative Marking</span>
                    </label>
                    {qNegEnabledInput && (
                      <div className="flex items-center gap-1 pt-2">
                        <span className="text-slate-500">Penalty:</span>
                        <input
                          type="number"
                          min={0}
                          value={qNegPointsInput}
                          onChange={(e) => setQNegPointsInput(parseInt(e.target.value, 10) || 0)}
                          className="w-16 p-1 rounded bg-white border border-slate-300 text-rose-600 font-bold"
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
              <Button variant="ghost" size="sm" onClick={() => setIsQuestionPickerOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={!selectedQvId}
                onClick={handleAddQuestionToAssessment}
              >
                Add to Assessment
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default AssessmentEditorPage;
