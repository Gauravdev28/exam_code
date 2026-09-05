import React, { useState, useRef } from 'react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  Image as ImageIcon,
  UploadCloud,
  X,
  AlertTriangle,
  Check,
  Eye,
  FileCode,
  ShieldCheck,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Layers,
} from 'lucide-react';
import { extractQuestionFromImage, createQuestion } from '../../api/questions';
import { QuestionType, Difficulty } from '../../types/question';

interface ExtractQuestionImageModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ExtractQuestionImageModal: React.FC<ExtractQuestionImageModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [step, setStep] = useState<'UPLOAD' | 'REVIEW'>('UPLOAD');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Zoom controls for the left panel preview
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  // Extracted Question Review Form State
  const [imageId, setImageId] = useState<string>('');
  const [title, setTitle] = useState('');
  const [questionType, setQuestionType] = useState<QuestionType>('CODING');
  const [difficulty, setDifficulty] = useState<Difficulty>('MEDIUM');
  const [points, setPoints] = useState<number>(10);
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [constraints, setConstraints] = useState('');
  const [inputFormat, setInputFormat] = useState('');
  const [outputFormat, setOutputFormat] = useState('');
  const [starterCode, setStarterCode] = useState('');
  const [allowedLanguages, setAllowedLanguages] = useState<string[]>(['PYTHON', 'CPP', 'JAVA']);
  const [examples, setExamples] = useState<{ input: string; output: string; explanation?: string }[]>([]);
  const [testCases, setTestCases] = useState<any[]>([]);
  const [mcqOptions, setMcqOptions] = useState<string[]>(['', '', '', '']);
  const [correctOption, setCorrectOption] = useState<string>('A');
  const [confidenceScore, setConfidenceScore] = useState<number>(85);
  const [confidenceLevel, setConfidenceLevel] = useState<string>('HIGH');
  const [confidenceNotice, setConfidenceNotice] = useState<string>('');
  const [reviewWarnings, setReviewWarnings] = useState<string[]>([]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['png', 'jpg', 'jpeg', 'webp'].includes(ext || '')) {
      setErrorMessage('Please upload a valid PNG, JPG, or WEBP image.');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('Image file size exceeds the 10MB limit.');
      return;
    }

    setSelectedFile(file);
    setImagePreviewUrl(URL.createObjectURL(file));
    setErrorMessage(null);
  };

  const handleRunExtraction = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res = await extractQuestionFromImage(selectedFile);
      if (res.data) {
        const d = res.data;
        setImageId(d.image_id || '');
        setTitle(d.title || 'Extracted Question');
        setQuestionType((d.question_type as QuestionType) || 'CODING');
        setDifficulty((d.difficulty as Difficulty) || 'MEDIUM');
        setPoints(d.points || 10);
        setDescription(d.description || '');
        setInstructions(d.instructions || '');
        setConfidenceScore(d.confidence_score || 80);
        setConfidenceLevel(d.confidence_level || 'HIGH');
        setConfidenceNotice(
          d.confidence_notice ||
            'Review extracted content before saving. AI/OCR is an assistant and can make mistakes.'
        );
        setReviewWarnings(d.review_warnings || []);

        if (d.coding_config) {
          setConstraints(d.coding_config.constraints || '');
          setInputFormat(d.coding_config.input_format || '');
          setOutputFormat(d.coding_config.output_format || '');
          setStarterCode(d.coding_config.starter_code || '');
          if (d.coding_config.allowed_languages) {
            setAllowedLanguages(d.coding_config.allowed_languages);
          }
        }

        if (d.examples && Array.isArray(d.examples)) {
          setExamples(d.examples);
        }
        if (d.test_cases && Array.isArray(d.test_cases)) {
          setTestCases(d.test_cases);
        } else if (d.examples && Array.isArray(d.examples) && d.examples.length > 0) {
          setTestCases(
            d.examples.map((ex: any, idx: number) => ({
              input_data: ex.input || '',
              expected_output: ex.output || '',
              points: 5,
              is_hidden: false,
              execution_order: idx + 1,
            }))
          );
        }

        if (d.type_config?.options) {
          const opts = d.type_config.options.map((o: any) => o.text || '');
          setMcqOptions(opts.length >= 4 ? opts : [...opts, '', '', ''].slice(0, 4));
        }

        setStep('REVIEW');
        setZoomLevel(1);
      }
    } catch (err: any) {
      setErrorMessage(
        err.error?.message || err.message || 'Failed to extract question from image.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveAsDraft = async () => {
    if (!title.trim() || !description.trim()) {
      setErrorMessage('Title and Problem Description are required.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const payload: any = {
        question_type: questionType,
        title: title.trim(),
        description: description.trim(),
        instructions: instructions.trim(),
        points: Number(points) || 10,
        difficulty: difficulty,
        tags: ['Extracted from Image'],
        type_config: {
          _source: 'IMAGE_EXTRACTION',
          _source_image_id: imageId,
        },
      };

      if (questionType === 'CODING') {
        payload.coding_config = {
          problem_statement: description.trim(),
          allowed_languages: allowedLanguages,
          starter_code: starterCode.trim(),
          constraints: constraints.trim(),
          input_format: inputFormat.trim(),
          output_format: outputFormat.trim(),
          time_limit_ms: 2000,
          memory_limit_mb: 256,
        };

        // Prepare test cases
        if (testCases.length > 0) {
          payload.test_cases = testCases.map((tc, idx) => ({
            input_data: tc.input_data || tc.input || '',
            expected_output: tc.expected_output || tc.output || '',
            points: Number(tc.points) || Math.max(1, Math.floor(points / testCases.length)),
            is_hidden: Boolean(tc.is_hidden),
            execution_order: idx + 1,
          }));
        } else if (examples.length > 0) {
          payload.test_cases = examples.map((ex, idx) => ({
            input_data: ex.input,
            expected_output: ex.output,
            points: Math.max(1, Math.floor(points / examples.length)),
            is_hidden: false,
            execution_order: idx + 1,
          }));
        }
      } else if (questionType === 'MCQ' || questionType === 'MULTI_SELECT') {
        const optionKeys = ['A', 'B', 'C', 'D'];
        payload.type_config.options = mcqOptions
          .filter((opt) => opt.trim().length > 0)
          .map((opt, idx) => ({
            id: optionKeys[idx] || `OPT_${idx + 1}`,
            text: opt.trim(),
            is_correct: optionKeys[idx] === correctOption,
          }));
      }

      await createQuestion(payload);
      onSuccess();
      handleClose();
    } catch (err: any) {
      setErrorMessage(
        err.error?.message || err.message || 'Failed to save draft question.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setStep('UPLOAD');
    setSelectedFile(null);
    setImagePreviewUrl(null);
    setErrorMessage(null);
    setZoomLevel(1);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <Card
        className={`w-full flex flex-col p-6 space-y-4 bg-white border border-slate-200 shadow-2xl relative ${
          step === 'REVIEW' ? 'max-w-7xl h-[92vh]' : 'max-w-xl'
        }`}
      >
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-50 text-blue-700 border border-blue-200">
              <ImageIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">
                {step === 'UPLOAD' ? 'Extract Question from Screenshot' : 'Two-Panel OCR Review & Draft Authoring'}
              </h3>
              <p className="text-xs text-slate-600 font-medium">
                {step === 'UPLOAD'
                  ? 'Upload an image of a coding problem, MCQ, or exam prompt.'
                  : 'Compare original source image with parsed structure. Saved strictly as DRAFT.'}
              </p>
            </div>
          </div>
          {step === 'REVIEW' && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold px-2 py-1 rounded bg-amber-100 text-amber-900 border border-amber-200">
                Confidence: {confidenceLevel} ({confidenceScore}%)
              </span>
              <Badge variant="warning">DRAFT ONLY</Badge>
            </div>
          )}
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span className="font-semibold">{errorMessage}</span>
          </div>
        )}

        {/* STEP 1: UPLOAD */}
        {step === 'UPLOAD' && (
          <div className="space-y-4">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-300 hover:border-blue-500 bg-slate-50/70 hover:bg-blue-50/30 rounded-xl p-8 text-center cursor-pointer transition-colors space-y-3"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png, image/jpeg, image/webp"
                onChange={handleFileChange}
                className="hidden"
              />
              {imagePreviewUrl ? (
                <div className="space-y-2">
                  <img
                    src={imagePreviewUrl}
                    alt="Preview"
                    className="max-h-48 mx-auto rounded-lg border border-slate-200 shadow-sm object-contain"
                  />
                  <p className="text-xs font-semibold text-slate-700 font-mono">
                    {selectedFile?.name} ({(selectedFile?.size || 0) / 1024 < 1024
                      ? `${Math.round((selectedFile?.size || 0) / 1024)} KB`
                      : `${((selectedFile?.size || 0) / (1024 * 1024)).toFixed(1)} MB`})
                  </p>
                </div>
              ) : (
                <>
                  <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-700 mx-auto flex items-center justify-center">
                    <UploadCloud className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-slate-800">
                      Click to upload or drag question screenshot here
                    </p>
                    <p className="text-xs text-slate-600 font-medium">
                      PNG, JPG, or WEBP (up to 10MB)
                    </p>
                  </div>
                </>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
              <Button variant="secondary" size="sm" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleRunExtraction}
                isLoading={isLoading}
                disabled={!selectedFile}
              >
                Extract Question Content
              </Button>
            </div>
          </div>
        )}

        {/* STEP 2: TWO-PANEL HUMAN REVIEW */}
        {step === 'REVIEW' && (
          <div className="flex-1 flex flex-col space-y-3 overflow-hidden">
            {/* Warning Banner */}
            <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 flex flex-col gap-1.5 text-xs text-amber-900">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-amber-700 shrink-0" />
                  <span>{confidenceNotice}</span>
                </div>
                <span className="text-[11px] font-semibold text-slate-500 font-mono">
                  Pillow Preprocessing + Vision/Tesseract Engine
                </span>
              </div>
              {reviewWarnings.length > 0 && (
                <div className="pt-1.5 border-t border-amber-200/60 flex flex-wrap gap-2">
                  {reviewWarnings.map((warn, i) => (
                    <span key={i} className="inline-flex items-center gap-1 text-[11px] text-amber-800 font-medium">
                      <AlertTriangle className="w-3 h-3 text-amber-600" />
                      {warn}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Two Panels Layout */}
            <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 overflow-hidden min-h-0">
              {/* Left Panel: Original Image with Zoom / Pan Controls */}
              <div className="flex flex-col border border-slate-200 rounded-xl overflow-hidden bg-slate-900/5">
                <div className="p-2 bg-slate-100 border-b border-slate-200 flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-800 flex items-center gap-1.5">
                    <Eye className="w-3.5 h-3.5 text-slate-500" />
                    Original Screenshot
                  </span>

                  {/* Zoom Controls */}
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.25))}
                      className="p-1 rounded bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs"
                      title="Zoom Out"
                    >
                      <ZoomOut className="w-3.5 h-3.5" />
                    </button>
                    <span className="px-1.5 py-0.5 text-[11px] font-mono font-bold text-slate-700">
                      {Math.round(zoomLevel * 100)}%
                    </span>
                    <button
                      type="button"
                      onClick={() => setZoomLevel((z) => Math.min(3, z + 0.25))}
                      className="p-1 rounded bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs"
                      title="Zoom In"
                    >
                      <ZoomIn className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setZoomLevel(1)}
                      className="p-1 rounded bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs ml-1"
                      title="Reset Zoom"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="flex-1 p-4 overflow-auto flex items-center justify-center bg-slate-950/10">
                  {imagePreviewUrl && (
                    <div
                      style={{
                        transform: `scale(${zoomLevel})`,
                        transformOrigin: 'top center',
                        transition: 'transform 0.15s ease-out',
                      }}
                      className="max-w-full"
                    >
                      <img
                        src={imagePreviewUrl}
                        alt="Source Screenshot"
                        className="max-w-full max-h-[70vh] object-contain rounded border border-slate-300 shadow-md"
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Right Panel: Structured Editable Fields */}
              <div className="flex flex-col border border-slate-200 rounded-xl overflow-hidden bg-white">
                <div className="p-2 bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-800 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <FileCode className="w-3.5 h-3.5 text-blue-600" />
                    Extracted Question Fields (Editable)
                  </span>
                  <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    Will Save as DRAFT
                  </span>
                </div>

                <div className="flex-1 p-4 overflow-y-auto space-y-3.5 text-xs">
                  {/* Title */}
                  <div className="space-y-1">
                    <label className="block text-slate-800 font-bold">Title *</label>
                    <input
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-semibold focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  {/* Metadata Row */}
                  <div className="grid grid-cols-3 gap-2.5">
                    <div>
                      <label className="block text-slate-800 font-bold">Type</label>
                      <select
                        value={questionType}
                        onChange={(e) => setQuestionType(e.target.value as QuestionType)}
                        className="w-full px-2 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-semibold"
                      >
                        <option value="CODING">Coding</option>
                        <option value="MCQ">MCQ (Single Choice)</option>
                        <option value="MULTI_SELECT">Multi-Select</option>
                        <option value="TRUE_FALSE">True / False</option>
                        <option value="SHORT_ANSWER">Short Answer</option>
                        <option value="SQL">SQL Query</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-800 font-bold">Difficulty</label>
                      <select
                        value={difficulty}
                        onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                        className="w-full px-2 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-semibold"
                      >
                        <option value="EASY">Easy</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="HARD">Hard</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-800 font-bold">Points</label>
                      <input
                        type="number"
                        min="1"
                        value={points}
                        onChange={(e) => setPoints(Number(e.target.value))}
                        className="w-full px-2 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-mono font-bold"
                      />
                    </div>
                  </div>

                  {/* Problem Description */}
                  <div className="space-y-1">
                    <label className="block text-slate-800 font-bold">Problem Statement *</label>
                    <textarea
                      rows={5}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-blue-500 font-sans"
                    />
                  </div>

                  {/* Coding Specific Fields */}
                  {questionType === 'CODING' && (
                    <>
                      <div className="space-y-1">
                        <label className="block text-slate-800 font-bold">Constraints</label>
                        <textarea
                          rows={2}
                          value={constraints}
                          onChange={(e) => setConstraints(e.target.value)}
                          placeholder="e.g. 1 <= N <= 10^5"
                          className="w-full px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-mono"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <label className="block text-slate-800 font-bold">Input Format</label>
                          <input
                            type="text"
                            value={inputFormat}
                            onChange={(e) => setInputFormat(e.target.value)}
                            placeholder="Input description..."
                            className="w-full px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-xs"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="block text-slate-800 font-bold">Output Format</label>
                          <input
                            type="text"
                            value={outputFormat}
                            onChange={(e) => setOutputFormat(e.target.value)}
                            placeholder="Output description..."
                            className="w-full px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-xs"
                          />
                        </div>
                      </div>

                      <div className="space-y-1">
                        <label className="block text-slate-800 font-bold">Starter Code</label>
                        <textarea
                          rows={3}
                          value={starterCode}
                          onChange={(e) => setStarterCode(e.target.value)}
                          placeholder="def solve(): pass"
                          className="w-full px-3 py-1.5 rounded-lg bg-slate-900 text-emerald-400 text-xs font-mono"
                        />
                      </div>

                      {/* Test cases extracted from examples */}
                      {testCases.length > 0 && (
                        <div className="space-y-2 p-3 rounded-lg bg-slate-50 border border-slate-200">
                          <span className="font-bold text-slate-800 flex items-center gap-1">
                            <Layers className="w-3.5 h-3.5 text-emerald-600" />
                            Extracted Sample Test Cases ({testCases.length})
                          </span>
                          <div className="space-y-2 max-h-36 overflow-y-auto">
                            {testCases.map((tc, idx) => (
                              <div key={idx} className="p-2 rounded bg-white border border-slate-200 text-[11px] font-mono">
                                <span className="font-bold text-slate-700">Case {idx + 1}: </span>
                                <span>Input: <code>{tc.input_data || tc.input}</code> | Output: <code>{tc.expected_output || tc.output}</code></span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {/* MCQ Options */}
                  {(questionType === 'MCQ' || questionType === 'MULTI_SELECT') && (
                    <div className="space-y-2">
                      <label className="block text-slate-800 font-bold">MCQ Options</label>
                      {['A', 'B', 'C', 'D'].map((optKey, idx) => (
                        <div key={optKey} className="flex items-center gap-2">
                          <span className="w-6 font-mono font-bold text-slate-700">{optKey}:</span>
                          <input
                            type="text"
                            value={mcqOptions[idx] || ''}
                            onChange={(e) => {
                              const next = [...mcqOptions];
                              next[idx] = e.target.value;
                              setMcqOptions(next);
                            }}
                            className="flex-1 px-2.5 py-1 rounded bg-white border border-slate-300 text-slate-900 text-xs"
                          />
                          <input
                            type="radio"
                            name="correctOpt"
                            checked={correctOption === optKey}
                            onChange={() => setCorrectOption(optKey)}
                            title="Mark as correct option"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-200">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setStep('UPLOAD')}
                className="text-slate-700"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
                Upload Different Image
              </Button>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSaveAsDraft}
                  isLoading={isLoading}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
                >
                  <Check className="w-3.5 h-3.5 mr-1" />
                  Save as Draft Question
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
