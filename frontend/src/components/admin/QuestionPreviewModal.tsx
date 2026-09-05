import React, { useState, useEffect } from 'react';
import { getQuestionVersionPreview } from '../../api/questions';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  X,
  Eye,
  AlertCircle,
  Clock,
  HardDrive,
  CheckCircle2,
  Database,
  Code2,
  ListOrdered,
  HelpCircle,
} from 'lucide-react';
import { QuestionVersionDetail } from '../../types/question';

interface QuestionPreviewModalProps {
  questionId: string | null;
  versionNumber: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export const QuestionPreviewModal: React.FC<QuestionPreviewModalProps> = ({
  questionId,
  versionNumber,
  isOpen,
  onClose,
}) => {
  const [data, setData] = useState<QuestionVersionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Student interaction mockup state
  const [selectedOption, setSelectedOption] = useState<string>('');
  const [selectedMulti, setSelectedMulti] = useState<string[]>([]);
  const [tfAnswer, setTfAnswer] = useState<boolean | null>(null);
  const [shortText, setShortText] = useState<string>('');

  useEffect(() => {
    if (isOpen && questionId && versionNumber) {
      loadPreview(questionId, versionNumber);
    } else {
      setData(null);
      setSelectedOption('');
      setSelectedMulti([]);
      setTfAnswer(null);
      setShortText('');
      setErrorMessage(null);
    }
  }, [isOpen, questionId, versionNumber]);

  const loadPreview = async (qId: string, vNum: number) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await getQuestionVersionPreview(qId, vNum);
      if (res.data) {
        setData(res.data);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load question preview.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm overflow-y-auto">
      <Card className="max-w-3xl w-full p-6 space-y-6 bg-white border border-slate-200 shadow-2xl relative my-8">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
              <Eye className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900">Student Assessment Preview</h3>
                {data && (
                  <Badge variant="neutral">v{data.version_number}</Badge>
                )}
              </div>
              <p className="text-xs text-slate-500">Previewing exact student view and rendering interface</p>
            </div>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-500 font-mono">Loading preview configuration...</p>
          </div>
        ) : data ? (
          <div className="space-y-6">
            {/* Question Meta Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <div className="flex items-center gap-2">
                <Badge variant="info">{data.question_type}</Badge>
                <Badge
                  variant={
                    data.difficulty === 'EASY'
                      ? 'success'
                      : data.difficulty === 'MEDIUM'
                      ? 'warning'
                      : 'danger'
                  }
                >
                  {data.difficulty}
                </Badge>
              </div>
              <div className="flex items-center gap-4 text-slate-700 font-semibold font-mono">
                <span>Points: <span className="text-emerald-700 font-bold">{data.points}</span></span>
                {data.negative_marking_enabled && (
                  <span className="text-rose-600">Penalty: -{data.negative_points}</span>
                )}
              </div>
            </div>

            {/* Title & Description */}
            <div className="space-y-3">
              <h2 className="text-lg font-bold text-slate-900">{data.title}</h2>
              <div className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap font-sans bg-slate-50 p-4 rounded-xl border border-slate-200">
                {data.description}
              </div>
              {data.instructions && (
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2">
                  <HelpCircle className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                  <span><strong>Instructions:</strong> {data.instructions}</span>
                </div>
              )}
            </div>

            {/* Type-Specific Student Interaction Area */}
            <div className="pt-2">
              {data.question_type === 'MCQ' && (
                <div className="space-y-2.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-600 font-mono">
                    Select One Option
                  </label>
                  <div className="space-y-2">
                    {(data.type_config?.options || []).map((opt: any) => (
                      <label
                        key={opt.id}
                        className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                          selectedOption === opt.id
                            ? 'bg-emerald-50/70 border-emerald-400 text-slate-900 shadow-sm'
                            : 'bg-white border-slate-200 text-slate-800 hover:bg-slate-50'
                        }`}
                      >
                        <input
                          type="radio"
                          name="mcq_preview"
                          checked={selectedOption === opt.id}
                          onChange={() => setSelectedOption(opt.id)}
                          className="text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                        />
                        <span className="font-mono font-bold text-emerald-700 w-5">{opt.id}.</span>
                        <span className="text-sm font-medium">{opt.text}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {data.question_type === 'MULTI_SELECT' && (
                <div className="space-y-2.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-600 font-mono">
                    Select All That Apply
                  </label>
                  <div className="space-y-2">
                    {(data.type_config?.options || []).map((opt: any) => {
                      const isChecked = selectedMulti.includes(opt.id);
                      return (
                        <label
                          key={opt.id}
                          className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                            isChecked
                              ? 'bg-emerald-50/70 border-emerald-400 text-slate-900 shadow-sm'
                              : 'bg-white border-slate-200 text-slate-800 hover:bg-slate-50'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedMulti([...selectedMulti, opt.id]);
                              } else {
                                setSelectedMulti(selectedMulti.filter((id) => id !== opt.id));
                              }
                            }}
                            className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4 bg-white border-slate-300"
                          />
                          <span className="font-mono font-bold text-emerald-700 w-5">{opt.id}.</span>
                          <span className="text-sm font-medium">{opt.text}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              {data.question_type === 'TRUE_FALSE' && (
                <div className="space-y-2.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-600 font-mono">
                    Select Answer
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setTfAnswer(true)}
                      className={`p-4 rounded-xl border font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                        tfAnswer === true
                          ? 'bg-emerald-50 border-emerald-400 text-emerald-700 shadow-sm'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      TRUE
                    </button>
                    <button
                      type="button"
                      onClick={() => setTfAnswer(false)}
                      className={`p-4 rounded-xl border font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                        tfAnswer === false
                          ? 'bg-rose-50 border-rose-400 text-rose-700 shadow-sm'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      <X className="w-4 h-4" />
                      FALSE
                    </button>
                  </div>
                </div>
              )}

              {data.question_type === 'SHORT_ANSWER' && (
                <div className="space-y-2.5">
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-600 font-mono">
                    Your Answer
                  </label>
                  <input
                    type="text"
                    value={shortText}
                    onChange={(e) => setShortText(e.target.value)}
                    placeholder="Type your answer here..."
                    className="w-full px-4 py-3 rounded-xl bg-white border border-slate-300 text-slate-900 font-mono text-sm focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              )}

              {data.question_type === 'CODING' && data.coding_config && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-700 p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="flex items-center gap-1.5">
                      <Code2 className="w-4 h-4 text-emerald-600" />
                      <span>Languages: <strong className="text-slate-900">{data.coding_config.allowed_languages.join(', ')}</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-amber-600" />
                      <span>Time: <strong className="text-slate-900">{data.coding_config.time_limit_ms} ms</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <HardDrive className="w-4 h-4 text-sky-600" />
                      <span>Memory: <strong className="text-slate-900">{data.coding_config.memory_limit_mb} MB</strong></span>
                    </div>
                  </div>

                  {data.coding_config.constraints && (
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                      <h4 className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wider mb-1">Constraints</h4>
                      <p className="text-xs text-slate-800 font-mono whitespace-pre-wrap">{data.coding_config.constraints}</p>
                    </div>
                  )}

                  {/* Public Example Test Cases */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-mono font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                      <ListOrdered className="w-4 h-4 text-emerald-600" />
                      Example Test Cases (Visible to Students)
                    </h4>
                    {data.coding_config.test_cases && data.coding_config.test_cases.length > 0 ? (
                      <div className="space-y-2.5">
                        {data.coding_config.test_cases.map((tc, idx) => (
                          <div key={idx} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono space-y-2">
                            <div className="flex justify-between text-slate-600 border-b border-slate-200 pb-1.5">
                              <span className="font-bold text-slate-800">Example Case #{idx + 1}</span>
                              <span className="text-emerald-700 font-bold">{tc.points} pts</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2.5">
                              <div>
                                <span className="text-slate-500 block font-semibold mb-1">Input:</span>
                                <pre className="p-2.5 rounded-lg bg-slate-900 text-slate-100 overflow-x-auto">{tc.input_data || '(empty)'}</pre>
                              </div>
                              <div>
                                <span className="text-slate-500 block font-semibold mb-1">Expected Output:</span>
                                <pre className="p-2.5 rounded-lg bg-slate-900 text-slate-100 overflow-x-auto">{tc.expected_output}</pre>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 italic">No public example test cases configured.</p>
                    )}
                  </div>
                </div>
              )}

              {data.question_type === 'SQL' && data.sql_config && (
                <div className="space-y-4">
                  <div className="flex items-center gap-4 text-xs font-mono text-slate-700 p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="flex items-center gap-1.5">
                      <Database className="w-4 h-4 text-cyan-600" />
                      <span>Dialect: <strong className="text-slate-900">{data.sql_config.allowed_dialect}</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-amber-600" />
                      <span>Limit: <strong className="text-slate-900">{data.sql_config.time_limit_ms} ms</strong></span>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <h4 className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wider mb-2">Sandbox Tables / Schema Setup</h4>
                    <pre className="p-3 rounded-lg bg-slate-900 text-cyan-300 font-mono text-xs overflow-x-auto border border-slate-800">
                      {data.sql_config.schema_setup_sql}
                    </pre>
                  </div>
                </div>
              )}
            </div>

            {/* Tags */}
            {data.tags && data.tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-3 border-t border-slate-200">
                <span className="text-xs text-slate-500 font-medium mr-1">Tags:</span>
                {data.tags.map((t) => (
                  <Badge key={t.id} variant="neutral">#{t.name}</Badge>
                ))}
              </div>
            )}
          </div>
        ) : null}

        <div className="pt-3 flex justify-end border-t border-slate-200">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close Preview
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default QuestionPreviewModal;
