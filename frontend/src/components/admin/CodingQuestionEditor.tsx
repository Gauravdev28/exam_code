import React, { useState } from 'react';
import {
  Code2,
  CheckCircle2,
  AlertCircle,
  Play,
  Eye,
  Plus,
  Trash2,
  Lock,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Layers,
  FileText,
  Bookmark,
  Check,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { QuestionPreviewModal } from './QuestionPreviewModal';
import { runSandboxTest, RunSandboxResult } from '../../api/questions';
import { CodingLanguage, Difficulty, TestCase } from '../../types/question';

interface ExampleItem {
  id: string;
  name: string;
  input: string;
  output: string;
  explanation: string;
}

interface CodingQuestionEditorProps {
  initialData?: any;
  isLocked?: boolean;
  versionNumber?: number;
  onSaveDraft: (payload: any) => Promise<void>;
  onPublish: (payload: any) => Promise<void>;
  isSaving: boolean;
  isPublishing: boolean;
}

const DEFAULT_STARTER_CODE: Record<CodingLanguage, string> = {
  PYTHON: `# Write your solution below\ndef solve():\n    import sys\n    input_data = sys.stdin.read().split()\n    if not input_data:\n        return\n    # Process solution\n    print(input_data[0])\n\nif __name__ == '__main__':\n    solve()\n`,
  CPP: `#include <iostream>\n#include <vector>\n#include <string>\n\nusing namespace std;\n\nint main() {\n    ios_base::sync_with_stdio(false);\n    cin.tie(NULL);\n    \n    // Read input and solve\n    string s;\n    if (cin >> s) {\n        cout << s << "\\n";\n    }\n    \n    return 0;\n}\n`,
  JAVA: `import java.util.Scanner;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in);\n        if (scanner.hasNext()) {\n            String input = scanner.next();\n            System.out.println(input);\n        }\n    }\n}\n`,
};

export const CodingQuestionEditor: React.FC<CodingQuestionEditorProps> = ({
  initialData,
  isLocked = false,
  versionNumber = 1,
  onSaveDraft,
  onPublish,
  isSaving,
  isPublishing,
}) => {
  // 6-step authoring workflow state (1 to 6)
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Step 1: Problem Definition
  const [title, setTitle] = useState(initialData?.title || '');
  const [difficulty, setDifficulty] = useState<Difficulty>(initialData?.difficulty || 'MEDIUM');
  const [points, setPoints] = useState<number>(initialData?.points || 10);
  const [negativeMarkingEnabled, setNegativeMarkingEnabled] = useState(initialData?.negative_marking_enabled || false);
  const [negativePoints, setNegativePoints] = useState<number>(initialData?.negative_points || 0);
  const [tagsInput, setTagsInput] = useState(
    initialData?.tags?.map((t: any) => t.name || t).join(', ') || ''
  );
  const [description, setDescription] = useState(initialData?.description || '');
  const [constraints, setConstraints] = useState(
    initialData?.coding_config?.constraints || ''
  );
  const [inputFormat, setInputFormat] = useState(
    initialData?.coding_config?.input_format || ''
  );
  const [outputFormat, setOutputFormat] = useState(
    initialData?.coding_config?.output_format || ''
  );
  const [instructions, setInstructions] = useState(initialData?.instructions || '');
  const [adminNotes, setAdminNotes] = useState(
    initialData?.coding_config?.admin_notes || initialData?.type_config?.admin_notes || ''
  );

  // Step 2: Examples
  const [examples, setExamples] = useState<ExampleItem[]>(() => {
    if (initialData?.examples && Array.isArray(initialData.examples) && initialData.examples.length > 0) {
      return initialData.examples.map((ex: any, idx: number) => ({
        id: `ex-${idx}`,
        name: ex.name || `Example ${idx + 1}`,
        input: ex.input || '',
        output: ex.output || '',
        explanation: ex.explanation || '',
      }));
    }
    // Extract from existing sample test cases if available
    const existingSamples = initialData?.coding_config?.test_cases?.filter((tc: any) => !tc.is_hidden) || [];
    if (existingSamples.length > 0) {
      return existingSamples.map((tc: any, idx: number) => ({
        id: `ex-${idx}`,
        name: `Example ${idx + 1}`,
        input: tc.input_data || '',
        output: tc.expected_output || '',
        explanation: tc.explanation || '',
      }));
    }
    return [
      { id: 'ex-1', name: 'Example 1', input: '2 7 11 15\n9', output: '0 1', explanation: 'nums[0] + nums[1] == 9, return [0, 1].' },
    ];
  });

  // Step 3: Languages & Starter Code
  const [allowedLanguages, setAllowedLanguages] = useState<CodingLanguage[]>(
    initialData?.coding_config?.allowed_languages || ['PYTHON', 'CPP', 'JAVA']
  );
  const [activeCodeTab, setActiveCodeTab] = useState<CodingLanguage>('PYTHON');
  const [starterCodeMap, setStarterCodeMap] = useState<Record<CodingLanguage, string>>(() => {
    return {
      PYTHON: initialData?.coding_config?.starter_code || DEFAULT_STARTER_CODE.PYTHON,
      CPP: DEFAULT_STARTER_CODE.CPP,
      JAVA: DEFAULT_STARTER_CODE.JAVA,
    };
  });
  const [timeLimitMs, setTimeLimitMs] = useState<number>(
    initialData?.coding_config?.time_limit_ms || 2000
  );
  const [memoryLimitMb, setMemoryLimitMb] = useState<number>(
    initialData?.coding_config?.memory_limit_mb || 256
  );

  // Step 4: Test Cases Workspace
  const [testCases, setTestCases] = useState<TestCase[]>(() => {
    if (initialData?.coding_config?.test_cases && initialData.coding_config.test_cases.length > 0) {
      return initialData.coding_config.test_cases;
    }
    return [
      { input_data: '2 7 11 15\n9', expected_output: '0 1', points: 5, is_hidden: false, execution_order: 1 },
      { input_data: '3 2 4\n6', expected_output: '1 2', points: 5, is_hidden: true, execution_order: 2 },
    ];
  });

  // Step 5: Sandbox Evaluation
  const [sandboxCode, setSandboxCode] = useState<string>(starterCodeMap.PYTHON);
  const [sandboxLang, setSandboxLang] = useState<CodingLanguage>('PYTHON');
  const [sandboxStdin, setSandboxStdin] = useState<string>('2 7 11 15\n9');
  const [sandboxExpected, setSandboxExpected] = useState<string>('0 1');
  const [sandboxLoading, setSandboxLoading] = useState<boolean>(false);
  const [sandboxResult, setSandboxResult] = useState<RunSandboxResult | null>(null);

  // Step 6: Preview Modal
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // Synchronize examples into test cases if needed
  const handleSyncExamplesToTestCases = () => {
    const sampleCases: TestCase[] = examples.map((ex, idx) => ({
      input_data: ex.input,
      expected_output: ex.output,
      points: Math.max(1, Math.floor(points / (examples.length + 1))),
      is_hidden: false,
      execution_order: idx + 1,
    }));

    // Keep hidden test cases
    const hiddenCases = testCases.filter((tc) => tc.is_hidden);
    if (hiddenCases.length === 0) {
      hiddenCases.push({
        input_data: '3 3\n6',
        expected_output: '0 1',
        points: Math.max(1, points - sampleCases.reduce((sum, c) => sum + c.points, 0)),
        is_hidden: true,
        execution_order: sampleCases.length + 1,
      });
    }

    setTestCases([...sampleCases, ...hiddenCases]);
  };

  // Test Case Point Sum Calculation
  const totalTestCasePoints = testCases.reduce((sum, tc) => sum + (Number(tc.points) || 0), 0);
  const isPointSumValid = totalTestCasePoints === points;

  const handleAutoBalancePoints = () => {
    if (testCases.length === 0) return;
    const basePoints = Math.floor(points / testCases.length);
    const remainder = points % testCases.length;
    const balanced = testCases.map((tc, idx) => ({
      ...tc,
      points: idx === 0 ? basePoints + remainder : basePoints,
    }));
    setTestCases(balanced);
  };

  // Run Sandbox Code Execution via Judge0
  const handleRunSandbox = async () => {
    setSandboxLoading(true);
    setSandboxResult(null);
    try {
      const res = await runSandboxTest({
        source_code: sandboxCode,
        language: sandboxLang,
        stdin: sandboxStdin,
        expected_output: sandboxExpected,
        cpu_time_limit_ms: timeLimitMs,
        memory_limit_mb: memoryLimitMb,
      });
      if (res.data) {
        setSandboxResult(res.data);
      }
    } catch (err: any) {
      setSandboxResult({
        status_id: 13,
        status_description: err.error?.message || 'External sandbox unavailable (Fail-Closed).',
        stdout: null,
        stderr: err.message || 'Execution failed.',
        compile_output: null,
        time: 0,
        memory: 0,
        passed: false,
      });
    } finally {
      setSandboxLoading(false);
    }
  };

  // Assemble Complete Payload
  const assemblePayload = () => {
    const parsedTags = tagsInput
      .split(',')
      .map((t: string) => t.trim())
      .filter(Boolean);

    return {
      question_type: 'CODING',
      title: title.trim(),
      description: description.trim(),
      instructions: instructions.trim(),
      points,
      negative_marking_enabled: negativeMarkingEnabled,
      negative_points: negativeMarkingEnabled ? negativePoints : 0,
      difficulty,
      tags: parsedTags,
      type_config: {
        admin_notes: adminNotes.trim(),
      },
      coding_config: {
        problem_statement: description.trim(),
        constraints: constraints.trim(),
        input_format: inputFormat.trim(),
        output_format: outputFormat.trim(),
        admin_notes: adminNotes.trim(),
        allowed_languages: allowedLanguages,
        starter_code: starterCodeMap[activeCodeTab] || starterCodeMap.PYTHON,
        time_limit_ms: timeLimitMs,
        memory_limit_mb: memoryLimitMb,
      },
      test_cases: testCases.map((tc, idx) => ({
        input_data: tc.input_data,
        expected_output: tc.expected_output,
        points: Number(tc.points) || 0,
        is_hidden: Boolean(tc.is_hidden),
        execution_order: idx + 1,
      })),
    };
  };

  const handleSaveDraftClick = () => {
    const payload = assemblePayload();
    onSaveDraft(payload);
  };

  const handlePublishClick = () => {
    const payload = assemblePayload();
    onPublish(payload);
  };

  // Step 6 Quality Checklist
  const qualityChecks = [
    { label: 'Problem title specified', passed: Boolean(title.trim()) },
    { label: 'Problem statement / prompt written', passed: Boolean(description.trim()) },
    { label: 'At least one programming language enabled', passed: allowedLanguages.length > 0 },
    { label: 'At least one public/sample test case configured', passed: testCases.some((t) => !t.is_hidden) },
    { label: 'At least one hidden grading test case configured', passed: testCases.some((t) => t.is_hidden) },
    {
      label: `Test case points sum matches question total (${totalTestCasePoints}/${points} pts)`,
      passed: isPointSumValid,
    },
  ];
  const allQualityChecksPassed = qualityChecks.every((c) => c.passed);

  const steps = [
    { num: 1, title: 'Problem Definition', icon: <FileText className="w-4 h-4" /> },
    { num: 2, title: 'Examples', icon: <Bookmark className="w-4 h-4" /> },
    { num: 3, title: 'Languages & Starter Code', icon: <Code2 className="w-4 h-4" /> },
    { num: 4, title: 'Test Cases Workspace', icon: <Layers className="w-4 h-4" /> },
    { num: 5, title: 'Sandbox Evaluation', icon: <Play className="w-4 h-4" /> },
    { num: 6, title: 'Preview & Publish', icon: <Sparkles className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6">
      {/* 6-Step Workflow Navigation Header */}
      <div className="bg-white rounded-2xl border border-slate-200 p-3 shadow-sm">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {steps.map((step) => {
            const isActive = currentStep === step.num;
            const isCompleted = currentStep > step.num;

            return (
              <button
                key={step.num}
                type="button"
                onClick={() => setCurrentStep(step.num)}
                className={`flex items-center gap-2 p-2.5 rounded-xl border text-left transition-all ${
                  isActive
                    ? 'bg-emerald-50 border-emerald-500 text-emerald-900 shadow-sm ring-1 ring-emerald-500/30'
                    : isCompleted
                    ? 'bg-slate-50/80 border-slate-200 text-slate-700 hover:bg-slate-100'
                    : 'bg-white border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-slate-50'
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-mono font-bold shrink-0 ${
                    isActive
                      ? 'bg-emerald-600 text-white'
                      : isCompleted
                      ? 'bg-slate-200 text-slate-700'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isCompleted ? <Check className="w-3.5 h-3.5 stroke-[2.5]" /> : step.num}
                </div>
                <div className="min-w-0">
                  <div className="text-[10px] uppercase font-mono font-bold tracking-wider text-slate-500">
                    Step {step.num}
                  </div>
                  <div className="text-xs font-bold truncate">{step.title}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* STEP 1: PROBLEM DEFINITION */}
      {currentStep === 1 && (
        <Card className="p-6 space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FileText className="w-5 h-5 text-emerald-600" />
              Step 1: Problem Definition & Constraints
            </h3>
            <p className="text-xs text-slate-500">
              Configure core question identity, scoring weights, constraints, and instructions.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5 md:col-span-2">
              <label className="block text-xs font-semibold text-slate-700">Question Title *</label>
              <input
                type="text"
                disabled={isLocked}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Two Sum / Longest Palindromic Substring"
                className="w-full px-3.5 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Difficulty</label>
              <select
                disabled={isLocked}
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-semibold focus:ring-2 focus:ring-emerald-500"
              >
                <option value="EASY">EASY</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HARD">HARD</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Total Points *</label>
              <input
                type="number"
                min={1}
                disabled={isLocked}
                value={points}
                onChange={(e) => setPoints(Math.max(1, parseInt(e.target.value, 10) || 10))}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-semibold text-slate-700">Negative Marking</label>
                <input
                  type="checkbox"
                  disabled={isLocked}
                  checked={negativeMarkingEnabled}
                  onChange={(e) => setNegativeMarkingEnabled(e.target.checked)}
                  className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                />
              </div>
              <input
                type="number"
                min={0}
                step={0.5}
                disabled={isLocked || !negativeMarkingEnabled}
                value={negativePoints}
                onChange={(e) => setNegativePoints(Math.max(0, parseFloat(e.target.value) || 0))}
                placeholder="Penalty (e.g. 1)"
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono text-xs focus:ring-2 focus:ring-emerald-500 disabled:bg-slate-100 disabled:text-slate-400"
              />
            </div>

            <div className="space-y-1.5 md:col-span-2">
              <label className="block text-xs font-semibold text-slate-700">Tags (Comma-separated)</label>
              <input
                type="text"
                disabled={isLocked}
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="Algorithms, Arrays, Dynamic Programming, Strings"
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          {/* Problem Statement (Prompt) */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Problem Statement (Markdown) *</label>
            <textarea
              rows={6}
              disabled={isLocked}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target..."
              className="w-full px-3.5 py-2.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-emerald-500 font-sans"
            />
          </div>

          {/* Constraints */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Problem Constraints</label>
            <textarea
              rows={3}
              disabled={isLocked}
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              placeholder="2 <= nums.length <= 10^4&#10;-10^9 <= nums[i] <= 10^9&#10;Only one valid answer exists."
              className="w-full px-3.5 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {/* Input & Output Format */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Input Format</label>
              <textarea
                rows={2}
                disabled={isLocked}
                value={inputFormat}
                onChange={(e) => setInputFormat(e.target.value)}
                placeholder="First line contains N. Second line contains space-separated integers."
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Output Format</label>
              <textarea
                rows={2}
                disabled={isLocked}
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value)}
                placeholder="Print the zero-indexed integer indices separated by a space."
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          {/* Student Instructions */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">Student Instructions (Optional)</label>
            <input
              type="text"
              disabled={isLocked}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g., Read input from standard input (stdin) and print output to standard output (stdout)."
              className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {/* Internal Admin Notes (Never exposed to student) */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-amber-600" />
                Internal Admin Notes
              </label>
              <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-200">
                Admin Eyes Only — Never Exposed to Candidates
              </span>
            </div>
            <textarea
              rows={2}
              disabled={isLocked}
              value={adminNotes}
              onChange={(e) => setAdminNotes(e.target.value)}
              placeholder="Rubric notes, solution approach hints, or internal reviewer guidelines..."
              className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </Card>
      )}

      {/* STEP 2: EXAMPLES */}
      {currentStep === 2 && (
        <Card className="p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Bookmark className="w-5 h-5 text-emerald-600" />
                Step 2: Examples & Explanations
              </h3>
              <p className="text-xs text-slate-500">
                Visible examples help candidates understand input/output structure. These map to sample test cases.
              </p>
            </div>
            {!isLocked && (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    const newEx: ExampleItem = {
                      id: `ex-${Date.now()}`,
                      name: `Example ${examples.length + 1}`,
                      input: '',
                      output: '',
                      explanation: '',
                    };
                    setExamples([...examples, newEx]);
                  }}
                >
                  <Plus className="w-3.5 h-3.5 mr-1" /> Add Example
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleSyncExamplesToTestCases}
                  title="Generate sample test cases from these examples"
                >
                  <Layers className="w-3.5 h-3.5 mr-1 text-emerald-600" /> Sync to Test Cases
                </Button>
              </div>
            )}
          </div>

          <div className="space-y-4">
            {examples.map((ex, idx) => (
              <div key={ex.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-800 font-mono">
                    Example {idx + 1}
                  </span>
                  {!isLocked && examples.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setExamples(examples.filter((e) => e.id !== ex.id))}
                      className="text-slate-400 hover:text-rose-600 transition p-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600">Sample Input</label>
                    <textarea
                      rows={3}
                      disabled={isLocked}
                      value={ex.input}
                      onChange={(e) => {
                        const updated = [...examples];
                        updated[idx].input = e.target.value;
                        setExamples(updated);
                      }}
                      placeholder="e.g. 4&#10;1 2 3 4"
                      className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600">Expected Output</label>
                    <textarea
                      rows={3}
                      disabled={isLocked}
                      value={ex.output}
                      onChange={(e) => {
                        const updated = [...examples];
                        updated[idx].output = e.target.value;
                        setExamples(updated);
                      }}
                      placeholder="e.g. 10"
                      className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-600">Explanation (Optional)</label>
                  <input
                    type="text"
                    disabled={isLocked}
                    value={ex.explanation}
                    onChange={(e) => {
                      const updated = [...examples];
                      updated[idx].explanation = e.target.value;
                      setExamples(updated);
                    }}
                    placeholder="Explanation of the derivation..."
                    className="w-full p-2 rounded-lg bg-white border border-slate-300 text-xs focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* STEP 3: LANGUAGES & STARTER CODE */}
      {currentStep === 3 && (
        <Card className="p-6 space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Code2 className="w-5 h-5 text-emerald-600" />
              Step 3: Languages & Starter Code Templates
            </h3>
            <p className="text-xs text-slate-500">
              Configure allowed runtime languages (Python, C++, Java) and default starter boilerplate.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-700">Allowed Languages *</label>
              <div className="flex flex-col gap-2 pt-1">
                {(['PYTHON', 'CPP', 'JAVA'] as CodingLanguage[]).map((lang) => (
                  <label
                    key={lang}
                    className="flex items-center gap-2 p-2 rounded-lg border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-700 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      disabled={isLocked}
                      checked={allowedLanguages.includes(lang)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setAllowedLanguages([...allowedLanguages, lang]);
                        } else {
                          if (allowedLanguages.length <= 1) {
                            alert('At least one language must remain allowed.');
                            return;
                          }
                          setAllowedLanguages(allowedLanguages.filter((l) => l !== lang));
                        }
                      }}
                      className="rounded text-emerald-600 focus:ring-emerald-500"
                    />
                    <span>{lang === 'PYTHON' ? 'Python 3.11+' : lang === 'CPP' ? 'C++ (GCC 13)' : 'Java (OpenJDK 17)'}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">CPU Time Limit (ms)</label>
              <input
                type="number"
                min={100}
                max={5000}
                disabled={isLocked}
                value={timeLimitMs}
                onChange={(e) => setTimeLimitMs(Math.min(5000, Math.max(100, parseInt(e.target.value, 10) || 2000)))}
                className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
              />
              <span className="text-[10px] text-slate-500">Default: 2000ms (max 5000ms)</span>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Memory Limit (MB)</label>
              <input
                type="number"
                min={64}
                max={256}
                disabled={isLocked}
                value={memoryLimitMb}
                onChange={(e) => setMemoryLimitMb(Math.min(256, Math.max(64, parseInt(e.target.value, 10) || 256)))}
                className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
              />
              <span className="text-[10px] text-slate-500">Default: 256MB (sandbox bound)</span>
            </div>
          </div>

          {/* Starter Code Tabs */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-700">Starter Code Boilerplate</label>
              <div className="flex items-center gap-1">
                {allowedLanguages.map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => setActiveCodeTab(lang)}
                    className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition ${
                      activeCodeTab === lang
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {lang}
                  </button>
                ))}
              </div>
            </div>

            <textarea
              rows={12}
              disabled={isLocked}
              value={starterCodeMap[activeCodeTab] || ''}
              onChange={(e) => {
                setStarterCodeMap({
                  ...starterCodeMap,
                  [activeCodeTab]: e.target.value,
                });
              }}
              className="w-full p-3 rounded-xl bg-slate-900 text-emerald-400 font-mono text-xs focus:ring-2 focus:ring-emerald-500 border border-slate-800 leading-relaxed"
            />
          </div>
        </Card>
      )}

      {/* STEP 4: TEST CASES WORKSPACE */}
      {currentStep === 4 && (
        <Card className="p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Layers className="w-5 h-5 text-emerald-600" />
                Step 4: Test Cases Workspace
              </h3>
              <p className="text-xs text-slate-500">
                Configure sample (visible to candidates) and hidden test cases for automated scoring.
              </p>
            </div>

            {!isLocked && (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    const newTc: TestCase = {
                      input_data: '',
                      expected_output: '',
                      points: 5,
                      is_hidden: true,
                      execution_order: testCases.length + 1,
                    };
                    setTestCases([...testCases, newTc]);
                  }}
                >
                  <Plus className="w-3.5 h-3.5 mr-1" /> Add Test Case
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleAutoBalancePoints}
                  title="Balance points evenly to match Question Total Points"
                >
                  Auto-Balance Points
                </Button>
              </div>
            )}
          </div>

          {/* Real-time Point Sum Validation Banner */}
          <div
            className={`p-3.5 rounded-xl border flex items-center justify-between text-xs font-mono ${
              isPointSumValid
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-amber-50 border-amber-200 text-amber-900'
            }`}
          >
            <div className="flex items-center gap-2">
              {isPointSumValid ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              )}
              <span>
                Total Points: <strong>{points}</strong> | Allocated Test Case Points:{' '}
                <strong>{totalTestCasePoints}</strong>
              </span>
            </div>
            {!isPointSumValid && (
              <span className="font-bold text-rose-600">
                Point discrepancy: {totalTestCasePoints - points > 0 ? `+${totalTestCasePoints - points}` : totalTestCasePoints - points} pts
              </span>
            )}
          </div>

          {/* Test Cases List */}
          <div className="space-y-4">
            {testCases.map((tc, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-xl border transition-all ${
                  tc.is_hidden
                    ? 'bg-slate-50 border-slate-300'
                    : 'bg-emerald-50/40 border-emerald-200'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold font-mono text-slate-800">
                      Test Case #{idx + 1}
                    </span>
                    <Badge variant={tc.is_hidden ? 'neutral' : 'success'}>
                      {tc.is_hidden ? 'HIDDEN (Evaluation Only)' : 'SAMPLE (Visible in Exam)'}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-3">
                    {/* Sample vs Hidden Toggle */}
                    <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer font-medium">
                      <input
                        type="checkbox"
                        disabled={isLocked}
                        checked={tc.is_hidden}
                        onChange={(e) => {
                          const updated = [...testCases];
                          updated[idx].is_hidden = e.target.checked;
                          setTestCases(updated);
                        }}
                        className="rounded text-slate-900 focus:ring-slate-500"
                      />
                      <span>Hidden</span>
                    </label>

                    {/* Points Allocation */}
                    <div className="flex items-center gap-1 text-xs">
                      <span className="text-slate-500">Points:</span>
                      <input
                        type="number"
                        min={0}
                        max={points}
                        disabled={isLocked}
                        value={tc.points}
                        onChange={(e) => {
                          const updated = [...testCases];
                          updated[idx].points = Math.max(0, parseInt(e.target.value, 10) || 0);
                          setTestCases(updated);
                        }}
                        className="w-16 p-1 rounded bg-white border border-slate-300 font-mono text-xs font-bold text-slate-900 focus:ring-2 focus:ring-emerald-500"
                      />
                    </div>

                    {!isLocked && testCases.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setTestCases(testCases.filter((_, i) => i !== idx))}
                        className="text-slate-400 hover:text-rose-600 transition p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600">Standard Input (stdin)</label>
                    <textarea
                      rows={3}
                      disabled={isLocked}
                      value={tc.input_data}
                      onChange={(e) => {
                        const updated = [...testCases];
                        updated[idx].input_data = e.target.value;
                        setTestCases(updated);
                      }}
                      placeholder="Input passed to stdin..."
                      className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600">Expected Output (stdout)</label>
                    <textarea
                      rows={3}
                      disabled={isLocked}
                      value={tc.expected_output}
                      onChange={(e) => {
                        const updated = [...testCases];
                        updated[idx].expected_output = e.target.value;
                        setTestCases(updated);
                      }}
                      placeholder="Expected exact stdout..."
                      className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* STEP 5: SANDBOX EVALUATION */}
      {currentStep === 5 && (
        <Card className="p-6 space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Play className="w-5 h-5 text-emerald-600" />
              Step 5: Admin Sandbox Execution (Fail-Closed)
            </h3>
            <p className="text-xs text-slate-500">
              Run untrusted candidate code strictly through the isolated Judge0 CE container. No host evaluation fallback.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Code Editor & Settings */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-700">Language:</span>
                  <select
                    value={sandboxLang}
                    onChange={(e) => {
                      const newLang = e.target.value as CodingLanguage;
                      setSandboxLang(newLang);
                      setSandboxCode(starterCodeMap[newLang] || DEFAULT_STARTER_CODE[newLang]);
                    }}
                    className="px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-xs font-mono font-bold"
                  >
                    {allowedLanguages.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>

                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  onClick={handleRunSandbox}
                  disabled={sandboxLoading}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
                >
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                  {sandboxLoading ? 'Executing in Sandbox...' : 'Run in Sandbox'}
                </Button>
              </div>

              <textarea
                rows={12}
                value={sandboxCode}
                onChange={(e) => setSandboxCode(e.target.value)}
                className="w-full p-3 rounded-xl bg-slate-900 text-emerald-400 font-mono text-xs focus:ring-2 focus:ring-emerald-500 border border-slate-800"
              />

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">Test Input (stdin)</label>
                  <textarea
                    rows={3}
                    value={sandboxStdin}
                    onChange={(e) => setSandboxStdin(e.target.value)}
                    className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">Expected Output (Optional)</label>
                  <textarea
                    rows={3}
                    value={sandboxExpected}
                    onChange={(e) => setSandboxExpected(e.target.value)}
                    className="w-full p-2 rounded-lg bg-white border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>
            </div>

            {/* Right: Sandbox Execution Output */}
            <div className="space-y-4">
              <span className="text-xs font-semibold text-slate-700">Execution Diagnostics</span>

              {sandboxLoading ? (
                <div className="h-64 flex flex-col items-center justify-center p-6 rounded-2xl bg-slate-900 text-slate-400 font-mono text-xs space-y-3">
                  <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                  <span>Communicating with isolated Judge0 CE container...</span>
                </div>
              ) : sandboxResult ? (
                <div className="p-4 rounded-2xl bg-slate-900 text-white font-mono text-xs space-y-4">
                  {/* Status Banner */}
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400">Verdict:</span>
                      <span
                        className={`font-bold px-2 py-0.5 rounded ${
                          sandboxResult.passed === true
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : sandboxResult.status_id === 3
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : 'bg-rose-950 text-rose-400 border border-rose-800'
                        }`}
                      >
                        {sandboxResult.status_description}
                        {sandboxResult.passed !== null && ` (${sandboxResult.passed ? 'MATCH' : 'MISMATCH'})`}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-slate-400 text-[11px]">
                      <span>{sandboxResult.time}s</span>
                      <span>{sandboxResult.memory} KB</span>
                    </div>
                  </div>

                  {/* Stdout */}
                  <div className="space-y-1">
                    <span className="text-slate-400 text-[11px] uppercase tracking-wider">stdout</span>
                    <pre className="p-2.5 rounded-lg bg-slate-950 text-emerald-300 border border-slate-800 whitespace-pre-wrap max-h-32 overflow-y-auto">
                      {sandboxResult.stdout || '(Empty stdout)'}
                    </pre>
                  </div>

                  {/* Stderr / Compile Error */}
                  {(sandboxResult.stderr || sandboxResult.compile_output) && (
                    <div className="space-y-1">
                      <span className="text-rose-400 text-[11px] uppercase tracking-wider">
                        stderr / compile error
                      </span>
                      <pre className="p-2.5 rounded-lg bg-rose-950/40 text-rose-300 border border-rose-900 whitespace-pre-wrap max-h-32 overflow-y-auto">
                        {sandboxResult.compile_output || sandboxResult.stderr}
                      </pre>
                    </div>
                  )}
                </div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center p-6 rounded-2xl bg-slate-50 border border-slate-200 text-slate-500 text-xs font-mono text-center space-y-2">
                  <Play className="w-8 h-8 text-slate-400" />
                  <p>Click "Run in Sandbox" to verify execution against Judge0.</p>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* STEP 6: PREVIEW & PUBLISH */}
      {currentStep === 6 && (
        <Card className="p-6 space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-emerald-600" />
              Step 6: Pre-Publish Quality Verification & Student Preview
            </h3>
            <p className="text-xs text-slate-500">
              Review automated quality criteria and verify candidate visibility before publishing.
            </p>
          </div>

          {/* Quality Checklist */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider font-mono">
              Server-Enforced Quality Checklist
            </span>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              {qualityChecks.map((qc, idx) => (
                <div
                  key={idx}
                  className={`p-2.5 rounded-lg border flex items-center gap-2 font-medium ${
                    qc.passed
                      ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
                      : 'bg-rose-50/80 border-rose-200 text-rose-800'
                  }`}
                >
                  {qc.passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  )}
                  <span>{qc.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Candidate Preview Trigger */}
          <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/50 flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-0.5">
              <span className="text-xs font-bold text-blue-900 flex items-center gap-1.5">
                <Eye className="w-4 h-4 text-blue-600" />
                Candidate Perspective Preview
              </span>
              <p className="text-xs text-blue-800">
                View this question as a student in an active test room. Hidden test cases and admin notes are strictly omitted.
              </p>
            </div>
            {initialData?.question ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setIsPreviewOpen(true)}
                className="bg-white hover:bg-slate-50 text-blue-700 border-blue-200 font-semibold"
              >
                <Eye className="w-3.5 h-3.5 mr-1" />
                Preview as Candidate
              </Button>
            ) : (
              <span className="text-xs text-blue-700 font-mono italic">
                (Save as Draft first to generate candidate preview)
              </span>
            )}
          </div>
        </Card>
      )}

      {/* Footer Workflow Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2">
          {currentStep > 1 && (
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => setCurrentStep((s) => Math.max(1, s - 1))}
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              Previous Step
            </Button>
          )}
          {currentStep < 6 && (
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => setCurrentStep((s) => Math.min(6, s + 1))}
            >
              Next Step
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={handleSaveDraftClick}
            disabled={isSaving || isLocked}
            className="font-semibold"
          >
            {isSaving ? 'Saving Draft...' : 'Save as Draft'}
          </Button>

          {!isLocked && (
            <Button
              type="button"
              variant="primary"
              size="md"
              onClick={handlePublishClick}
              disabled={isPublishing || !allQualityChecksPassed}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold"
              title={!allQualityChecksPassed ? 'Complete all quality checks to publish' : ''}
            >
              <Sparkles className="w-4 h-4 mr-1.5" />
              {isPublishing ? 'Publishing...' : 'Publish Question (Lock Immutability)'}
            </Button>
          )}
        </div>
      </div>

      {/* Candidate Preview Modal */}
      {initialData?.question && (
        <QuestionPreviewModal
          questionId={initialData.question}
          versionNumber={versionNumber}
          isOpen={isPreviewOpen}
          onClose={() => setIsPreviewOpen(false)}
        />
      )}
    </div>
  );
};
