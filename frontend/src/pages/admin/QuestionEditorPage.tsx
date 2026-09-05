import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  createQuestion,
  getQuestionVersionDetail,
  updateDraftVersion,
  publishVersion,
} from '../../api/questions';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { QuestionPreviewModal } from '../../components/admin/QuestionPreviewModal';
import { CodingQuestionEditor } from '../../components/admin/CodingQuestionEditor';
import {
  ArrowLeft,
  Save,
  CheckCircle2,
  Eye,
  AlertCircle,
  Plus,
  Trash2,
  Lock,
  Database,
  ListFilter,
  CheckSquare,
  Binary,
  AlignLeft,
} from 'lucide-react';
import {
  QuestionType,
  Difficulty,
  TestCase,
  CodingLanguage,
} from '../../types/question';

export const QuestionEditorPage: React.FC = () => {
  const { id: routeQuestionId, version: routeVersionStr } = useParams<{ id?: string; version?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const typeParam = searchParams.get('type') as QuestionType | null;

  const isEditing = Boolean(routeQuestionId && routeVersionStr);
  const routeVersionNum = routeVersionStr ? parseInt(routeVersionStr, 10) : 1;

  const [questionType, setQuestionType] = useState<QuestionType>('MCQ');
  const [versionStatus, setVersionStatus] = useState<'DRAFT' | 'PUBLISHED' | 'ARCHIVED'>('DRAFT');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [points, setPoints] = useState<number>(10);
  const [negativeMarkingEnabled, setNegativeMarkingEnabled] = useState(false);
  const [negativePoints, setNegativePoints] = useState<number>(0);
  const [difficulty, setDifficulty] = useState<Difficulty>('MEDIUM');
  const [tagsInput, setTagsInput] = useState('');

  // MCQ / Multi-Select Options
  const [options, setOptions] = useState<{ id: string; text: string }[]>([
    { id: 'A', text: '' },
    { id: 'B', text: '' },
    { id: 'C', text: '' },
    { id: 'D', text: '' },
  ]);
  const [correctOptions, setCorrectOptions] = useState<string[]>(['A']);

  // True / False
  const [tfCorrect, setTfCorrect] = useState<boolean>(true);

  // Short Answer
  const [acceptedAnswersInput, setAcceptedAnswersInput] = useState('');
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [trimWhitespace, setTrimWhitespace] = useState(true);
  const [normalizeSpaces, setNormalizeSpaces] = useState(true);

  // Coding Config
  const [codingProblemStatement, setCodingProblemStatement] = useState('');
  const [codingConstraints, setCodingConstraints] = useState('');
  const [allowedLanguages, setAllowedLanguages] = useState<CodingLanguage[]>(['PYTHON', 'CPP', 'JAVA']);
  const [timeLimitMs, setTimeLimitMs] = useState<number>(2000);
  const [memoryLimitMb, setMemoryLimitMb] = useState<number>(256);
  const [testCases, setTestCases] = useState<TestCase[]>([
    { input_data: '', expected_output: '', points: 5, is_hidden: false, execution_order: 1 },
    { input_data: '', expected_output: '', points: 5, is_hidden: true, execution_order: 2 },
  ]);

  // SQL Config
  const [sqlProblemStatement, setSqlProblemStatement] = useState('');
  const [schemaSetupSql, setSchemaSetupSql] = useState('');
  const [expectedResultDef, setExpectedResultDef] = useState('');
  const [allowedDialect, setAllowedDialect] = useState('MYSQL');
  const [sqlTimeLimitMs, setSqlTimeLimitMs] = useState<number>(3000);

  // UI state
  const [rawVersionDetail, setRawVersionDetail] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Preview Modal
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  useEffect(() => {
    if (!isEditing && typeParam) {
      setQuestionType(typeParam);
    }
  }, [isEditing, typeParam]);

  useEffect(() => {
    if (isEditing && routeQuestionId && routeVersionNum) {
      loadVersionData(routeQuestionId, routeVersionNum);
    }
  }, [isEditing, routeQuestionId, routeVersionNum]);

  const loadVersionData = async (qId: string, vNum: number) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await getQuestionVersionDetail(qId, vNum);
      if (res.data) {
        const v = res.data;
        setRawVersionDetail(v);
        setQuestionType(v.question_type);
        setVersionStatus(v.status);
        setTitle(v.title);
        setDescription(v.description);
        setInstructions(v.instructions || '');
        setPoints(v.points);
        setNegativeMarkingEnabled(v.negative_marking_enabled);
        setNegativePoints(v.negative_points);
        setDifficulty(v.difficulty);
        setTagsInput((v.tags || []).map((t) => t.name).join(', '));

        if (v.question_type === 'MCQ' || v.question_type === 'MULTI_SELECT') {
          if (v.type_config?.options) setOptions(v.type_config.options);
          if (v.type_config?.correct_options) setCorrectOptions(v.type_config.correct_options);
        } else if (v.question_type === 'TRUE_FALSE') {
          if (typeof v.type_config?.correct_answer === 'boolean') {
            setTfCorrect(v.type_config.correct_answer);
          }
        } else if (v.question_type === 'SHORT_ANSWER') {
          if (v.type_config?.accepted_answers) {
            setAcceptedAnswersInput(v.type_config.accepted_answers.join(', '));
          }
          if (typeof v.type_config?.case_sensitive === 'boolean') setCaseSensitive(v.type_config.case_sensitive);
          if (typeof v.type_config?.trim_whitespace === 'boolean') setTrimWhitespace(v.type_config.trim_whitespace);
          if (typeof v.type_config?.normalize_spaces === 'boolean') setNormalizeSpaces(v.type_config.normalize_spaces);
        } else if (v.question_type === 'CODING' && v.coding_config) {
          setCodingProblemStatement(v.coding_config.problem_statement || '');
          setCodingConstraints(v.coding_config.constraints || '');
          setAllowedLanguages(v.coding_config.allowed_languages || ['PYTHON', 'CPP', 'JAVA']);
          setTimeLimitMs(v.coding_config.time_limit_ms || 2000);
          setMemoryLimitMb(v.coding_config.memory_limit_mb || 256);
          if (v.coding_config.test_cases) setTestCases(v.coding_config.test_cases);
        } else if (v.question_type === 'SQL' && v.sql_config) {
          setSqlProblemStatement(v.sql_config.problem_statement || '');
          setSchemaSetupSql(v.sql_config.schema_setup_sql || '');
          setExpectedResultDef(v.sql_config.expected_result_definition || '');
          setAllowedDialect(v.sql_config.allowed_dialect || 'MYSQL');
          setSqlTimeLimitMs(v.sql_config.time_limit_ms || 3000);
        }
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load question version.');
    } finally {
      setIsLoading(false);
    }
  };

  // Compile Type Config
  const buildTypeConfig = () => {
    if (questionType === 'MCQ' || questionType === 'MULTI_SELECT') {
      return {
        options: options.map((opt) => ({ id: opt.id.trim(), text: opt.text.trim() })),
        correct_options: correctOptions,
      };
    }
    if (questionType === 'TRUE_FALSE') {
      return { correct_answer: tfCorrect };
    }
    if (questionType === 'SHORT_ANSWER') {
      return {
        accepted_answers: acceptedAnswersInput
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        case_sensitive: caseSensitive,
        trim_whitespace: trimWhitespace,
        normalize_spaces: normalizeSpaces,
      };
    }
    return {};
  };

  const parseTags = () =>
    tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

  const handleSaveDraft = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const typeConfigData = buildTypeConfig();
    const tagsList = parseTags();

    try {
      if (!isEditing) {
        // Create new Question + v1
        const payload: any = {
          question_type: questionType,
          title: title.trim(),
          description: description.trim(),
          instructions: instructions.trim(),
          points,
          negative_marking_enabled: negativeMarkingEnabled,
          negative_points: negativePoints,
          difficulty,
          tags: tagsList,
          type_config: typeConfigData,
        };

        if (questionType === 'CODING') {
          payload.coding_config = {
            problem_statement: codingProblemStatement || description,
            constraints: codingConstraints,
            allowed_languages: allowedLanguages,
            time_limit_ms: timeLimitMs,
            memory_limit_mb: memoryLimitMb,
          };
          payload.test_cases = testCases;
        } else if (questionType === 'SQL') {
          payload.sql_config = {
            problem_statement: sqlProblemStatement || description,
            schema_setup_sql: schemaSetupSql,
            expected_result_definition: expectedResultDef,
            allowed_dialect: allowedDialect,
            time_limit_ms: sqlTimeLimitMs,
          };
        }

        const res = await createQuestion(payload);
        if (res.data) {
          navigate(`/admin/questions/${res.data.question_id}/versions/${res.data.version_number}`);
        }
      } else {
        // Update existing Draft
        const payload: any = {
          title: title.trim(),
          description: description.trim(),
          instructions: instructions.trim(),
          points,
          negative_marking_enabled: negativeMarkingEnabled,
          negative_points: negativePoints,
          difficulty,
          tags: tagsList,
          type_config: typeConfigData,
        };

        if (questionType === 'CODING') {
          payload.coding_config = {
            problem_statement: codingProblemStatement || description,
            constraints: codingConstraints,
            allowed_languages: allowedLanguages,
            time_limit_ms: timeLimitMs,
            memory_limit_mb: memoryLimitMb,
          };
          payload.test_cases = testCases;
        } else if (questionType === 'SQL') {
          payload.sql_config = {
            problem_statement: sqlProblemStatement || description,
            schema_setup_sql: schemaSetupSql,
            expected_result_definition: expectedResultDef,
            allowed_dialect: allowedDialect,
            time_limit_ms: sqlTimeLimitMs,
          };
        }

        await updateDraftVersion(routeQuestionId!, routeVersionNum, payload);
        setSuccessMessage('Draft changes saved successfully.');
      }
    } catch (err: any) {
      setErrorMessage(
        err.error?.message ||
          (err.error?.details ? JSON.stringify(err.error.details) : null) ||
          err.message ||
          'Failed to save draft.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!isEditing || !routeQuestionId) {
      alert('Please save the draft before publishing.');
      return;
    }

    if (!window.confirm('Are you sure you want to publish this version? Once published, this version will become permanently IMMUTABLE.')) {
      return;
    }

    setIsPublishing(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      // Save latest draft state first
      await handleSaveDraft();
      // Execute Publish
      const res = await publishVersion(routeQuestionId, routeVersionNum);
      if (res.data) {
        setVersionStatus('PUBLISHED');
        setSuccessMessage('Question published successfully! Version is now locked and ready for assessments.');
      }
    } catch (err: any) {
      setErrorMessage(
        err.error?.message ||
          (err.error?.details ? JSON.stringify(err.error.details) : null) ||
          err.message ||
          'Failed to publish question version.'
      );
    } finally {
      setIsPublishing(false);
    }
  };

  const handleCodingSaveDraft = async (payload: any) => {
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      if (!isEditing) {
        const res = await createQuestion(payload);
        if (res.data) {
          navigate(`/admin/questions/${res.data.question_id}/versions/${res.data.version_number}`);
        }
      } else {
        await updateDraftVersion(routeQuestionId!, routeVersionNum, payload);
        await loadVersionData(routeQuestionId!, routeVersionNum);
        setSuccessMessage('Coding question draft saved successfully.');
      }
    } catch (err: any) {
      setErrorMessage(
        err.error?.message ||
          (err.error?.details ? JSON.stringify(err.error.details) : null) ||
          err.message ||
          'Failed to save coding question draft.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleCodingPublish = async (payload: any) => {
    setIsPublishing(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      let qId = routeQuestionId;
      let vNum = routeVersionNum;
      if (!isEditing) {
        const res = await createQuestion(payload);
        if (res.data) {
          qId = res.data.question_id;
          vNum = res.data.version_number;
        }
      } else {
        await updateDraftVersion(qId!, vNum, payload);
      }
      if (qId && vNum) {
        const pubRes = await publishVersion(qId, vNum);
        if (pubRes.data) {
          setVersionStatus('PUBLISHED');
          setSuccessMessage('Coding question published successfully! Immutability locked.');
          await loadVersionData(qId, vNum);
        }
      }
    } catch (err: any) {
      setErrorMessage(
        err.error?.message ||
          (err.error?.details ? JSON.stringify(err.error.details) : null) ||
          err.message ||
          'Failed to publish coding question.'
      );
    } finally {
      setIsPublishing(false);
    }
  };

  // Option handlers for MCQ/Multi
  const handleAddOption = () => {
    const nextId = String.fromCharCode(65 + options.length);
    setOptions([...options, { id: nextId, text: '' }]);
  };

  const handleRemoveOption = (idx: number) => {
    if (options.length <= 2) {
      alert('A minimum of 2 options is required.');
      return;
    }
    const removedId = options[idx].id;
    const updated = options.filter((_, i) => i !== idx);
    setOptions(updated);
    setCorrectOptions(correctOptions.filter((id) => id !== removedId));
  };

  const isLocked = versionStatus === 'PUBLISHED' || versionStatus === 'ARCHIVED';

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-16 flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400 font-mono">Loading question configuration...</p>
      </div>
    );
  }

  return (
    <div className={`container mx-auto px-4 py-8 space-y-6 ${questionType === 'CODING' ? 'max-w-7xl' : 'max-w-5xl'}`}>
      {/* Top Navigation for Non-Coding Question Types */}
      {questionType !== 'CODING' && (
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <Link
            to="/admin/questions"
            className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            Back to Question Bank
          </Link>

          <div className="flex items-center gap-2">
            {isEditing && (
              <Badge
                variant={
                  versionStatus === 'PUBLISHED'
                    ? 'success'
                    : versionStatus === 'ARCHIVED'
                    ? 'neutral'
                    : 'warning'
                }
              >
                {versionStatus} v{routeVersionNum}
              </Badge>
            )}
            {isLocked && (
              <span className="flex items-center gap-1 text-xs text-amber-700 font-medium">
                <Lock className="w-3.5 h-3.5" /> Locked (Immutable)
              </span>
            )}
          </div>
        </div>
      )}

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

      {/* Single-Page Coding Question Workspace */}
      {questionType === 'CODING' ? (
        <CodingQuestionEditor
          initialData={
            rawVersionDetail || {
              question: routeQuestionId,
              title,
              difficulty,
              points,
              negative_marking_enabled: negativeMarkingEnabled,
              negative_points: negativePoints,
              tags: tagsInput ? tagsInput.split(',').map((s) => s.trim()).filter(Boolean) : [],
              description,
              instructions,
              coding_config: {
                problem_statement: codingProblemStatement || description,
                constraints: codingConstraints,
                allowed_languages: allowedLanguages,
                starter_code: '',
                time_limit_ms: timeLimitMs,
                memory_limit_mb: memoryLimitMb,
                test_cases: testCases,
              },
            }
          }
          isLocked={isLocked}
          versionNumber={routeVersionNum}
          questionId={routeQuestionId}
          onSaveDraft={handleCodingSaveDraft}
          onPublish={handleCodingPublish}
          isSaving={isSaving}
          isPublishing={isPublishing}
        />
      ) : (
        /* Main Form for other Question Types (MCQ, MULTI_SELECT, TRUE_FALSE, SHORT_ANSWER, SQL) */
        <div className="space-y-6">
        {/* Section 1: Question Type & Core Metadata */}
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-200 pb-4">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <ListFilter className="w-5 h-5 text-emerald-600" />
              Question Architecture & Type Anchor
            </h2>
            {isEditing && (
              <span className="text-xs text-slate-500 font-medium">
                Question Type is permanent for this logical question.
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Question Type */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Question Type</label>
              <select
                disabled={isEditing || isLocked}
                value={questionType}
                onChange={(e) => setQuestionType(e.target.value as QuestionType)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-medium disabled:opacity-60 focus:ring-2 focus:ring-emerald-500"
              >
                <option value="MCQ">MCQ (Single Select)</option>
                <option value="MULTI_SELECT">Multi-Select</option>
                <option value="TRUE_FALSE">True / False</option>
                <option value="SHORT_ANSWER">Short Answer</option>
                <option value="CODING">Coding Problem</option>
                <option value="SQL">SQL Query</option>
              </select>
            </div>

            {/* Difficulty */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Difficulty</label>
              <select
                disabled={isLocked}
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-medium disabled:opacity-60 focus:ring-2 focus:ring-emerald-500"
              >
                <option value="EASY">Easy</option>
                <option value="MEDIUM">Medium</option>
                <option value="HARD">Hard</option>
              </select>
            </div>

            {/* Total Points */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Total Points</label>
              <input
                type="number"
                min={1}
                disabled={isLocked}
                value={points}
                onChange={(e) => setPoints(Math.max(1, parseInt(e.target.value, 10) || 1))}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-emerald-700 font-bold text-xs disabled:opacity-60 focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          {/* Negative Marking */}
          <div className="flex flex-wrap items-center gap-6 p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
              <input
                type="checkbox"
                disabled={isLocked}
                checked={negativeMarkingEnabled}
                onChange={(e) => setNegativeMarkingEnabled(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
              />
              <span>Enable Negative Marking Penalty</span>
            </label>

            {negativeMarkingEnabled && (
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-semibold">Penalty Points:</span>
                <input
                  type="number"
                  min={0}
                  max={points}
                  disabled={isLocked}
                  value={negativePoints}
                  onChange={(e) => setNegativePoints(Math.max(0, parseInt(e.target.value, 10) || 0))}
                  className="w-20 px-2 py-1 rounded bg-white border border-slate-300 text-rose-600 font-bold focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            )}
          </div>

          {/* Title */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Question Title</label>
            <input
              type="text"
              disabled={isLocked}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Reverse a Linked List / Python List Comprehension"
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          {/* Tags */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Tags (Comma-separated)</label>
            <input
              type="text"
              disabled={isLocked}
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="Python, Algorithms, Arrays, Recursion"
              className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {/* Description / Statement */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Problem Statement / Prompt (Markdown)</label>
            <textarea
              rows={5}
              disabled={isLocked}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the question context, problem statement, or background prompt..."
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {/* Instructions */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Student Instructions (Optional)</label>
            <input
              type="text"
              disabled={isLocked}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. Select the single best answer. No partial credit."
              className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </Card>

        {/* Section 2: Type-Specific Configuration */}
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-200 pb-4">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              {questionType === 'SQL' ? (
                <Database className="w-5 h-5 text-cyan-600" />
              ) : questionType === 'TRUE_FALSE' ? (
                <Binary className="w-5 h-5 text-emerald-600" />
              ) : questionType === 'SHORT_ANSWER' ? (
                <AlignLeft className="w-5 h-5 text-amber-600" />
              ) : (
                <CheckSquare className="w-5 h-5 text-purple-600" />
              )}
              {questionType} Configuration
            </h2>
          </div>

          {/* MCQ / Multi-Select */}
          {(questionType === 'MCQ' || questionType === 'MULTI_SELECT') && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-600 font-semibold">
                <span>Configure Options & Select Correct Choice(s)</span>
                {!isLocked && (
                  <Button type="button" variant="secondary" size="sm" onClick={handleAddOption}>
                    <Plus className="w-3.5 h-3.5 mr-1" /> Add Option
                  </Button>
                )}
              </div>

              <div className="space-y-3">
                {options.map((opt, idx) => {
                  const isChecked = correctOptions.includes(opt.id);
                  return (
                    <div
                      key={idx}
                      className={`flex items-center gap-3 p-3 rounded-xl border transition-colors ${
                        isChecked ? 'bg-emerald-50/60 border-emerald-300' : 'bg-white border-slate-200'
                      }`}
                    >
                      {questionType === 'MCQ' ? (
                        <input
                          type="radio"
                          name="mcq_correct_option"
                          disabled={isLocked}
                          checked={isChecked}
                          onChange={() => setCorrectOptions([opt.id])}
                          className="text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                        />
                      ) : (
                        <input
                          type="checkbox"
                          disabled={isLocked}
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setCorrectOptions([...correctOptions, opt.id]);
                            } else {
                              setCorrectOptions(correctOptions.filter((id) => id !== opt.id));
                            }
                          }}
                          className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                        />
                      )}

                      <span className="font-mono font-bold text-emerald-700 w-6">{opt.id}.</span>

                      <input
                        type="text"
                        disabled={isLocked}
                        value={opt.text}
                        onChange={(e) => {
                          const updated = [...options];
                          updated[idx].text = e.target.value;
                          setOptions(updated);
                        }}
                        placeholder={`Option ${opt.id} text...`}
                        className="flex-1 px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                      />

                      {!isLocked && options.length > 2 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveOption(idx)}
                          className="text-slate-400 hover:text-rose-600 p-1"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* True / False */}
          {questionType === 'TRUE_FALSE' && (
            <div className="space-y-3 text-xs">
              <label className="block text-slate-700 font-semibold">Select Correct Answer</label>
              <div className="flex gap-4">
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => setTfCorrect(true)}
                  className={`px-6 py-3 rounded-xl border font-bold text-sm transition-all ${
                    tfCorrect === true
                      ? 'bg-emerald-50 border-emerald-400 text-emerald-700 shadow-sm'
                      : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  TRUE
                </button>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => setTfCorrect(false)}
                  className={`px-6 py-3 rounded-xl border font-bold text-sm transition-all ${
                    tfCorrect === false
                      ? 'bg-rose-50 border-rose-400 text-rose-700 shadow-sm'
                      : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  FALSE
                </button>
              </div>
            </div>
          )}

          {/* Short Answer */}
          {questionType === 'SHORT_ANSWER' && (
            <div className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="block text-slate-700 font-semibold">Accepted Answer Tokens (Comma-separated)</label>
                <input
                  type="text"
                  disabled={isLocked}
                  value={acceptedAnswersInput}
                  onChange={(e) => setAcceptedAnswersInput(e.target.value)}
                  placeholder="80, port 80, 80/tcp"
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500 font-mono"
                />
              </div>

              <div className="flex flex-wrap gap-6 p-3 rounded-xl bg-slate-50 border border-slate-200">
                <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
                  <input
                    type="checkbox"
                    disabled={isLocked}
                    checked={caseSensitive}
                    onChange={(e) => setCaseSensitive(e.target.checked)}
                    className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                  />
                  <span>Case Sensitive Matching</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
                  <input
                    type="checkbox"
                    disabled={isLocked}
                    checked={trimWhitespace}
                    onChange={(e) => setTrimWhitespace(e.target.checked)}
                    className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                  />
                  <span>Trim Leading/Trailing Whitespace</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium">
                  <input
                    type="checkbox"
                    disabled={isLocked}
                    checked={normalizeSpaces}
                    onChange={(e) => setNormalizeSpaces(e.target.checked)}
                    className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                  />
                  <span>Normalize Internal Spaces</span>
                </label>
              </div>
            </div>
          )}



          {/* SQL Sandbox Config */}
          {questionType === 'SQL' && (
            <div className="space-y-4 text-xs font-mono">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block text-slate-700 font-semibold">SQL Dialect</label>
                  <input
                    type="text"
                    disabled
                    value={allowedDialect}
                    className="w-full px-3 py-2 rounded-lg bg-slate-100 border border-slate-300 text-slate-600 font-medium"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-slate-700 font-semibold">Execution Timeout (ms)</label>
                  <input
                    type="number"
                    disabled={isLocked}
                    value={sqlTimeLimitMs}
                    onChange={(e) => setSqlTimeLimitMs(parseInt(e.target.value, 10) || 3000)}
                    className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-slate-700 font-semibold">Schema Setup DDL / Seed Data SQL</label>
                <textarea
                  rows={4}
                  disabled={isLocked}
                  value={schemaSetupSql}
                  onChange={(e) => setSchemaSetupSql(e.target.value)}
                  placeholder="CREATE TABLE employees (id INT, name VARCHAR(50), salary INT); INSERT INTO employees VALUES (1, 'Alice', 90000);"
                  className="w-full p-3 rounded-lg bg-slate-900 border border-slate-800 text-cyan-300 focus:ring-2 focus:ring-emerald-500 font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-slate-700 font-semibold">Expected Result Definition Query</label>
                <textarea
                  rows={3}
                  disabled={isLocked}
                  value={expectedResultDef}
                  onChange={(e) => setExpectedResultDef(e.target.value)}
                  placeholder="SELECT name, salary FROM employees WHERE salary > 80000 ORDER BY salary DESC;"
                  className="w-full p-3 rounded-lg bg-slate-900 border border-slate-800 text-cyan-300 focus:ring-2 focus:ring-emerald-500 font-mono"
                />
              </div>
            </div>
          )}
        </Card>

        {/* Action Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-200">
          <Button variant="ghost" size="md" onClick={() => navigate('/admin/questions')}>
            Cancel
          </Button>

          <div className="flex items-center gap-3">
            {isEditing && (
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={() => setIsPreviewOpen(true)}
              >
                <Eye className="w-4 h-4 mr-2" />
                Preview
              </Button>
            )}

            {!isLocked && (
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={handleSaveDraft}
                isLoading={isSaving}
              >
                <Save className="w-4 h-4 mr-2" />
                Save Draft
              </Button>
            )}

            {!isLocked && isEditing && (
              <Button
                type="button"
                variant="primary"
                size="md"
                onClick={handlePublish}
                isLoading={isPublishing}
              >
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Publish Version
              </Button>
            )}
          </div>
        </div>
      </div>
      )}

      {/* Preview Modal */}
      <QuestionPreviewModal
        questionId={routeQuestionId || null}
        versionNumber={routeVersionNum}
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
      />
    </div>
  );
};

export default QuestionEditorPage;
