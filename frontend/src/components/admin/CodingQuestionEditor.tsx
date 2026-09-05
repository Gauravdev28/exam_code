import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import {
  Code2,
  CheckCircle2,
  AlertCircle,
  Play,
  Eye,
  Plus,
  Trash2,
  ArrowLeft,
  Layers,
  FileText,
  Bookmark,
  Check,
  RefreshCw,
  Clock,
  HardDrive,
  Sliders,
  AlertTriangle,
  Terminal,
  ShieldCheck,
  CheckSquare,
  Square,
  Sparkles,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import {
  runSandboxTest,
  RunSandboxResult,
  getQuestionVersionHealth,
  getSupportedLanguages,
} from '../../api/questions';
import {
  CodingLanguage,
  Difficulty,
  TestCase,
  QuestionHealthStatus,
  QuestionHealthCheck,
  SupportedLanguageItem,
} from '../../types/question';

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
  questionId?: string;
  onSaveDraft: (payload: any) => Promise<void>;
  onPublish: (payload: any) => Promise<void>;
  isSaving: boolean;
  isPublishing: boolean;
}

const FALLBACK_LANGUAGES: SupportedLanguageItem[] = [
  {
    key: 'PYTHON',
    label: 'Python 3.10',
    monaco_lang: 'python',
    judge0_id: 71,
    default_starter_code: `# Write your solution below\ndef solve():\n    import sys\n    input_data = sys.stdin.read().split()\n    if not input_data:\n        return\n    print(input_data[0])\n\nif __name__ == '__main__':\n    solve()\n`,
  },
  {
    key: 'CPP',
    label: 'C++ (GCC 11.2)',
    monaco_lang: 'cpp',
    judge0_id: 54,
    default_starter_code: `#include <iostream>\n#include <vector>\n#include <string>\n\nusing namespace std;\n\nint main() {\n    ios_base::sync_with_stdio(false);\n    cin.tie(NULL);\n    string s;\n    if (cin >> s) {\n        cout << s << "\\n";\n    }\n    return 0;\n}\n`,
  },
  {
    key: 'JAVA',
    label: 'Java (OpenJDK 17)',
    monaco_lang: 'java',
    judge0_id: 62,
    default_starter_code: `import java.util.Scanner;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in);\n        if (scanner.hasNext()) {\n            String input = scanner.next();\n            System.out.println(input);\n        }\n    }\n}\n`,
  },
];

async function sha256Hex(text: string): Promise<string> {
  try {
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  } catch {
    return String(text.length);
  }
}

