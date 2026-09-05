import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  Sparkles,
  Upload,
  AlertCircle,
  CheckCircle2,
  Shield,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  getPlatformImportStatus,
  previewPlatformImport,
  confirmPlatformImport,
} from '../../api/questions';
import { PlatformImportStatus, PlatformImportPreview } from '../../types/question';

interface ImportPlatformModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

type PlatformTab = 'HACKERRANK' | 'LEETCODE' | 'ZIP' | 'JSON';

export const ImportPlatformModal: React.FC<ImportPlatformModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const navigate = useNavigate();

  const [activePlatform, setActivePlatform] = useState<PlatformTab>('HACKERRANK');
  const [platformStatuses, setPlatformStatuses] = useState<PlatformImportStatus | null>(null);

  // Inputs
  const [hrSlug, setHrSlug] = useState('');
  const [hrRawJson, setHrRawJson] = useState('');
  const [lcTitle, setLcTitle] = useState('');
  const [lcDifficulty, setLcDifficulty] = useState<'EASY' | 'MEDIUM' | 'HARD'>('MEDIUM');
  const [lcProblemStatement, setLcProblemStatement] = useState('');
  const [lcConstraints, setLcConstraints] = useState('');
  const [lcInputFormat, setLcInputFormat] = useState('');
  const [lcOutputFormat, setLcOutputFormat] = useState('');
  const [lcSampleInput, setLcSampleInput] = useState('');
  const [lcSampleOutput, setLcSampleOutput] = useState('');
  const [lcJsonContent, setLcJsonContent] = useState('');
  const [lcInputMode, setLcInputMode] = useState<'FORM' | 'JSON'>('FORM');

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState('');

  // Preview & Submission State
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [previewData, setPreviewData] = useState<PlatformImportPreview | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadStatuses();
      setPreviewData(null);
      setErrorMessage(null);
    }
  }, [isOpen]);

  const loadStatuses = async () => {
    try {
      const res = await getPlatformImportStatus();
      if (res.data) {
        setPlatformStatuses(res.data);
      }
    } catch {
      // Fallback
      setPlatformStatuses({
        hackerrank: { configured: false, auth_mode: 'UNCONFIGURED', message: 'HackerRank integration not configured.' },
        leetcode: { configured: false, auth_mode: 'MANUAL_IMPORT_REQUIRED', message: 'LeetCode terms prohibit automated scraping. Import via manual content.' },
        zip_package: { supported: true, auth_mode: 'DIRECT_UPLOAD', message: 'Upload standard question ZIP' },
        manual_json: { supported: true, auth_mode: 'PASTE_JSON', message: 'Paste structured problem definition' },
      });
    }
  };

  if (!isOpen) return null;

  const handleGeneratePreview = async () => {
    setErrorMessage(null);
    setIsPreviewing(true);

    try {
      if (activePlatform === 'HACKERRANK') {
        const isConfigured = platformStatuses?.hackerrank?.configured;
        if (!isConfigured && !hrRawJson.trim()) {
          setErrorMessage('HackerRank integration is unconfigured. Please paste structured export JSON or configure credentials.');
          setIsPreviewing(false);
          return;
        }

        let payloadData: any = {};
        if (hrRawJson.trim()) {
          try {
            payloadData = JSON.parse(hrRawJson);
          } catch {
            setErrorMessage('Invalid JSON format in HackerRank export.');
            setIsPreviewing(false);
            return;
          }
        } else {
          payloadData = { slug: hrSlug.trim() };
        }

        const res = await previewPlatformImport('HACKERRANK', payloadData);
        if (res.data) {
          setPreviewData(res.data);
        }
      } else if (activePlatform === 'LEETCODE') {
        let payload: any = {};
        if (lcInputMode === 'JSON') {
          if (!lcJsonContent.trim()) {
            setErrorMessage('Please provide structured problem JSON.');
            setIsPreviewing(false);
            return;
          }
          try {
            payload = JSON.parse(lcJsonContent);
          } catch {
            setErrorMessage('Invalid JSON syntax in LeetCode problem data.');
            setIsPreviewing(false);
            return;
          }
        } else {
          if (!lcTitle.trim() || !lcProblemStatement.trim()) {
            setErrorMessage('Question title and problem statement are required.');
            setIsPreviewing(false);
            return;
          }

          payload = {
            title: lcTitle.trim(),
            problem_statement: lcProblemStatement.trim(),
            difficulty: lcDifficulty,
            constraints: lcConstraints.trim(),
            input_format: lcInputFormat.trim(),
            output_format: lcOutputFormat.trim(),
            examples: lcSampleInput.trim() ? [
              { input: lcSampleInput.trim(), output: lcSampleOutput.trim(), explanation: 'Sample Example 1' }
            ] : [],
            test_cases: lcSampleInput.trim() ? [
              { name: 'Sample Case 1', input_data: lcSampleInput.trim(), expected_output: lcSampleOutput.trim(), points: 5, is_hidden: false }
            ] : []
          };
        }

        const res = await previewPlatformImport('LEETCODE_MANUAL', payload);
        if (res.data) {
          setPreviewData(res.data);
        }
      } else if (activePlatform === 'ZIP') {
        if (!selectedFile) {
          setErrorMessage('Please select a CODEGUARD package ZIP file.');
          setIsPreviewing(false);
          return;
        }
        const res = await previewPlatformImport('CODEGUARD_ZIP', undefined, selectedFile);
        if (res.data) {
          setPreviewData(res.data);
        }
      } else if (activePlatform === 'JSON') {
        if (!jsonText.trim()) {
          setErrorMessage('Please paste problem definition JSON.');
          setIsPreviewing(false);
          return;
        }
        let parsed: any;
        try {
          parsed = JSON.parse(jsonText);
        } catch {
          setErrorMessage('Invalid JSON syntax.');
          setIsPreviewing(false);
          return;
        }
        const res = await previewPlatformImport('MANUAL_JSON', parsed);
        if (res.data) {
          setPreviewData(res.data);
        }
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to parse import preview.');
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!previewData?.normalized_payload) return;
    setIsConfirming(true);
    setErrorMessage(null);

    try {
      const res = await confirmPlatformImport(previewData.normalized_payload);
      if (res.data) {
        onClose();
        if (onSuccess) onSuccess();
        // Open single-page workspace for the imported draft question
        navigate(`/admin/questions/${res.data.question_id}/versions/${res.data.version_number}`);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to create imported draft question.');
      setIsConfirming(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-platform-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
    >
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 max-w-3xl w-full overflow-hidden text-slate-900 flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-8 py-6 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-between shrink-0">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono font-semibold uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Platform Ingestion</span>
            </div>
            <h2 id="import-platform-modal-title" className="text-xl font-extrabold tracking-tight">
              Import Coding Question
            </h2>
            <p className="text-xs text-slate-300">
              Import an authorized coding question into CODEGUARD as a Draft.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-white/10 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-8 overflow-y-auto space-y-6 flex-1">
          {errorMessage && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{errorMessage}</div>
            </div>
          )}

          {!previewData ? (
            <>
              {/* Platform Selector Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <button
                  type="button"
                  onClick={() => { setActivePlatform('HACKERRANK'); setErrorMessage(null); }}
                  className={`p-3.5 rounded-2xl border-2 text-left transition-all flex flex-col justify-between ${
                    activePlatform === 'HACKERRANK'
                      ? 'border-emerald-600 bg-emerald-50/50 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 font-bold flex items-center justify-center text-xs">
                      HR
                    </div>
                    {platformStatuses?.hackerrank?.configured ? (
                      <span className="w-2 h-2 rounded-full bg-emerald-500" title="API Configured" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-amber-400" title="Manual / JSON" />
                    )}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">HackerRank</div>
                    <div className="text-[10px] text-slate-500 font-mono">
                      {platformStatuses?.hackerrank?.configured ? 'API Token' : 'Structured'}
                    </div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => { setActivePlatform('LEETCODE'); setErrorMessage(null); }}
                  className={`p-3.5 rounded-2xl border-2 text-left transition-all flex flex-col justify-between ${
                    activePlatform === 'LEETCODE'
                      ? 'border-amber-600 bg-amber-50/50 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 font-bold flex items-center justify-center text-xs">
                      LC
                    </div>
                    <span className="w-2 h-2 rounded-full bg-blue-500" title="Manual / Structured" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">LeetCode</div>
                    <div className="text-[10px] text-slate-500 font-mono">Manual Content</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => { setActivePlatform('ZIP'); setErrorMessage(null); }}
                  className={`p-3.5 rounded-2xl border-2 text-left transition-all flex flex-col justify-between ${
                    activePlatform === 'ZIP'
                      ? 'border-blue-600 bg-blue-50/50 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-800 font-bold flex items-center justify-center text-xs">
                      ZIP
                    </div>
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">CODEGUARD ZIP</div>
                    <div className="text-[10px] text-slate-500 font-mono">Archive file</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => { setActivePlatform('JSON'); setErrorMessage(null); }}
                  className={`p-3.5 rounded-2xl border-2 text-left transition-all flex flex-col justify-between ${
                    activePlatform === 'JSON'
                      ? 'border-purple-600 bg-purple-50/50 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-8 h-8 rounded-lg bg-purple-100 text-purple-800 font-bold flex items-center justify-center text-xs">
                      {"{}"}
                    </div>
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">Structured JSON</div>
                    <div className="text-[10px] text-slate-500 font-mono">Direct Paste</div>
                  </div>
                </button>
              </div>

              {/* HackerRank Tab Panel */}
              {activePlatform === 'HACKERRANK' && (
                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 flex items-start gap-2.5">
                    <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-900">Authorized Integration Policy:</span> CODEGUARD communicates strictly through authorized HackerRank API tokens or structured exports. Scraping and crawling are never performed.
                    </div>
                  </div>

                  {platformStatuses?.hackerrank?.configured ? (
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-slate-800">HackerRank Challenge Slug / ID</label>
                      <input
                        type="text"
                        placeholder="e.g. solve-me-first"
                        value={hrSlug}
                        onChange={(e) => setHrSlug(e.target.value)}
                        className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                      />
                      <p className="text-[11px] text-slate-500">
                        Will be resolved via your configured HackerRank API credentials.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Badge variant="warning" size="sm">HackerRank Integration Not Configured</Badge>
                        <span className="text-[11px] text-slate-500 font-mono">API token not set in environment</span>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-bold text-slate-800">Paste HackerRank Problem JSON Export</label>
                        <textarea
                          rows={6}
                          placeholder='{"name": "Solve Me First", "body": "...", "examples": [...], "test_cases": [...]}'
                          value={hrRawJson}
                          onChange={(e) => setHrRawJson(e.target.value)}
                          className="w-full p-3 rounded-xl border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* LeetCode Tab Panel */}
              {activePlatform === 'LEETCODE' && (
                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-amber-950">Terms Compliance Notice:</span> LeetCode terms strictly prohibit crawling, automated scraping, or unauthorized spidering. Please paste problem text or upload a structured export below.
                    </div>
                  </div>

                  <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
                    <button
                      type="button"
                      onClick={() => setLcInputMode('FORM')}
                      className={`text-xs font-bold pb-1 px-2 border-b-2 transition-colors ${
                        lcInputMode === 'FORM' ? 'border-amber-600 text-amber-800' : 'border-transparent text-slate-500'
                      }`}
                    >
                      Paste Problem Form
                    </button>
                    <button
                      type="button"
                      onClick={() => setLcInputMode('JSON')}
                      className={`text-xs font-bold pb-1 px-2 border-b-2 transition-colors ${
                        lcInputMode === 'JSON' ? 'border-amber-600 text-amber-800' : 'border-transparent text-slate-500'
                      }`}
                    >
                      Paste JSON Export
                    </button>
                  </div>

                  {lcInputMode === 'FORM' ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div className="sm:col-span-2 space-y-1">
                          <label className="text-xs font-bold text-slate-800">Problem Title *</label>
                          <input
                            type="text"
                            placeholder="e.g. Two Sum"
                            value={lcTitle}
                            onChange={(e) => setLcTitle(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-amber-500 focus:outline-none"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-bold text-slate-800">Difficulty</label>
                          <select
                            value={lcDifficulty}
                            onChange={(e: any) => setLcDifficulty(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-amber-500 focus:outline-none"
                          >
                            <option value="EASY">EASY</option>
                            <option value="MEDIUM">MEDIUM</option>
                            <option value="HARD">HARD</option>
                          </select>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-800">Problem Statement (Markdown) *</label>
                        <textarea
                          rows={4}
                          placeholder="Given an array of integers nums and an integer target..."
                          value={lcProblemStatement}
                          onChange={(e) => setLcProblemStatement(e.target.value)}
                          className="w-full p-3 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-amber-500 focus:outline-none"
                        />
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-xs font-bold text-slate-800">Constraints</label>
                          <input
                            type="text"
                            placeholder="e.g. 2 <= nums.length <= 10^4"
                            value={lcConstraints}
                            onChange={(e) => setLcConstraints(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-amber-500 focus:outline-none"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-bold text-slate-800">Input Format</label>
                          <input
                            type="text"
                            placeholder="Line 1: space-separated integers..."
                            value={lcInputFormat}
                            onChange={(e) => setLcInputFormat(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-amber-500 focus:outline-none"
                          />
                        </div>
                        <div className="space-y-1 sm:col-span-2">
                          <label className="text-xs font-bold text-slate-800">Output Format</label>
                          <input
                            type="text"
                            placeholder="e.g. Return an array of two integers..."
                            value={lcOutputFormat}
                            onChange={(e) => setLcOutputFormat(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-amber-500 focus:outline-none"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-xs font-bold text-slate-800">Sample Input</label>
                          <textarea
                            rows={2}
                            placeholder="2 7 11 15\n9"
                            value={lcSampleInput}
                            onChange={(e) => setLcSampleInput(e.target.value)}
                            className="w-full p-2.5 rounded-lg border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-amber-500 focus:outline-none"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-bold text-slate-800">Sample Expected Output</label>
                          <textarea
                            rows={2}
                            placeholder="0 1"
                            value={lcSampleOutput}
                            onChange={(e) => setLcSampleOutput(e.target.value)}
                            className="w-full p-2.5 rounded-lg border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-amber-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-slate-800">Paste JSON Problem Data</label>
                      <textarea
                        rows={7}
                        placeholder='{"title": "Two Sum", "problem_statement": "...", "examples": [...], "test_cases": [...]}'
                        value={lcJsonContent}
                        onChange={(e) => setLcJsonContent(e.target.value)}
                        className="w-full p-3 rounded-xl border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-amber-500 focus:outline-none"
                      />
                    </div>
                  )}
                </div>
              )}

              {/* ZIP Tab Panel */}
              {activePlatform === 'ZIP' && (
                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700">
                    <p className="font-semibold text-slate-900 mb-1">Standard CODEGUARD Question Archive (.zip):</p>
                    <p className="text-slate-500">
                      Must contain a root <code className="text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded font-mono">question.json</code> or a combination of <code className="text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded font-mono">problem.md</code>, <code className="text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded font-mono">metadata.json</code>, and test case files.
                    </p>
                  </div>

                  <div className="border-2 border-dashed border-slate-300 rounded-2xl p-8 text-center hover:border-slate-400 transition-colors">
                    <input
                      type="file"
                      accept=".zip"
                      id="zip-file-input"
                      onChange={(e) => {
                        if (e.target.files?.[0]) setSelectedFile(e.target.files[0]);
                      }}
                      className="hidden"
                    />
                    <label htmlFor="zip-file-input" className="cursor-pointer space-y-2 flex flex-col items-center">
                      <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                        <Upload className="w-6 h-6" />
                      </div>
                      <div className="text-xs font-bold text-slate-800">
                        {selectedFile ? selectedFile.name : 'Click to select question ZIP package'}
                      </div>
                      <div className="text-[11px] text-slate-500">Maximum package size: 25 MB</div>
                    </label>
                  </div>
                </div>
              )}

              {/* Structured JSON Panel */}
              {activePlatform === 'JSON' && (
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-800">Paste Problem Definition JSON</label>
                  <textarea
                    rows={8}
                    placeholder='{\n  "title": "Matrix Inversion",\n  "problem_statement": "...",\n  "difficulty": "MEDIUM",\n  "test_cases": [...]\n}'
                    value={jsonText}
                    onChange={(e) => setJsonText(e.target.value)}
                    className="w-full p-3.5 rounded-xl border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                </div>
              )}
            </>
          ) : (
            /* Import Preview Card */
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-900 flex items-center gap-1.5 uppercase font-mono tracking-wider">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Preview Ready: {previewData.source}
                  </span>
                  <Badge variant="warning" size="sm">Will be saved as DRAFT</Badge>
                </div>
                <h3 className="text-base font-extrabold text-slate-900">{previewData.title}</h3>
                <div className="flex items-center gap-3 text-xs flex-wrap font-mono">
                  <span className="px-2 py-0.5 rounded-md bg-white border border-slate-200 text-slate-700 font-semibold">
                    {previewData.difficulty}
                  </span>
                  <span className="text-slate-600">
                    {previewData.test_case_count} Test Cases ({previewData.sample_test_count} Sample, {previewData.hidden_test_count} Hidden)
                  </span>
                  <span className="text-slate-600">
                    Languages: {previewData.languages.join(', ')}
                  </span>
                </div>
              </div>

              {/* Verification Invariant Notice */}
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                <div className="font-bold text-slate-900 flex items-center gap-2">
                  <Shield className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Authoritative Verification Invariant:</span>
                </div>
                <p className="text-slate-600 leading-relaxed">
                  All imported test cases start as <span className="font-mono text-rose-700 font-bold">Unverified</span>. The question enters as a Draft and must undergo Question Health verification and administrator review before publishing.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-8 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between shrink-0">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>

          {!previewData ? (
            <Button
              variant="primary"
              size="md"
              onClick={handleGeneratePreview}
              disabled={isPreviewing}
              className="flex items-center gap-2"
            >
              {isPreviewing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Parsing Import...</span>
                </>
              ) : (
                <>
                  <span>Preview Import</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </Button>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPreviewData(null)}
              >
                Back to Edit
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleConfirmImport}
                disabled={isConfirming}
                className="flex items-center gap-2"
              >
                {isConfirming ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Importing Draft...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Import as Draft</span>
                  </>
                )}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