export const CodingQuestionEditor: React.FC<CodingQuestionEditorProps> = ({
  initialData,
  isLocked = false,
  versionNumber = 1,
  questionId,
  onSaveDraft,
  onPublish,
  isSaving,
  isPublishing,
}) => {
  const navigate = useNavigate();

  // Dynamic Languages Registry
  const [supportedLanguages, setSupportedLanguages] = useState<SupportedLanguageItem[]>(FALLBACK_LANGUAGES);

  // Section A: Basic Information
  const [title, setTitle] = useState(initialData?.title || '');
  const [difficulty, setDifficulty] = useState<Difficulty>(initialData?.difficulty || 'MEDIUM');
  const [points, setPoints] = useState<number>(initialData?.points || 10);
  const [negativeMarkingEnabled, setNegativeMarkingEnabled] = useState(
    initialData?.negative_marking_enabled || false
  );
  const [negativePoints, setNegativePoints] = useState<number>(initialData?.negative_points || 0);
  const [tagsInput, setTagsInput] = useState(
    initialData?.tags?.map((t: any) => t.name || t).join(', ') || ''
  );

  // Section B: Problem Statement
  const [description, setDescription] = useState(
    initialData?.coding_config?.problem_statement || initialData?.description || ''
  );
  const [constraints, setConstraints] = useState(initialData?.coding_config?.constraints || '');
  const [inputFormat, setInputFormat] = useState(initialData?.coding_config?.input_format || '');
  const [outputFormat, setOutputFormat] = useState(initialData?.coding_config?.output_format || '');
  const [instructions, setInstructions] = useState(initialData?.instructions || '');
  const [adminNotes, setAdminNotes] = useState(
    initialData?.coding_config?.admin_notes || initialData?.type_config?.admin_notes || ''
  );

  // Section C: Examples
  const [examples, setExamples] = useState<ExampleItem[]>(() => {
    if (initialData?.coding_config?.examples && Array.isArray(initialData.coding_config.examples) && initialData.coding_config.examples.length > 0) {
      return initialData.coding_config.examples.map((ex: any, idx: number) => ({
        id: `ex-${idx}-${Date.now()}`,
        name: ex.name || `Example ${idx + 1}`,
        input: ex.input || '',
        output: ex.output || '',
        explanation: ex.explanation || '',
      }));
    }
    const sampleTcs = initialData?.coding_config?.test_cases?.filter((t: any) => !t.is_hidden) || [];
    if (sampleTcs.length > 0) {
      return sampleTcs.map((t: any, idx: number) => ({
        id: `ex-${idx}-${Date.now()}`,
        name: t.name || `Example ${idx + 1}`,
        input: t.input_data || '',
        output: t.expected_output || '',
        explanation: t.explanation || '',
      }));
    }
    return [
      {
        id: 'ex-1',
        name: 'Example 1',
        input: '4 5\n1 2 3 4',
        output: '10',
        explanation: 'The sum of the array elements is 10.',
      },
    ];
  });

  // Section D: Languages & Starter Code
  const [allowedLanguages, setAllowedLanguages] = useState<CodingLanguage[]>(
    initialData?.coding_config?.allowed_languages || ['PYTHON', 'CPP', 'JAVA']
  );
  const [activeCodeTab, setActiveCodeTab] = useState<string>('PYTHON');
  const [starterCodeMap, setStarterCodeMap] = useState<Record<string, string>>(() => {
    const existing = initialData?.coding_config?.starter_codes || {};
    if (initialData?.coding_config?.starter_code) {
      existing.PYTHON = initialData.coding_config.starter_code;
    }
    FALLBACK_LANGUAGES.forEach((l) => {
      if (!existing[l.key]) {
        existing[l.key] = l.default_starter_code;
      }
    });
    return existing;
  });
  const [timeLimitMs, setTimeLimitMs] = useState<number>(
    initialData?.coding_config?.time_limit_ms || 2000
  );
  const [memoryLimitMb, setMemoryLimitMb] = useState<number>(
    initialData?.coding_config?.memory_limit_mb || 256
  );

  // Section E: Test Cases
  const [testCases, setTestCases] = useState<TestCase[]>(() => {
    if (initialData?.coding_config?.test_cases && initialData.coding_config.test_cases.length > 0) {
      return initialData.coding_config.test_cases.map((tc: any, idx: number) => ({
        id: tc.id,
        name: tc.name || (tc.is_hidden ? `Hidden Test #${idx + 1}` : `Sample Test #${idx + 1}`),
        input_data: tc.input_data || '',
        expected_output: tc.expected_output || '',
        difficulty: tc.difficulty || 'MEDIUM',
        points: Number(tc.points) || 5,
        is_hidden: Boolean(tc.is_hidden),
        is_verified: Boolean(tc.is_verified),
        execution_order: tc.execution_order || idx + 1,
      }));
    }
    return [
      {
        name: 'Sample Test #1 (Basic)',
        input_data: '4 5\n1 2 3 4',
        expected_output: '10',
        difficulty: 'EASY',
        points: 5,
        is_hidden: false,
        is_verified: true,
        execution_order: 1,
      },
      {
        name: 'Hidden Test #1 (Edge Case)',
        input_data: '1 1\n0',
        expected_output: '0',
        difficulty: 'MEDIUM',
        points: 5,
        is_hidden: true,
        is_verified: false,
        execution_order: 2,
      },
    ];
  });

  // Section F: Expected Output Verification & Reference Solutions
  const [referenceSolutions, setReferenceSolutions] = useState<Record<string, string>>(() => {
    return initialData?.coding_config?.reference_solutions || {
      PYTHON: `# Reference Solution\ndef solve():\n    import sys\n    lines = sys.stdin.read().split()\n    if not lines:\n        return\n    nums = [int(x) for x in lines[2:]]\n    print(sum(nums))\n\nif __name__ == '__main__':\n    solve()\n`,
    };
  });
  const [refSolutionLang, setRefSolutionLang] = useState<string>(
    initialData?.coding_config?.reference_solution_language || 'PYTHON'
  );
  const [refSolutionVerified, setRefSolutionVerified] = useState<boolean>(
    initialData?.coding_config?.reference_solution_verified || false
  );
  const [refSolutionVerifiedAt, setRefSolutionVerifiedAt] = useState<string | null>(
    initialData?.coding_config?.reference_solution_verified_at || null
  );
  const [verifiedHash, setVerifiedHash] = useState<string>(
    initialData?.coding_config?.reference_solution_hash || ''
  );
  const [currentHash, setCurrentHash] = useState<string>('');
  const [isRefRunningAll, setIsRefRunningAll] = useState<boolean>(false);

  // Section G: Sandbox Verification
  const [sandboxCode, setSandboxCode] = useState<string>(() => {
    return (
      referenceSolutions[refSolutionLang] ||
      starterCodeMap[refSolutionLang] ||
      starterCodeMap.PYTHON ||
      ''
    );
  });
  const [sandboxLang, setSandboxLang] = useState<CodingLanguage>('PYTHON');
  const [sandboxStdin, setSandboxStdin] = useState<string>('4 5\n1 2 3 4');
  const [sandboxExpected, setSandboxExpected] = useState<string>('10');
  const [sandboxLoading, setSandboxLoading] = useState<boolean>(false);
  const [sandboxResult, setSandboxResult] = useState<RunSandboxResult | null>(null);
  const [runAllLoading, setRunAllLoading] = useState<boolean>(false);
  const [bulkRunResults, setBulkRunResults] = useState<{ [index: number]: RunSandboxResult }>({});

  // Question Health & Publish UX
  const [backendHealth, setBackendHealth] = useState<QuestionHealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(false);
  const [candidatePreviewOpen, setCandidatePreviewOpen] = useState<boolean>(false);

  // Load Supported Languages
  useEffect(() => {
    const fetchLangs = async () => {
      try {
        const res: any = await getSupportedLanguages();
        const langs = res?.data?.languages || res?.languages;
        if (langs && Array.isArray(langs) && langs.length > 0) {
          setSupportedLanguages(langs);
        }
      } catch {
        // keep fallback
      }
    };
    fetchLangs();
  }, []);

  // Compute Current Reference Solution Hash
  useEffect(() => {
    const compute = async () => {
      const code = referenceSolutions[refSolutionLang] || '';
      const text = `${code.trim()}:${refSolutionLang}`;
      const hash = await sha256Hex(text);
      setCurrentHash(hash);
    };
    compute();
  }, [referenceSolutions, refSolutionLang]);

  // Is reference solution stale?
  const isReferenceStale = useMemo(() => {
    if (!refSolutionVerified) return false;
    if (!verifiedHash) return true;
    return verifiedHash !== currentHash;
  }, [refSolutionVerified, verifiedHash, currentHash]);

  // Duplicate Inputs Check (Phase 6 normalization)
  const duplicateInputs = useMemo(() => {
    const map = new Map<string, number[]>();
    testCases.forEach((tc, idx) => {
      const norm = (tc.input_data || '').trim().replace(/\r\n/g, '\n').replace(/\s+/g, ' ');
      if (!norm) return;
      if (!map.has(norm)) map.set(norm, []);
      map.get(norm)!.push(idx + 1);
    });
    const dupes: string[] = [];
    map.forEach((indices) => {
      if (indices.length > 1) {
        dupes.push(`Test cases #${indices.join(' and #')} have identical normalized inputs.`);
      }
    });
    return dupes;
  }, [testCases]);

  // Points Sum Validation
  const totalTestCasePoints = useMemo(
    () => testCases.reduce((sum, tc) => sum + (Number(tc.points) || 0), 0),
    [testCases]
  );
  const isPointSumValid = totalTestCasePoints === points;

  // Fetch Authoritative Backend Health
  const loadBackendHealth = useCallback(async () => {
    const effectiveQId = questionId || initialData?.question;
    if (!effectiveQId || !versionNumber) return;
    setHealthLoading(true);
    try {
      const res: any = await getQuestionVersionHealth(effectiveQId, versionNumber);
      const healthData = res?.data || res;
      if (healthData?.checks) {
        setBackendHealth(healthData);
      }
    } catch {
      // ignore
    } finally {
      setHealthLoading(false);
    }
  }, [questionId, initialData?.question, versionNumber]);

  useEffect(() => {
    loadBackendHealth();
  }, [loadBackendHealth]);

  // Client-side dynamic preview of health checks for real-time authoring feedback
  const localHealthChecks: QuestionHealthCheck[] = useMemo(() => {
    const sampleCount = testCases.filter((t) => !t.is_hidden).length;
    const hiddenCount = testCases.filter((t) => t.is_hidden).length;
    const unverifiedCount = testCases.filter((t) => !t.is_verified).length;
    const missingOutputs = testCases.filter((t) => !t.expected_output || !t.expected_output.trim()).length;
    const missingStarter = allowedLanguages.some((l) => !starterCodeMap[l] || !starterCodeMap[l].trim());

    return [
      {
        key: 'problem_statement',
        display_name: 'Problem Statement',
        passed: Boolean(title.trim() && description.trim()),
        message:
          title.trim() && description.trim()
            ? 'Problem statement and title complete'
            : 'Title and problem statement must not be empty',
      },
      {
        key: 'examples',
        display_name: 'Examples',
        passed: examples.length > 0 && examples.every((ex) => ex.input.trim() && ex.output.trim()),
        message:
          examples.length > 0 && examples.every((ex) => ex.input.trim() && ex.output.trim())
            ? `${examples.length} candidate-facing example(s) configured`
            : 'At least one example with input and output is required',
      },
      {
        key: 'languages',
        display_name: 'Languages Registry',
        passed: allowedLanguages.length > 0,
        message:
          allowedLanguages.length > 0
            ? `${allowedLanguages.length} language(s) enabled: ${allowedLanguages.join(', ')}`
            : 'Select at least one supported programming language',
      },
      {
        key: 'starter_code',
        display_name: 'Starter Code',
        passed: !missingStarter,
        message: !missingStarter
          ? 'Starter code provided for all enabled languages'
          : 'Starter code missing for one or more enabled languages',
      },
      {
        key: 'sample_tests',
        display_name: 'Sample Tests',
        passed: sampleCount >= 1,
        message:
          sampleCount >= 1
            ? `${sampleCount} sample test case(s) configured`
            : 'At least one public/sample test case required',
      },
      {
        key: 'hidden_tests',
        display_name: 'Hidden Tests',
        passed: hiddenCount >= 1,
        message:
          hiddenCount >= 1
            ? `${hiddenCount} hidden test case(s) configured`
            : 'At least one hidden grading test case required',
      },
      {
        key: 'expected_output_verification',
        display_name: 'Expected Output Verification',
        passed: !isReferenceStale && unverifiedCount === 0 && testCases.length > 0,
        message: isReferenceStale
          ? 'Reference solution verification is stale; re-run reference solution'
          : unverifiedCount > 0
          ? `${unverifiedCount} test case(s) are unverified`
          : 'All expected outputs explicitly verified',
      },
      {
        key: 'expected_outputs',
        display_name: 'Expected Outputs',
        passed: missingOutputs === 0 && testCases.length > 0,
        message:
          missingOutputs === 0 && testCases.length > 0
            ? 'All test cases have non-empty expected outputs'
            : `${missingOutputs} test case(s) missing expected outputs`,
      },
      {
        key: 'judge0_execution',
        display_name: 'Judge0 Sandbox Boundary',
        passed: true,
        message: 'Authoritative Judge0 CE + Isolate sandbox configured',
      },
      {
        key: 'scoring_configuration',
        display_name: 'Scoring Configuration',
        passed: testCases.length > 0 && testCases.every((t) => Number(t.points) >= 1),
        message:
          testCases.length > 0 && testCases.every((t) => Number(t.points) >= 1)
            ? 'Positive point allocations configured'
            : 'All test cases must have at least 1 point',
      },
      {
        key: 'point_sum_invariant',
        display_name: 'Point Sum Invariant',
        passed: isPointSumValid,
        message: isPointSumValid
          ? `Test case points sum (${totalTestCasePoints}) matches question points (${points})`
          : `Test case points (${totalTestCasePoints}) do not equal question points (${points})`,
      },
      {
        key: 'duplicate_inputs',
        display_name: 'Duplicate Inputs',
        passed: duplicateInputs.length === 0,
        message:
          duplicateInputs.length === 0
            ? 'No duplicate normalized inputs'
            : duplicateInputs[0],
      },
    ];
  }, [
    title,
    description,
    examples,
    allowedLanguages,
    starterCodeMap,
    testCases,
    isReferenceStale,
    isPointSumValid,
    duplicateInputs,
    totalTestCasePoints,
    points,
  ]);

  // Use authoritative backend checks if available, otherwise local checks
  const displayChecks = backendHealth?.checks?.length ? backendHealth.checks : localHealthChecks;
  const passedChecksCount = displayChecks.filter((c) => c.passed).length;
  const isHealthReady = passedChecksCount === displayChecks.length && !isReferenceStale;
  const blockingIssues = displayChecks.filter((c) => !c.passed);

  // Assemble full payload for saving / publishing
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
        starter_code: starterCodeMap[activeCodeTab] || starterCodeMap.PYTHON || '',
        starter_codes: starterCodeMap,
        examples: examples.map((ex) => ({
          name: ex.name,
          input: ex.input,
          output: ex.output,
          explanation: ex.explanation,
        })),
        time_limit_ms: timeLimitMs,
        memory_limit_mb: memoryLimitMb,
        reference_solutions: referenceSolutions,
        reference_solution_language: refSolutionLang,
        reference_solution_verified: refSolutionVerified && !isReferenceStale,
        reference_solution_hash: refSolutionVerified && !isReferenceStale ? verifiedHash : '',
        reference_solution_verified_at: refSolutionVerifiedAt,
      },
      test_cases: testCases.map((tc, idx) => ({
        id: tc.id,
        name: tc.name || (tc.is_hidden ? `Hidden Test #${idx + 1}` : `Sample Test #${idx + 1}`),
        input_data: tc.input_data,
        expected_output: tc.expected_output,
        difficulty: tc.difficulty || 'MEDIUM',
        points: Number(tc.points) || 0,
        is_hidden: Boolean(tc.is_hidden),
        is_verified: Boolean(tc.is_verified),
        execution_order: idx + 1,
      })),
    };
  };

  const handleSaveDraft = async () => {
    const payload = assemblePayload();
    await onSaveDraft(payload);
    await loadBackendHealth();
  };

  const handlePublish = async () => {
    if (!isHealthReady) {
      alert(`Publishing is blocked. Please resolve the ${blockingIssues.length} issues identified in Question Health.`);
      return;
    }
    const payload = assemblePayload();
    await onPublish(payload);
    await loadBackendHealth();
  };

  // Examples Management
  const handleAddExample = () => {
    const newEx: ExampleItem = {
      id: `ex-${Date.now()}`,
      name: `Example ${examples.length + 1}`,
      input: '',
      output: '',
      explanation: '',
    };
    setExamples([...examples, newEx]);
  };

  const handleDeleteExample = (id: string) => {
    setExamples(examples.filter((e) => e.id !== id));
  };

  const handleSyncExamplesToTestCases = () => {
    const sampleTcs: TestCase[] = examples.map((ex, idx) => ({
      name: ex.name,
      input_data: ex.input,
      expected_output: ex.output,
      difficulty: 'EASY',
      points: Math.max(1, Math.floor(points / (examples.length + 1))),
      is_hidden: false,
      is_verified: true,
      execution_order: idx + 1,
    }));
    const hiddenTcs = testCases.filter((t) => t.is_hidden);
    if (hiddenTcs.length === 0) {
      hiddenTcs.push({
        name: 'Hidden Test #1',
        input_data: '',
        expected_output: '',
        difficulty: 'MEDIUM',
        points: Math.max(1, points - sampleTcs.reduce((s, c) => s + c.points, 0)),
        is_hidden: true,
        is_verified: false,
        execution_order: sampleTcs.length + 1,
      });
    }
    setTestCases([...sampleTcs, ...hiddenTcs]);
  };

  // Language Selection
  const toggleLanguage = (langKey: CodingLanguage) => {
    if (allowedLanguages.includes(langKey)) {
      if (allowedLanguages.length <= 1) {
        alert('At least one language must remain enabled.');
        return;
      }
      const next = allowedLanguages.filter((l) => l !== langKey);
      setAllowedLanguages(next);
      if (activeCodeTab === langKey) {
        setActiveCodeTab(next[0]);
      }
    } else {
      setAllowedLanguages([...allowedLanguages, langKey]);
    }
  };

  const handleSelectAllLanguages = () => {
    const all = supportedLanguages.map((l) => l.key as CodingLanguage);
    setAllowedLanguages(all);
  };

  const handleClearAllLanguages = () => {
    if (supportedLanguages.length > 0) {
      setAllowedLanguages([supportedLanguages[0].key as CodingLanguage]);
      setActiveCodeTab(supportedLanguages[0].key);
    }
  };

  // Test Case Management
  const handleAddTestCase = (isHidden = false) => {
    const newTc: TestCase = {
      name: isHidden ? `Hidden Test #${testCases.length + 1}` : `Sample Test #${testCases.length + 1}`,
      input_data: '',
      expected_output: '',
      difficulty: 'MEDIUM',
      points: Math.max(1, Math.floor(points / (testCases.length + 1))),
      is_hidden: isHidden,
      is_verified: false,
      execution_order: testCases.length + 1,
    };
    setTestCases([...testCases, newTc]);
  };

  const handleDeleteTestCase = (idx: number) => {
    setTestCases(testCases.filter((_, i) => i !== idx));
  };

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

  // Model A: Run Reference Solution on All Test Cases via Judge0
  const handleRunReferenceSolutionOnAllTests = async () => {
    const code = referenceSolutions[refSolutionLang] || '';
    if (!code.trim()) {
      alert(`Please provide reference solution code for ${refSolutionLang}.`);
      return;
    }
    if (testCases.length === 0) {
      alert('Please configure at least one test case.');
      return;
    }

    setIsRefRunningAll(true);
    const updatedTestCases = [...testCases];
    let allSucceeded = true;

    for (let i = 0; i < updatedTestCases.length; i++) {
      const tc = updatedTestCases[i];
      try {
        const res = await runSandboxTest({
          source_code: code,
          language: refSolutionLang as CodingLanguage,
          stdin: tc.input_data,
          expected_output: tc.expected_output || '',
          cpu_time_limit_ms: timeLimitMs,
          memory_limit_mb: memoryLimitMb,
        });

        if (res.data && res.data.stdout !== null && (res.data.status_id === 3 || res.data.passed || res.data.stdout.length > 0)) {
          updatedTestCases[i] = {
            ...tc,
            expected_output: res.data.stdout.trim(),
            is_verified: true,
          };
        } else {
          allSucceeded = false;
        }
      } catch {
        allSucceeded = false;
      }
    }

    setTestCases(updatedTestCases);
    setIsRefRunningAll(false);

    if (allSucceeded) {
      const hash = await sha256Hex(`${code.trim()}:${refSolutionLang}`);
      setVerifiedHash(hash);
      setRefSolutionVerified(true);
      setRefSolutionVerifiedAt(new Date().toISOString());
      alert('Reference solution executed successfully on all test cases! Outputs populated and verified.');
    } else {
      alert('Some test cases failed during execution. Please inspect individual results.');
    }
  };

  // Model B: Mark all test cases verified
  const handleMarkAllVerified = () => {
    setTestCases(
      testCases.map((tc) => ({
        ...tc,
        is_verified: true,
      }))
    );
    if (referenceSolutions[refSolutionLang]?.trim()) {
      setRefSolutionVerified(true);
      setRefSolutionVerifiedAt(new Date().toISOString());
      setVerifiedHash(currentHash);
    }
  };

  // Sandbox Test Execution
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
        status_description: err.error?.message || 'Sandbox execution failed.',
        stdout: null,
        stderr: err.message || 'Error communicating with execution boundary.',
        compile_output: null,
        time: 0,
        memory: 0,
        passed: false,
      });
    } finally {
      setSandboxLoading(false);
    }
  };

  const handleRunAllSandboxTests = async () => {
    setRunAllLoading(true);
    setBulkRunResults({});
    const results: { [index: number]: RunSandboxResult } = {};

    for (let i = 0; i < testCases.length; i++) {
      const tc = testCases[i];
      try {
        const res = await runSandboxTest({
          source_code: sandboxCode,
          language: sandboxLang,
          stdin: tc.input_data,
          expected_output: tc.expected_output,
          cpu_time_limit_ms: timeLimitMs,
          memory_limit_mb: memoryLimitMb,
        });
        if (res.data) {
          results[i] = res.data;
        }
      } catch (err: any) {
        results[i] = {
          status_id: 13,
          status_description: err.message || 'Execution error',
          stdout: null,
          stderr: 'Execution failed',
          compile_output: null,
          time: 0,
          memory: 0,
          passed: false,
        };
      }
    }
    setBulkRunResults(results);
    setRunAllLoading(false);
  };

  // Monaco Language Helpers
  const getMonacoLang = (key: string) => {
    const found = supportedLanguages.find((l) => l.key === key);
    return found?.monaco_lang || 'plaintext';
  };

  return (
    <div className="space-y-6 pb-24">
      {/* Sticky Top Header */}
      <div className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-sm py-3.5 px-4 -mx-4 sm:-mx-6 rounded-b-2xl">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate('/admin/questions')}
              className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors p-1.5 rounded-lg hover:bg-slate-100"
              title="Return to Question Bank"
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </button>
            <div className="h-4 w-px bg-slate-200" />
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-slate-900 tracking-tight">
                  {title.trim() || 'Untitled Coding Question'}
                </h1>
                <Badge variant={isLocked ? 'neutral' : 'warning'}>
                  {isLocked ? `PUBLISHED v${versionNumber}` : `DRAFT v${versionNumber}`}
                </Badge>
              </div>
              <p className="text-[11px] text-slate-500 font-mono">
                Single-Page Coding Workspace • Phase 6 Judge0 Sandbox Boundary
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Health Pill */}
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-mono font-bold ${
                isHealthReady
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                  : 'bg-amber-50 text-amber-800 border-amber-300'
              }`}
            >
              {isHealthReady ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              )}
              <span>
                {isHealthReady
                  ? 'Ready to Publish'
                  : `${blockingIssues.length} issue${blockingIssues.length > 1 ? 's' : ''} blocked`}
              </span>
            </div>

            {/* Candidate Preview */}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCandidatePreviewOpen(true)}
              className="bg-white border-slate-300 text-slate-700 font-semibold shadow-xs hover:bg-slate-50"
            >
              <Eye className="w-3.5 h-3.5 mr-1.5 text-blue-600" />
              Candidate Preview
            </Button>

            {/* Save Draft */}
            <Button
              variant="secondary"
              size="sm"
              disabled={isSaving || isLocked}
              onClick={handleSaveDraft}
              className="bg-white border-slate-300 text-slate-800 font-bold shadow-xs hover:bg-slate-50"
            >
              {isSaving ? (
                <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin text-emerald-600" />
              ) : (
                <Check className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
              )}
              {isSaving ? 'Saving...' : 'Save Draft'}
            </Button>

            {/* Publish Button */}
            <div className="relative group">
              <Button
                variant={isHealthReady ? 'primary' : 'secondary'}
                size="sm"
                disabled={isPublishing || isLocked || !isHealthReady}
                onClick={handlePublish}
                className={
                  isHealthReady
                    ? 'font-bold shadow-sm'
                    : 'opacity-60 cursor-not-allowed bg-slate-100 border-slate-300 text-slate-500 font-bold'
                }
              >
                {isPublishing ? (
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                )}
                {isPublishing ? 'Publishing...' : 'Publish Question'}
              </Button>

              {!isHealthReady && (
                <div className="absolute right-0 top-full mt-2 w-72 p-3 bg-slate-900 text-white text-xs rounded-xl shadow-xl z-50 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity space-y-1.5 font-sans">
                  <div className="font-bold text-amber-400 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Publishing Blocked
                  </div>
                  <p className="text-[11px] text-slate-300">
                    Fix the following issues before publishing:
                  </p>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-slate-200">
                    {blockingIssues.slice(0, 4).map((b, i) => (
                      <li key={i}>{b.message}</li>
                    ))}
                    {blockingIssues.length > 4 && (
                      <li className="text-slate-400">+{blockingIssues.length - 4} more...</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Anchored Section Jump Bar */}
        <div className="max-w-7xl mx-auto flex items-center gap-1 mt-2.5 pt-2 border-t border-slate-100 overflow-x-auto text-[11px] font-mono scrollbar-none">
          {[
            { id: 'section-basic', label: 'Basic Info' },
            { id: 'section-problem', label: 'Problem' },
            { id: 'section-examples', label: 'Examples' },
            { id: 'section-languages', label: 'Languages & Starter Code' },
            { id: 'section-tests', label: `Test Cases (${testCases.length})` },
            { id: 'section-verification', label: 'Expected Output Verification' },
            { id: 'section-sandbox', label: 'Sandbox Execution' },
            { id: 'section-health', label: `Health (${passedChecksCount}/${displayChecks.length})` },
          ].map((sec) => (
            <a
              key={sec.id}
              href={`#${sec.id}`}
              className="px-2.5 py-1 rounded-lg text-slate-600 hover:text-emerald-700 hover:bg-emerald-50/60 font-semibold whitespace-nowrap transition-colors"
            >
              {sec.label}
            </a>
          ))}
        </div>
      </div>

      {/* Staleness Banner if applicable */}
      {isReferenceStale && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-3 shadow-xs">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <h4 className="font-bold text-amber-800">
              Reference Solution Stale — Reverification Required
            </h4>
            <p className="text-amber-700 leading-relaxed">
              The reference solution code or language has changed since it was last verified.
              Phase 6 immutability requires re-running the reference solution against test cases
              before publishing.
            </p>
            <div className="pt-1">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRunReferenceSolutionOnAllTests}
                disabled={isRefRunningAll}
                className="bg-amber-600 text-white hover:bg-amber-700 border-amber-600 text-xs font-bold"
              >
                {isRefRunningAll ? 'Re-verifying...' : 'Re-verify Reference Solution Now'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* SECTION A — BASIC INFORMATION */}
      <section id="section-basic">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section A: Basic Information
                </h3>
                <p className="text-xs text-slate-500">Core assessment metadata, scoring, and classification</p>
              </div>
            </div>
            <span className="text-[11px] font-mono text-slate-500">Authoring Model A & B</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Question Title */}
            <div className="md:col-span-2 space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">
                Question Title <span className="text-rose-600">*</span>
              </label>
              <input
                type="text"
                disabled={isLocked}
                placeholder="e.g. Subarray Sum Equals K"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs font-medium focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {/* Difficulty */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Difficulty</label>
              <select
                disabled={isLocked}
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs font-medium focus:ring-2 focus:ring-emerald-500"
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
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-emerald-700 font-bold text-xs focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          {/* Negative Marking & Tags */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="flex flex-wrap items-center gap-4 p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
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
                  <span className="text-slate-600 font-semibold">Penalty:</span>
                  <input
                    type="number"
                    min={0}
                    max={points}
                    disabled={isLocked}
                    value={negativePoints}
                    onChange={(e) =>
                      setNegativePoints(Math.max(0, parseInt(e.target.value, 10) || 0))
                    }
                    className="w-16 px-2 py-1 rounded-lg bg-white border border-slate-300 text-rose-600 font-bold focus:ring-2 focus:ring-emerald-500"
                  />
                  <span className="text-slate-500">pts</span>
                </div>
              )}
            </div>

            {/* Tags */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">
                Tags (Comma-separated)
              </label>
              <input
                type="text"
                disabled={isLocked}
                placeholder="arrays, hash-table, prefix-sum"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>
        </Card>
      </section>

      {/* SECTION B — PROBLEM STATEMENT */}
      <section id="section-problem">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-blue-50 text-blue-700 border border-blue-200">
                <Bookmark className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section B: Problem Statement & Formats
                </h3>
                <p className="text-xs text-slate-500">
                  Student-facing markdown problem description, constraints, and standard I/O formats
                </p>
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCandidatePreviewOpen(true)}
              className="text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border-blue-200"
            >
              <Eye className="w-3.5 h-3.5 mr-1" />
              Candidate Preview
            </Button>
          </div>

          {/* Problem Statement */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700">
              Problem Statement (Markdown supported) <span className="text-rose-600">*</span>
            </label>
            <textarea
              rows={6}
              disabled={isLocked}
              placeholder="Given an array of integers nums and an integer k, return the total number of subarrays whose sum equals to k..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs font-sans leading-relaxed focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Constraints */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Constraints</label>
              <textarea
                rows={3}
                disabled={isLocked}
                placeholder="1 <= nums.length <= 2 * 10^4&#10;-1000 <= nums[i] <= 1000&#10;-10^7 <= k <= 10^7"
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {/* Input Format */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Input Format</label>
              <textarea
                rows={3}
                disabled={isLocked}
                placeholder="First line contains n and k. Second line contains n space-separated integers."
                value={inputFormat}
                onChange={(e) => setInputFormat(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {/* Output Format */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Output Format</label>
              <textarea
                rows={3}
                disabled={isLocked}
                placeholder="Print a single integer representing the count of valid subarrays."
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          {/* Instructions & Admin Notes */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Special Instructions (Candidate Visible)</label>
              <textarea
                rows={2}
                disabled={isLocked}
                placeholder="e.g. Read input from standard input (stdin) and print output to standard output (stdout)."
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">Internal Admin Notes (Private)</label>
              <textarea
                rows={2}
                disabled={isLocked}
                placeholder="e.g. Reference solution time complexity is O(N), memory is O(N). Problem adapted from verified bank."
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>
        </Card>
      </section>

      {/* SECTION C — EXAMPLES */}
      <section id="section-examples">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-purple-50 text-purple-700 border border-purple-200">
                <Bookmark className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section C: Examples (Candidate Visible)
                </h3>
                <p className="text-xs text-slate-500">
                  Multiple examples with inputs, outputs, and optional explanations for students
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleSyncExamplesToTestCases}
                title="Populate test cases from these examples"
                className="text-xs text-purple-700 bg-purple-50 border-purple-200 hover:bg-purple-100"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
                Sync to Sample Test Cases
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleAddExample}
                disabled={isLocked}
                className="text-xs font-semibold text-emerald-700 bg-emerald-50 border-emerald-200 hover:bg-emerald-100"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                Add Example
              </Button>
            </div>
          </div>

          <div className="space-y-4">
            {examples.map((ex, idx) => (
              <div
                key={ex.id}
                className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-md bg-purple-100 text-purple-800 font-mono font-bold text-xs border border-purple-200">
                      #{idx + 1}
                    </span>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={ex.name}
                      onChange={(e) => {
                        const updated = [...examples];
                        updated[idx].name = e.target.value;
                        setExamples(updated);
                      }}
                      className="px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-xs font-bold text-slate-800"
                    />
                  </div>
                  {examples.length > 1 && (
                    <button
                      type="button"
                      disabled={isLocked}
                      onClick={() => handleDeleteExample(ex.id)}
                      className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-white"
                      title="Delete Example"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600 font-mono">Input</label>
                    <textarea
                      rows={2}
                      disabled={isLocked}
                      value={ex.input}
                      onChange={(e) => {
                        const updated = [...examples];
                        updated[idx].input = e.target.value;
                        setExamples(updated);
                      }}
                      placeholder="e.g. 2 7 11 15\n9"
                      className="w-full p-2.5 rounded-xl bg-white border border-slate-300 text-xs font-mono text-slate-900"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-600 font-mono">Output</label>
                    <textarea
                      rows={2}
                      disabled={isLocked}
                      value={ex.output}
                      onChange={(e) => {
                        const updated = [...examples];
                        updated[idx].output = e.target.value;
                        setExamples(updated);
                      }}
                      placeholder="e.g. 0 1"
                      className="w-full p-2.5 rounded-xl bg-white border border-slate-300 text-xs font-mono text-slate-900"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-600 font-mono">
                    Explanation (Optional)
                  </label>
                  <input
                    type="text"
                    disabled={isLocked}
                    value={ex.explanation}
                    onChange={(e) => {
                      const updated = [...examples];
                      updated[idx].explanation = e.target.value;
                      setExamples(updated);
                    }}
                    placeholder="e.g. Because nums[0] + nums[1] == 9, we return [0, 1]."
                    className="w-full px-3 py-1.5 rounded-xl bg-white border border-slate-300 text-xs text-slate-800"
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* SECTION D — LANGUAGES & STARTER CODE */}
      <section id="section-languages">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-teal-50 text-teal-700 border border-teal-200">
                <Code2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section D: Languages & Starter Code
                </h3>
                <p className="text-xs text-slate-500">
                  Dynamic backend registry, execution limits, and Monaco Editor starter code templates
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSelectAllLanguages}
                className="text-xs font-mono font-semibold text-teal-700 hover:underline px-2 py-1"
              >
                Select All
              </button>
              <span className="text-slate-300">•</span>
              <button
                type="button"
                onClick={handleClearAllLanguages}
                className="text-xs font-mono font-semibold text-slate-500 hover:underline px-2 py-1"
              >
                Reset
              </button>
            </div>
          </div>

          {/* Enabled Languages Badges */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-slate-700">
              Enabled Programming Languages ({allowedLanguages.length} active)
            </label>
            <div className="flex flex-wrap gap-2.5">
              {supportedLanguages.map((lang) => {
                const isSelected = allowedLanguages.includes(lang.key as CodingLanguage);
                return (
                  <button
                    key={lang.key}
                    type="button"
                    disabled={isLocked}
                    onClick={() => toggleLanguage(lang.key as CodingLanguage)}
                    className={`px-3.5 py-2 rounded-xl border text-xs font-mono font-semibold transition-all flex items-center gap-2 ${
                      isSelected
                        ? 'bg-teal-50 text-teal-900 border-teal-400 shadow-xs'
                        : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {isSelected ? (
                      <CheckSquare className="w-4 h-4 text-teal-600" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-400" />
                    )}
                    <span>{lang.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Limits */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 rounded-2xl bg-slate-50 border border-slate-200 text-xs">
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-slate-700 font-semibold font-mono">
                <Clock className="w-4 h-4 text-amber-600" />
                <span>CPU Execution Time Limit (ms)</span>
              </div>
              <input
                type="number"
                min={100}
                max={15000}
                step={500}
                disabled={isLocked}
                value={timeLimitMs}
                onChange={(e) => setTimeLimitMs(Math.max(100, parseInt(e.target.value, 10) || 1000))}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 font-mono font-bold"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5 text-slate-700 font-semibold font-mono">
                <HardDrive className="w-4 h-4 text-sky-600" />
                <span>Memory Allocation Limit (MB)</span>
              </div>
              <input
                type="number"
                min={16}
                max={1024}
                step={64}
                disabled={isLocked}
                value={memoryLimitMb}
                onChange={(e) => setMemoryLimitMb(Math.max(16, parseInt(e.target.value, 10) || 256))}
                className="w-full px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 font-mono font-bold"
              />
            </div>
          </div>

          {/* Starter Code Monaco Tabs */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-200">
              <div className="flex items-center gap-1">
                {allowedLanguages.map((lKey) => {
                  const isActive = activeCodeTab === lKey;
                  const langItem = supportedLanguages.find((l) => l.key === lKey);
                  return (
                    <button
                      key={lKey}
                      type="button"
                      onClick={() => setActiveCodeTab(lKey)}
                      className={`px-4 py-2 border-b-2 text-xs font-mono font-bold transition-colors ${
                        isActive
                          ? 'border-teal-600 text-teal-800 bg-teal-50/40'
                          : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                      }`}
                    >
                      {langItem?.label || lKey}
                    </button>
                  );
                })}
              </div>

              <span className="text-[11px] font-mono text-slate-500 pr-2">
                Monaco Editor • Starter Boilerplate
              </span>
            </div>

            <div className="rounded-2xl overflow-hidden border border-slate-800 shadow-md">
              <Editor
                height="280px"
                language={getMonacoLang(activeCodeTab)}
                value={starterCodeMap[activeCodeTab] || ''}
                onChange={(val) => {
                  setStarterCodeMap({
                    ...starterCodeMap,
                    [activeCodeTab]: val || '',
                  });
                }}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  scrollBeyondLastLine: false,
                  wordWrap: 'on',
                  lineNumbers: 'on',
                }}
              />
            </div>
          </div>
        </Card>
      </section>

      {/* SECTION E — TEST CASES WORKSPACE */}
      <section id="section-tests">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                <Layers className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section E: Test Cases Management
                </h3>
                <p className="text-xs text-slate-500">
                  Sample & Hidden grading test cases with explicit verification badges
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleAutoBalancePoints}
                className="text-xs font-mono font-semibold text-slate-700 bg-white border-slate-300 hover:bg-slate-50"
              >
                <Sliders className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                Auto-Balance ({totalTestCasePoints}/{points} pts)
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleAddTestCase(false)}
                disabled={isLocked}
                className="text-xs font-semibold text-emerald-800 bg-emerald-50 border-emerald-200 hover:bg-emerald-100"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                + Sample Test
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleAddTestCase(true)}
                disabled={isLocked}
                className="text-xs font-semibold text-slate-800 bg-slate-100 border-slate-300 hover:bg-slate-200"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                + Hidden Test
              </Button>
            </div>
          </div>

          {/* Security Notice */}
          <div className="p-3.5 rounded-xl bg-slate-900 text-slate-200 text-xs flex items-start gap-3 border border-slate-800 shadow-xs">
            <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <strong className="text-white font-mono">Candidate Protection Boundary:</strong>
              <p className="text-slate-300 text-[11px] leading-relaxed">
                Hidden test inputs, outputs, points, and diagnostics are NEVER returned to student
                endpoints. Administrator views retain authorized inspection for auditing.
              </p>
            </div>
          </div>

          {/* Duplicate Inputs Warning */}
          {duplicateInputs.length > 0 && (
            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-800 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold font-mono">Duplicate Input Invariant Notice:</strong>
                <p className="text-[11px] mt-0.5">{duplicateInputs[0]}</p>
              </div>
            </div>
          )}

          {/* Test Cases Table */}
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="px-4 py-3">#</th>
                  <th className="px-4 py-3">Name & Details</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Points</th>
                  <th className="px-4 py-3">Verification State</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-800">
                {testCases.map((tc, idx) => {
                  const isVerified = Boolean(tc.is_verified);
                  const isMissingOutput = !tc.expected_output || !tc.expected_output.trim();

                  return (
                    <tr key={idx} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3 text-slate-400 font-bold">{idx + 1}</td>
                      <td className="px-4 py-3 space-y-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            disabled={isLocked}
                            value={tc.name || ''}
                            onChange={(e) => {
                              const updated = [...testCases];
                              updated[idx].name = e.target.value;
                              setTestCases(updated);
                            }}
                            className="w-full max-w-xs px-2.5 py-1 rounded-lg bg-white border border-slate-300 font-bold text-slate-900 text-xs"
                            placeholder="Test Case Name"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[11px]">
                          <div>
                            <span className="text-slate-400 block mb-0.5 font-semibold">Stdin:</span>
                            <textarea
                              rows={2}
                              disabled={isLocked}
                              value={tc.input_data}
                              onChange={(e) => {
                                const updated = [...testCases];
                                updated[idx].input_data = e.target.value;
                                setTestCases(updated);
                              }}
                              className="w-full p-1.5 rounded bg-slate-50 border border-slate-200 font-mono text-[11px]"
                              placeholder="Input stdin..."
                            />
                          </div>
                          <div>
                            <span className="text-slate-400 block mb-0.5 font-semibold">Expected Stdout:</span>
                            <textarea
                              rows={2}
                              disabled={isLocked}
                              value={tc.expected_output}
                              onChange={(e) => {
                                const updated = [...testCases];
                                updated[idx].expected_output = e.target.value;
                                setTestCases(updated);
                              }}
                              className="w-full p-1.5 rounded bg-slate-50 border border-slate-200 font-mono text-[11px]"
                              placeholder="Expected stdout..."
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          disabled={isLocked}
                          onClick={() => {
                            const updated = [...testCases];
                            updated[idx].is_hidden = !updated[idx].is_hidden;
                            setTestCases(updated);
                          }}
                          className={`px-2 py-1 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider border cursor-pointer ${
                            tc.is_hidden
                              ? 'bg-slate-900 text-slate-100 border-slate-800'
                              : 'bg-emerald-100 text-emerald-800 border-emerald-300'
                          }`}
                        >
                          {tc.is_hidden ? 'HIDDEN' : 'SAMPLE'}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <input
                            type="number"
                            min={1}
                            max={points}
                            disabled={isLocked}
                            value={tc.points}
                            onChange={(e) => {
                              const updated = [...testCases];
                              updated[idx].points = Math.max(1, parseInt(e.target.value, 10) || 1);
                              setTestCases(updated);
                            }}
                            className="w-14 px-2 py-1 rounded-lg bg-white border border-slate-300 font-bold text-emerald-700"
                          />
                          <span className="text-slate-400 text-[10px]">pts</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {isMissingOutput ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 border border-rose-200 text-[10px] font-bold">
                            <AlertCircle className="w-3 h-3" /> Missing Output
                          </span>
                        ) : isReferenceStale ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-bold">
                            <AlertTriangle className="w-3 h-3" /> Stale
                          </span>
                        ) : isVerified ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
                            <CheckCircle2 className="w-3 h-3" /> Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200 text-[10px] font-bold">
                            Unverified
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-1 whitespace-nowrap">
                        <button
                          type="button"
                          disabled={isLocked}
                          onClick={() => {
                            const updated = [...testCases];
                            updated[idx].is_verified = !updated[idx].is_verified;
                            setTestCases(updated);
                          }}
                          className="px-2 py-1 text-[11px] rounded-lg border border-slate-300 hover:bg-slate-100 text-slate-700 font-semibold"
                          title="Toggle verification status"
                        >
                          {tc.is_verified ? 'Unverify' : 'Verify'}
                        </button>
                        {testCases.length > 1 && (
                          <button
                            type="button"
                            disabled={isLocked}
                            onClick={() => handleDeleteTestCase(idx)}
                            className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-slate-100"
                            title="Delete Test Case"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* SECTION F — EXPECTED OUTPUT VERIFICATION */}
      <section id="section-verification">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-amber-50 text-amber-700 border border-amber-200">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section F: Expected Output Verification
                </h3>
                <p className="text-xs text-slate-500">
                  Two approved models: Model A (Reference Solution) or Model B (Manual Verification)
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleMarkAllVerified}
                className="text-xs font-mono font-semibold text-slate-700 bg-white border-slate-300 hover:bg-slate-50"
              >
                <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                Model B: Mark All Verified
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleRunReferenceSolutionOnAllTests}
                disabled={isRefRunningAll || isLocked}
                className="text-xs font-bold font-mono"
              >
                {isRefRunningAll ? (
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                )}
                {isRefRunningAll ? 'Executing...' : 'Model A: Run Reference on All Tests'}
              </Button>
            </div>
          </div>

          {/* Verification Status Banner */}
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-700">Verification Lifecycle:</span>
                <span
                  className={`px-2 py-0.5 rounded-full font-bold uppercase ${
                    isReferenceStale
                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                      : refSolutionVerified
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {isReferenceStale
                    ? 'STALE — Reverification Required'
                    : refSolutionVerified
                    ? 'VERIFIED'
                    : 'UNVERIFIED'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-sans">
                {refSolutionVerifiedAt
                  ? `Last verified: ${new Date(refSolutionVerifiedAt).toLocaleString()}`
                  : 'Outputs must be verified before publishing is unlocked.'}
              </p>
            </div>

            <div className="text-right text-[11px] text-slate-500">
              <span>Ref Solution Hash: </span>
              <code className="bg-slate-200 px-1.5 py-0.5 rounded text-slate-800">
                {currentHash.slice(0, 12)}...
              </code>
            </div>
          </div>

          {/* Reference Solution Monaco Editor */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <label className="text-xs font-semibold text-slate-700 font-mono">
                  Reference Solution Language:
                </label>
                <select
                  value={refSolutionLang}
                  onChange={(e) => setRefSolutionLang(e.target.value)}
                  className="px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-xs font-mono font-bold text-slate-800"
                >
                  {allowedLanguages.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">
                Model A Judge0 Execution Source
              </span>
            </div>

            <div className="rounded-2xl overflow-hidden border border-slate-800 shadow-md">
              <Editor
                height="300px"
                language={getMonacoLang(refSolutionLang)}
                value={referenceSolutions[refSolutionLang] || ''}
                onChange={(val) => {
                  setReferenceSolutions({
                    ...referenceSolutions,
                    [refSolutionLang]: val || '',
                  });
                }}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  scrollBeyondLastLine: false,
                  wordWrap: 'on',
                  lineNumbers: 'on',
                }}
              />
            </div>
          </div>
        </Card>
      </section>

      {/* SECTION G — SANDBOX VERIFICATION */}
      <section id="section-sandbox">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-sky-50 text-sky-700 border border-sky-200">
                <Terminal className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section G: Integrated Sandbox Verification
                </h3>
                <p className="text-xs text-slate-500">
                  Execute code live against the Judge0 CE + Isolate sandbox environment
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRunAllSandboxTests}
                disabled={runAllLoading || sandboxLoading}
                className="text-xs font-mono font-bold text-slate-800 bg-white border-slate-300 hover:bg-slate-50"
              >
                {runAllLoading ? (
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin text-sky-600" />
                ) : (
                  <Play className="w-3.5 h-3.5 mr-1.5 text-sky-600" />
                )}
                {runAllLoading ? 'Running All...' : 'Run All Tests'}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleRunSandbox}
                disabled={sandboxLoading || runAllLoading}
                className="text-xs font-bold font-mono"
              >
                {sandboxLoading ? (
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                )}
                {sandboxLoading ? 'Executing...' : 'Run Code'}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Left: Code to Run */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-semibold text-slate-700">Language:</span>
                  <select
                    value={sandboxLang}
                    onChange={(e) => setSandboxLang(e.target.value as CodingLanguage)}
                    className="px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-xs font-mono font-bold"
                  >
                    {allowedLanguages.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const refCode = referenceSolutions[sandboxLang] || '';
                    if (refCode) setSandboxCode(refCode);
                    else setSandboxCode(starterCodeMap[sandboxLang] || '');
                  }}
                  className="text-[11px] font-mono text-sky-700 hover:underline"
                >
                  Load Reference Solution
                </button>
              </div>

              <div className="rounded-2xl overflow-hidden border border-slate-800 shadow-sm">
                <Editor
                  height="260px"
                  language={getMonacoLang(sandboxLang)}
                  value={sandboxCode}
                  onChange={(val) => setSandboxCode(val || '')}
                  theme="vs-dark"
                  options={{
                    minimap: { enabled: false },
                    fontSize: 13,
                    scrollBeyondLastLine: false,
                    wordWrap: 'on',
                    lineNumbers: 'on',
                  }}
                />
              </div>

              {/* Custom Stdin & Expected Output */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-semibold text-slate-600 font-mono">
                      Stdin Input
                    </label>
                    {testCases.length > 0 && (
                      <select
                        onChange={(e) => {
                          const idx = parseInt(e.target.value, 10);
                          if (!isNaN(idx) && testCases[idx]) {
                            setSandboxStdin(testCases[idx].input_data);
                            setSandboxExpected(testCases[idx].expected_output);
                          }
                        }}
                        className="text-[10px] font-mono border border-slate-200 rounded px-1.5 py-0.5 bg-slate-50"
                      >
                        <option value="">Load from TC...</option>
                        {testCases.map((tc, i) => (
                          <option key={i} value={i}>
                            #{i + 1} {tc.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                  <textarea
                    rows={3}
                    value={sandboxStdin}
                    onChange={(e) => setSandboxStdin(e.target.value)}
                    className="w-full p-2 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-600 font-mono">
                    Expected Output (Comparison)
                  </label>
                  <textarea
                    rows={3}
                    value={sandboxExpected}
                    onChange={(e) => setSandboxExpected(e.target.value)}
                    className="w-full p-2 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Right: Sandbox Execution Output */}
            <div className="p-4 rounded-2xl bg-slate-900 text-slate-100 border border-slate-800 space-y-3 font-mono text-xs flex flex-col justify-between">
              <div className="space-y-3 overflow-y-auto max-h-[420px]">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="font-bold text-slate-300 uppercase tracking-wider text-[11px]">
                    Execution Verdict & Diagnostics
                  </span>
                  {sandboxResult && (
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        sandboxResult.passed || sandboxResult.status_id === 3
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      }`}
                    >
                      {sandboxResult.status_description}
                    </span>
                  )}
                </div>

                {sandboxResult ? (
                  <div className="space-y-3">
                    {/* Metrics */}
                    <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                      <div>
                        Time: <strong className="text-slate-100">{sandboxResult.time}s</strong>
                      </div>
                      <div>
                        Memory: <strong className="text-slate-100">{sandboxResult.memory} KB</strong>
                      </div>
                    </div>

                    {/* Stdout */}
                    <div>
                      <span className="text-slate-400 text-[10px] block mb-1">Actual Stdout:</span>
                      <pre className="p-2.5 rounded-lg bg-slate-950 text-emerald-300 overflow-x-auto border border-slate-800 font-mono">
                        {sandboxResult.stdout !== null ? sandboxResult.stdout : '(empty stdout)'}
                      </pre>
                    </div>

                    {/* Stderr / Compile Error */}
                    {(sandboxResult.stderr || sandboxResult.compile_output) && (
                      <div>
                        <span className="text-rose-400 text-[10px] block mb-1">Diagnostics / Stderr:</span>
                        <pre className="p-2.5 rounded-lg bg-rose-950/40 text-rose-300 overflow-x-auto border border-rose-900/40 font-mono">
                          {sandboxResult.compile_output || sandboxResult.stderr}
                        </pre>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="py-16 text-center text-slate-500 text-xs">
                    Click "Run Code" or "Run All Tests" to inspect real Judge0 output.
                  </div>
                )}

                {/* Bulk Results Summary if active */}
                {Object.keys(bulkRunResults).length > 0 && (
                  <div className="pt-2 border-t border-slate-800 space-y-1.5">
                    <span className="text-[10px] text-slate-400 font-bold uppercase">
                      Bulk Test Run Results:
                    </span>
                    <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                      {testCases.map((tc, idx) => {
                        const res = bulkRunResults[idx];
                        if (!res) return null;
                        const passed = res.passed || res.status_id === 3;
                        return (
                          <div
                            key={idx}
                            className={`p-1.5 rounded border flex items-center justify-between ${
                              passed
                                ? 'bg-emerald-950/30 border-emerald-900/50 text-emerald-300'
                                : 'bg-rose-950/30 border-rose-900/50 text-rose-300'
                            }`}
                          >
                            <span>#{idx + 1} {tc.name}</span>
                            <span className="font-bold">{passed ? 'PASS' : 'FAIL'}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              <div className="text-[10px] text-slate-500 pt-2 border-t border-slate-800 flex justify-between">
                <span>Real Judge0 CE v1.13.1 + Isolate v1.10.1</span>
                <span>Fail-Closed Security</span>
              </div>
            </div>
          </div>
        </Card>
      </section>

      {/* SECTION H — QUESTION HEALTH */}
      <section id="section-health">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-rose-50 text-rose-700 border border-rose-200">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider font-mono">
                  Section H: Question Health (Authoritative 12 Checks)
                </h3>
                <p className="text-xs text-slate-500">
                  Deterministic backend validation enforcing immutability invariants before publishing
                </p>
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={loadBackendHealth}
              disabled={healthLoading}
              className="text-xs font-mono font-semibold text-slate-700 bg-white border-slate-300 hover:bg-slate-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1 ${healthLoading ? 'animate-spin text-emerald-600' : ''}`} />
              Refresh Health
            </Button>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-mono font-bold">
              <span className="text-slate-700">Health Readiness Assessment</span>
              <span className={isHealthReady ? 'text-emerald-700' : 'text-amber-700'}>
                {passedChecksCount} / {displayChecks.length} Checks Passed ({Math.round((passedChecksCount / displayChecks.length) * 100)}%)
              </span>
            </div>
            <div className="w-full h-2.5 rounded-full bg-slate-100 overflow-hidden border border-slate-200">
              <div
                className={`h-full transition-all duration-300 ${
                  isHealthReady ? 'bg-emerald-600' : 'bg-amber-500'
                }`}
                style={{ width: `${(passedChecksCount / displayChecks.length) * 100}%` }}
              />
            </div>
          </div>

          {/* 12 Checks Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {displayChecks.map((check, idx) => (
              <div
                key={check.key || idx}
                className={`p-3.5 rounded-xl border transition-all flex items-start gap-3 ${
                  check.passed
                    ? 'bg-emerald-50/40 border-emerald-200/80 text-slate-800'
                    : 'bg-rose-50/50 border-rose-200 text-rose-900'
                }`}
              >
                <div className="mt-0.5">
                  {check.passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-600" />
                  )}
                </div>
                <div className="space-y-0.5 flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs font-mono text-slate-900">
                      {check.display_name}
                    </span>
                    <span
                      className={`text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded ${
                        check.passed
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {check.passed ? 'PASS' : 'ERROR'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed font-sans">
                    {check.message}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* SECTION I — CANDIDATE PREVIEW MODAL */}
      {candidatePreviewOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
        >
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-900">
            {/* Modal Header */}
            <div className="px-6 py-4 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <Eye className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold tracking-tight">
                    Candidate Test Room Preview (Live Draft)
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Exact student view • Hidden tests, reference solutions & diagnostics are strictly redacted
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setCandidatePreviewOpen(false)}
                className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Problem Metadata */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="info">CODING</Badge>
                  <Badge
                    variant={
                      difficulty === 'EASY'
                        ? 'success'
                        : difficulty === 'MEDIUM'
                        ? 'warning'
                        : 'danger'
                    }
                  >
                    {difficulty}
                  </Badge>
                </div>
                <div className="font-mono font-bold text-slate-700">
                  Points: <span className="text-emerald-700">{points} pts</span>
                  {negativeMarkingEnabled && (
                    <span className="text-rose-600 ml-2">Penalty: -{negativePoints}</span>
                  )}
                </div>
              </div>

              {/* Title & Description */}
              <div className="space-y-3">
                <h2 className="text-lg font-bold text-slate-900">{title || '(Untitled Question)'}</h2>
                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-800 leading-relaxed whitespace-pre-wrap font-sans">
                  {description || '(No problem statement provided)'}
                </div>
              </div>

              {/* Constraints & Formats */}
              {(constraints || inputFormat || outputFormat) && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  {constraints && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <strong className="block text-slate-700 font-mono mb-1">Constraints:</strong>
                      <pre className="font-mono text-[11px] text-slate-800 whitespace-pre-wrap">
                        {constraints}
                      </pre>
                    </div>
                  )}
                  {inputFormat && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <strong className="block text-slate-700 font-mono mb-1">Input Format:</strong>
                      <p className="font-mono text-[11px] text-slate-800">{inputFormat}</p>
                    </div>
                  )}
                  {outputFormat && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <strong className="block text-slate-700 font-mono mb-1">Output Format:</strong>
                      <p className="font-mono text-[11px] text-slate-800">{outputFormat}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Public Examples */}
              <div className="space-y-3">
                <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700">
                  Candidate Examples ({examples.length})
                </h4>
                <div className="space-y-3">
                  {examples.map((ex, i) => (
                    <div
                      key={i}
                      className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono space-y-2"
                    >
                      <div className="font-bold text-slate-800">{ex.name}</div>
                      <div className="grid grid-cols-2 gap-3 text-[11px]">
                        <div>
                          <span className="text-slate-500 block mb-0.5">Input:</span>
                          <pre className="p-2 rounded bg-slate-900 text-slate-100 overflow-x-auto">
                            {ex.input || '(empty)'}
                          </pre>
                        </div>
                        <div>
                          <span className="text-slate-500 block mb-0.5">Output:</span>
                          <pre className="p-2 rounded bg-slate-900 text-slate-100 overflow-x-auto">
                            {ex.output || '(empty)'}
                          </pre>
                        </div>
                      </div>
                      {ex.explanation && (
                        <p className="text-[11px] text-slate-600 font-sans italic">
                          Explanation: {ex.explanation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Candidate Starter Code Preview */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold uppercase text-slate-700">
                    Candidate Code Editor
                  </span>
                  <div className="flex items-center gap-1">
                    {allowedLanguages.map((l) => (
                      <button
                        key={l}
                        type="button"
                        onClick={() => setActiveCodeTab(l)}
                        className={`px-2.5 py-1 text-xs font-mono rounded-lg border ${
                          activeCodeTab === l
                            ? 'bg-slate-900 text-white border-slate-900 font-bold'
                            : 'bg-white text-slate-600 border-slate-300'
                        }`}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl overflow-hidden border border-slate-800">
                  <Editor
                    height="240px"
                    language={getMonacoLang(activeCodeTab)}
                    value={starterCodeMap[activeCodeTab] || ''}
                    theme="vs-dark"
                    options={{
                      readOnly: true,
                      minimap: { enabled: false },
                      fontSize: 12,
                      scrollBeyondLastLine: false,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCandidatePreviewOpen(false)}
              >
                Close Preview
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CodingQuestionEditor;
