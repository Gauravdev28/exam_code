import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import {
  getStudentAttemptDetail,
  saveAttemptAnswer,
  submitAttempt,
} from '../../api/assessments';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  Clock,
  CheckCircle2,
  Code2,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
  Send,
  Lock,
  HelpCircle,
  AlertTriangle,
  Camera,
  CameraOff,
  Mic,
  Shield,
  ShieldAlert,
} from 'lucide-react';
import {
  StudentAttemptDetail,
  StudentSnapshotQuestion,
  StudentAnswerData,
} from '../../types/assessment';
import { evaluatorApi } from '../../api/evaluator';
import { CodeSubmissionResult } from '../../types/evaluator';
import {
  startProctoringSession,
  reportBrowserEvent,
  uploadProctoringFrame,
  acknowledgeWarning,
  sendProctoringHeartbeat,
} from '../../api/proctoring';
import { ProctoringWarning } from '../../types/proctoring';


export const StudentTestRoomPage: React.FC = () => {
  const { attemptId } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();

  const [attemptData, setAttemptData] = useState<StudentAttemptDetail | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number>(0);
  const [answers, setAnswers] = useState<Record<string, StudentAnswerData>>({});

  // Timer & Real-time State
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [saveStatus, setSaveStatus] = useState<'SAVED' | 'SAVING' | 'ERROR'>('SAVED');

  // Submit Modal
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Evaluator Execution State
  const [executingQuestionId, setExecutingQuestionId] = useState<string | null>(null);
  const [executionMode, setExecutionMode] = useState<'RUN' | 'SUBMIT' | null>(null);
  const [submissionResults, setSubmissionResults] = useState<Record<string, CodeSubmissionResult | undefined>>({});
  const [activeTestCaseTabs, setActiveTestCaseTabs] = useState<Record<string, number>>({});
  const [executionError, setExecutionError] = useState<Record<string, string | null>>({});

  // AI Proctoring & Telemetry State
  const [isProctoringActive, setIsProctoringActive] = useState<boolean>(false);
  const [cameraStatus, setCameraStatus] = useState<'CONNECTED' | 'DISCONNECTED' | 'DENIED'>('DISCONNECTED');
  const [micStatus, setMicStatus] = useState<'CONNECTED' | 'DISCONNECTED' | 'DENIED'>('DISCONNECTED');
  const [activeWarning, setActiveWarning] = useState<ProctoringWarning | null>(null);
  const [isWarningModalOpen, setIsWarningModalOpen] = useState<boolean>(false);

  const socketRef = useRef<WebSocket | null>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const revisionsRef = useRef<Record<string, number>>({});
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const frameSeqRef = useRef<number>(0);

  // Initialize Proctoring & Capture Media
  useEffect(() => {
    if (!attemptId) return;

    let isMounted = true;
    let sampleInterval: NodeJS.Timeout | null = null;
    let heartbeatInterval: NodeJS.Timeout | null = null;

    const setupProctoring = async () => {
      try {
        await startProctoringSession(attemptId);
        if (isMounted) setIsProctoringActive(true);
      } catch (err) {
        console.warn('Proctoring start fallback:', err);
      }

      // Request media devices gracefully
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 320 }, height: { ideal: 240 }, frameRate: { ideal: 10 } },
          audio: true,
        });

        if (!isMounted) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        mediaStreamRef.current = stream;
        setCameraStatus('CONNECTED');
        setMicStatus('CONNECTED');

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        // Periodic Frame Capture (Target 0.5 FPS = 1 frame every 2.0s)
        sampleInterval = setInterval(() => {
          if (!videoRef.current || !canvasRef.current) return;
          const video = videoRef.current;
          const canvas = canvasRef.current;
          if (video.videoWidth === 0 || video.videoHeight === 0) return;

          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext('2d');
          if (!ctx) return;

          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          canvas.toBlob(
            async (blob) => {
              if (blob && attemptId) {
                frameSeqRef.current += 1;
                try {
                  await uploadProctoringFrame(attemptId, blob, frameSeqRef.current);
                } catch (err) {
                  // Throttled / network jitter handled gracefully
                }
              }
            },
            'image/jpeg',
            0.6
          );
        }, 2000);
      } catch (mediaErr) {
        console.warn('Media capture unavailable:', mediaErr);
        if (isMounted) {
          setCameraStatus('DENIED');
          setMicStatus('DENIED');
          reportBrowserEvent(attemptId, 'CAMERA_UNAVAILABLE').catch(() => {});
        }
      }

      // Periodic REST Heartbeat fallback (every 15s)
      heartbeatInterval = setInterval(() => {
        if (attemptId) {
          sendProctoringHeartbeat(attemptId).catch(() => {});
        }
      }, 15000);
    };

    setupProctoring();

    // Browser Telemetry Event Listeners
    const handleVisibilityChange = () => {
      if (document.hidden && attemptId) {
        reportBrowserEvent(attemptId, 'TAB_SWITCH')
          .then((res) => {
            if (res.warning_issued && res.warning) {
              setActiveWarning(res.warning);
              setIsWarningModalOpen(true);
            }
          })
          .catch(() => {});
      }
    };

    const handleWindowBlur = () => {
      if (attemptId) {
        reportBrowserEvent(attemptId, 'WINDOW_BLUR')
          .then((res) => {
            if (res.warning_issued && res.warning) {
              setActiveWarning(res.warning);
              setIsWarningModalOpen(true);
            }
          })
          .catch(() => {});
      }
    };

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement && attemptId) {
        reportBrowserEvent(attemptId, 'FULLSCREEN_EXIT')
          .then((res) => {
            if (res.warning_issued && res.warning) {
              setActiveWarning(res.warning);
              setIsWarningModalOpen(true);
            }
          })
          .catch(() => {});
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('blur', handleWindowBlur);
    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => {
      isMounted = false;
      if (sampleInterval) clearInterval(sampleInterval);
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('blur', handleWindowBlur);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [attemptId]);

  const handleAcknowledgeWarning = async () => {
    if (activeWarning && attemptId) {
      try {
        await acknowledgeWarning(attemptId, activeWarning.id);
      } catch (err) {
        console.warn('Warning ack error:', err);
      }
    }
    setIsWarningModalOpen(false);
  };

  // Load Attempt State
  const loadAttemptState = useCallback(async () => {
    if (!attemptId) return;
    try {
      const res = await getStudentAttemptDetail(attemptId);
      if (res.data) {
        const d = res.data;
        setAttemptData(d);
        setRemainingSeconds(d.remaining_seconds);
        setAnswers(d.answers || {});

        // Initialize local revisions
        const revMap: Record<string, number> = {};
        Object.entries(d.answers || {}).forEach(([qId, ans]) => {
          revMap[qId] = ans.revision || 1;
        });
        revisionsRef.current = revMap;
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load test attempt.');
    } finally {
      setIsLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    loadAttemptState();
  }, [loadAttemptState]);

  // WebSocket Connection
  useEffect(() => {
    if (!attemptId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/attempts/${attemptId}/`;

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'PONG' || data.type === 'SYNC_STATE') {
          if (typeof data.remaining_seconds === 'number') {
            setRemainingSeconds(data.remaining_seconds);
          }
          if (data.status === 'EXPIRED' || data.status === 'SUBMITTED') {
            setAttemptData((prev) => (prev ? { ...prev, status: data.status } : null));
          }
        } else if (data.type === 'CODE_SUBMISSION_COMPLETED' || data.type === 'CODE_SUBMISSION_QUEUED' || data.type === 'CODE_SUBMISSION_PROCESSING') {
          const submData = data.data;
          if (submData && submData.question_id) {
            if (data.type === 'CODE_SUBMISSION_COMPLETED') {
              // Fetch full submission details
              evaluatorApi.getSubmissionResult(submData.submission_id).then((res) => {
                if (res.data) {
                  setSubmissionResults((prev) => ({
                    ...prev,
                    [submData.question_id]: res.data,
                  }));
                }
                setExecutingQuestionId(null);
                setExecutionMode(null);
              }).catch(() => {
                setExecutingQuestionId(null);
                setExecutionMode(null);
              });
            }
          }
        }
      } catch (err) {
        console.error('WS error parsing message', err);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    // Ping interval for timer sync every 10 seconds
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'PING' }));
      }
    }, 10000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [attemptId]);

  // Handle Code Run (Public Tests Only)
  const handleRunCode = async (questionId: string) => {
    if (!attemptId) return;
    const currentAns = answers[questionId];
    const code = currentAns?.code_response || '';
    const lang = currentAns?.code_language || 'PYTHON';

    setExecutingQuestionId(questionId);
    setExecutionMode('RUN');
    setExecutionError((prev) => ({ ...prev, [questionId]: null }));

    try {
      const res = await evaluatorApi.runCode(attemptId, questionId, code, lang);
      if (res.data) {
        const subId = res.data.submission_id;
        // Poll for result as fallback
        const pollInterval = setInterval(async () => {
          try {
            const subRes = await evaluatorApi.getSubmissionResult(subId);
            if (subRes.data && (subRes.data.status === 'COMPLETED' || subRes.data.status === 'FAILED')) {
              clearInterval(pollInterval);
              setSubmissionResults((prev) => ({ ...prev, [questionId]: subRes.data }));
              setExecutingQuestionId(null);
              setExecutionMode(null);
            }
          } catch {
            clearInterval(pollInterval);
            setExecutingQuestionId(null);
            setExecutionMode(null);
          }
        }, 1000);
      }
    } catch (err: any) {
      setExecutionError((prev) => ({
        ...prev,
        [questionId]: err.error?.message || err.message || 'Execution request failed.',
      }));
      setExecutingQuestionId(null);
      setExecutionMode(null);
    }
  };

  // Handle Code Submit (Authoritative Evaluation)
  const handleSubmitCode = async (questionId: string) => {
    if (!attemptId) return;
    const currentAns = answers[questionId];
    const code = currentAns?.code_response || '';
    const lang = currentAns?.code_language || 'PYTHON';

    setExecutingQuestionId(questionId);
    setExecutionMode('SUBMIT');
    setExecutionError((prev) => ({ ...prev, [questionId]: null }));

    try {
      const res = await evaluatorApi.submitCode(attemptId, questionId, code, lang);
      if (res.data) {
        const subId = res.data.submission_id;
        // Poll for result as fallback
        const pollInterval = setInterval(async () => {
          try {
            const subRes = await evaluatorApi.getSubmissionResult(subId);
            if (subRes.data && (subRes.data.status === 'COMPLETED' || subRes.data.status === 'FAILED')) {
              clearInterval(pollInterval);
              setSubmissionResults((prev) => ({ ...prev, [questionId]: subRes.data }));
              setExecutingQuestionId(null);
              setExecutionMode(null);
              // Refresh answers
              setAnswers((prev) => ({
                ...prev,
                [questionId]: {
                  ...prev[questionId],
                  is_answered: true,
                  code_response: code,
                  code_language: lang,
                }
              }));
            }
          } catch {
            clearInterval(pollInterval);
            setExecutingQuestionId(null);
            setExecutionMode(null);
          }
        }, 1000);
      }
    } catch (err: any) {
      setExecutionError((prev) => ({
        ...prev,
        [questionId]: err.error?.message || err.message || 'Submission evaluation failed.',
      }));
      setExecutingQuestionId(null);
      setExecutionMode(null);
    }
  };


  // Local Countdown Timer
  useEffect(() => {
    if (remainingSeconds <= 0) return;

    const timer = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          loadAttemptState(); // auto refresh on expiry
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [remainingSeconds, loadAttemptState]);

  // Debounced Autosave Handler
  const triggerAutosave = (questionId: string, updatedFields: Partial<StudentAnswerData>) => {
    if (!attemptId || attemptData?.status !== 'IN_PROGRESS') return;

    setSaveStatus('SAVING');

    // Update local state immediately
    setAnswers((prev) => {
      const existing = prev[questionId] || {
        question_id: questionId,
        question_type: currentQuestion?.question_type || 'MCQ',
        revision: revisionsRef.current[questionId] || 1,
        is_answered: true,
      };
      return {
        ...prev,
        [questionId]: {
          ...existing,
          ...updatedFields,
          is_answered: true,
        },
      };
    });

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(async () => {
      const nextRev = (revisionsRef.current[questionId] || 1) + 1;
      revisionsRef.current[questionId] = nextRev;

      try {
        const payload: any = {
          ...updatedFields,
          revision: nextRev,
        };
        const res = await saveAttemptAnswer(attemptId, questionId, payload);
        if (res.data?.status === 'SAVED') {
          setSaveStatus('SAVED');
          revisionsRef.current[questionId] = res.data.server_revision;
        } else {
          setSaveStatus('SAVED');
        }
      } catch (err) {
        console.error('Autosave error', err);
        setSaveStatus('ERROR');
      }
    }, 600);
  };

  const handleSubmit = async () => {
    if (!attemptId) return;
    setIsSubmitting(true);
    try {
      const res = await submitAttempt(attemptId);
      if (res.data) {
        setAttemptData((prev) => (prev ? { ...prev, status: 'SUBMITTED' } : null));
        setIsSubmitModalOpen(false);
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to submit attempt.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const questions = attemptData?.questions || [];
  const currentQuestion: StudentSnapshotQuestion | undefined = questions[currentQuestionIndex];
  const currentAnswer = currentQuestion ? answers[currentQuestion.snapshot_question_id] : undefined;

  const isTerminal = attemptData?.status === 'SUBMITTED' || attemptData?.status === 'EXPIRED' || remainingSeconds === 0;

  // Format Timer MM:SS
  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(mins).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const answeredCount = Object.values(answers).filter((a) => a.is_answered).length;

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center space-y-3 bg-slate-950">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400 font-mono">Initializing secure test room & snapshot...</p>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-slate-950">
        <Card className="max-w-md w-full p-8 text-center space-y-6 border-slate-800 shadow-2xl">
          <div className="w-14 h-14 rounded-2xl bg-red-500/10 text-red-400 border border-red-500/20 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-8 h-8 text-red-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Access Error</h2>
            <p className="text-xs text-red-300 mt-2 font-mono">{errorMessage}</p>
          </div>
          <Button variant="secondary" size="md" className="w-full" onClick={() => navigate('/student/assessments')}>
            Back to Assessments
          </Button>
        </Card>
      </div>
    );
  }

  if (isTerminal && attemptData?.status !== 'IN_PROGRESS') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-slate-950">
        <Card className="max-w-md w-full p-8 text-center space-y-6 border-slate-800 shadow-2xl">
          <div className="w-14 h-14 rounded-2xl bg-brand-500/10 text-brand-400 border border-brand-500/20 flex items-center justify-center mx-auto">
            {attemptData?.status === 'SUBMITTED' ? (
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            ) : (
              <Lock className="w-8 h-8 text-amber-400" />
            )}
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">
              {attemptData?.status === 'SUBMITTED' ? 'Assessment Submitted' : 'Assessment Time Expired'}
            </h2>
            <p className="text-xs text-slate-400 mt-2 font-mono">
              Your responses have been recorded on the server.
            </p>
          </div>
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 font-mono text-xs text-slate-300 space-y-1 text-left">
            <div>Assessment: <strong className="text-white">{attemptData?.title}</strong></div>
            <div>Status: <span className="text-brand-400 font-bold">{attemptData?.status}</span></div>
            <div>Total Questions: <strong>{questions.length}</strong></div>
            <div>Answered: <strong className="text-emerald-400">{answeredCount}</strong></div>
          </div>
          <Button variant="primary" size="md" className="w-full" onClick={() => navigate('/')}>
            Back to Dashboard
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-brand-500/30">
      {/* Top HUD Bar */}
      <header className="sticky top-0 z-40 glass-panel border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h2 className="text-sm font-bold text-white truncate max-w-xs sm:max-w-md">
              {attemptData?.title}
            </h2>
            <span className="text-[10px] font-mono text-slate-400">
              Attempt #{attemptData?.attempt_number} &bull; Q{currentQuestionIndex + 1} of {questions.length}
            </span>
          </div>
        </div>

        {/* Center: Timer & Status */}
        <div className="flex items-center gap-6 font-mono text-xs">
          {/* Server Timer */}
          <div
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl border font-bold ${
              remainingSeconds < 300
                ? 'bg-red-500/20 border-red-500 text-red-300 animate-pulse'
                : 'bg-slate-900 border-slate-800 text-brand-300'
            }`}
          >
            <Clock className="w-4 h-4" />
            <span className="text-sm">{formatTime(remainingSeconds)}</span>
          </div>

          {/* Autosave Status */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400">
            <span
              className={`w-2 h-2 rounded-full ${
                saveStatus === 'SAVED'
                  ? 'bg-emerald-400'
                  : saveStatus === 'SAVING'
                  ? 'bg-amber-400 animate-pulse'
                  : 'bg-red-400'
              }`}
            />
            <span>{saveStatus === 'SAVED' ? 'Saved' : saveStatus === 'SAVING' ? 'Saving...' : 'Sync Error'}</span>
          </div>

          {/* AI Proctoring HUD Status */}
          <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px]">
            <span className="flex items-center gap-1 text-slate-300">
              <Camera className={`w-3 h-3 ${cameraStatus === 'CONNECTED' ? 'text-emerald-400' : 'text-amber-400'}`} />
              <span className="text-[10px]">{cameraStatus === 'CONNECTED' ? 'Cam ON' : 'Cam Off'}</span>
            </span>
            <span className="text-slate-700">|</span>
            <span className="flex items-center gap-1 text-slate-300">
              <Mic className={`w-3 h-3 ${micStatus === 'CONNECTED' ? 'text-emerald-400' : 'text-amber-400'}`} />
              <span className="text-[10px]">{micStatus === 'CONNECTED' ? 'Mic ON' : 'Mic Off'}</span>
            </span>
            <span className="text-slate-700">|</span>
            <span className="flex items-center gap-1 text-slate-300">
              <Shield className={`w-3 h-3 ${isProctoringActive ? 'text-indigo-400' : 'text-slate-500'}`} />
              <span className="text-[10px]">{isProctoringActive ? 'Shield Active' : 'Shield Off'}</span>
            </span>
          </div>

          {/* Connection */}
          <div className="hidden md:flex items-center gap-1 text-[11px] text-slate-500">
            {wsConnected ? (
              <Wifi className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-amber-400" />
            )}
          </div>
        </div>

        {/* Submit Action */}
        <Button variant="primary" size="sm" onClick={() => setIsSubmitModalOpen(true)}>
          <Send className="w-3.5 h-3.5 mr-1.5" />
          Finish & Submit
        </Button>
      </header>

      {/* Main Workspace: Left Sidebar & Question Canvas */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Left Question Roster Sidebar */}
        <aside className="w-full md:w-64 border-r border-slate-900 bg-slate-950/80 p-4 space-y-4 overflow-y-auto flex-shrink-0">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>Questions</span>
            <span className="text-emerald-400 font-bold">{answeredCount}/{questions.length} answered</span>
          </div>

          {/* Question Grid Pills */}
          <div className="grid grid-cols-5 md:grid-cols-4 gap-2 font-mono text-xs">
            {questions.map((q, idx) => {
              const isCurr = idx === currentQuestionIndex;
              const isAns = answers[q.snapshot_question_id]?.is_answered;

              return (
                <button
                  key={q.snapshot_question_id}
                  onClick={() => setCurrentQuestionIndex(idx)}
                  className={`h-9 rounded-lg font-bold transition-all border ${
                    isCurr
                      ? 'bg-brand-500 text-slate-950 border-brand-400 shadow-md shadow-brand-500/20'
                      : isAns
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30'
                      : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="pt-4 border-t border-slate-900 space-y-2 text-[11px] font-mono text-slate-400">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-emerald-500/20 border border-emerald-500/40" />
              <span>Answered</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-slate-900 border border-slate-800" />
              <span>Unanswered</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-brand-500 border border-brand-400" />
              <span>Current</span>
            </div>
          </div>
        </aside>

        {/* Center: Active Question Canvas */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-8 space-y-6 max-w-4xl mx-auto w-full">
          {currentQuestion ? (
            <div className="space-y-6">
              {/* Question Header & Meta */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 font-mono text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="info">{currentQuestion.question_type}</Badge>
                  <Badge
                    variant={
                      currentQuestion.difficulty === 'EASY'
                        ? 'success'
                        : currentQuestion.difficulty === 'MEDIUM'
                        ? 'warning'
                        : 'danger'
                    }
                  >
                    {currentQuestion.difficulty}
                  </Badge>
                </div>

                <div className="flex items-center gap-4 text-slate-300 font-semibold">
                  <span>Points: <strong className="text-brand-400">{currentQuestion.points}</strong></span>
                  {currentQuestion.negative_marking_enabled && (
                    <span className="text-red-400">Penalty: -{currentQuestion.negative_points}</span>
                  )}
                </div>
              </div>

              {/* Title & Prompt */}
              <div className="space-y-3">
                <h1 className="text-lg font-bold text-white">{currentQuestion.title}</h1>
                <div className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed bg-slate-900/40 p-4 rounded-xl border border-slate-800">
                  {currentQuestion.description}
                </div>
                {currentQuestion.instructions && (
                  <div className="p-3 rounded-lg bg-brand-500/5 border border-brand-500/20 text-xs text-brand-300 flex items-start gap-2">
                    <HelpCircle className="w-4 h-4 text-brand-400 flex-shrink-0 mt-0.5" />
                    <span><strong>Instructions:</strong> {currentQuestion.instructions}</span>
                  </div>
                )}
              </div>

              {/* Type-Specific Answer Inputs */}
              <div className="pt-2">
                {/* MCQ */}
                {currentQuestion.question_type === 'MCQ' && (
                  <div className="space-y-3 font-sans">
                    <label className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider block">
                      Select One Option:
                    </label>
                    <div className="space-y-2">
                      {(currentQuestion.type_config?.options || []).map((opt: any) => {
                        const isSelected = (currentAnswer?.selected_options || []).includes(opt.id);
                        return (
                          <label
                            key={opt.id}
                            className={`flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                              isSelected
                                ? 'bg-brand-500/10 border-brand-500 text-white shadow-sm'
                                : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700'
                            }`}
                          >
                            <input
                              type="radio"
                              name={`mcq_${currentQuestion.snapshot_question_id}`}
                              checked={isSelected}
                              onChange={() =>
                                triggerAutosave(currentQuestion.snapshot_question_id, {
                                  selected_options: [opt.id],
                                })
                              }
                              className="text-brand-500 focus:ring-brand-500 h-4 w-4 bg-slate-900 border-slate-700"
                            />
                            <span className="font-mono font-bold text-brand-400 w-5">{opt.id}.</span>
                            <span className="text-sm">{opt.text}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Multi-Select */}
                {currentQuestion.question_type === 'MULTI_SELECT' && (
                  <div className="space-y-3 font-sans">
                    <label className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider block">
                      Select All Correct Options:
                    </label>
                    <div className="space-y-2">
                      {(currentQuestion.type_config?.options || []).map((opt: any) => {
                        const selectedList = currentAnswer?.selected_options || [];
                        const isChecked = selectedList.includes(opt.id);
                        return (
                          <label
                            key={opt.id}
                            className={`flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                              isChecked
                                ? 'bg-brand-500/10 border-brand-500 text-white shadow-sm'
                                : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                const nextList = e.target.checked
                                  ? [...selectedList, opt.id]
                                  : selectedList.filter((id: string) => id !== opt.id);
                                triggerAutosave(currentQuestion.snapshot_question_id, {
                                  selected_options: nextList,
                                });
                              }}
                              className="rounded text-brand-500 focus:ring-brand-500 h-4 w-4 bg-slate-900 border-slate-700"
                            />
                            <span className="font-mono font-bold text-brand-400 w-5">{opt.id}.</span>
                            <span className="text-sm">{opt.text}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* True / False */}
                {currentQuestion.question_type === 'TRUE_FALSE' && (
                  <div className="space-y-3 font-mono">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                      Select Answer:
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                      <button
                        type="button"
                        onClick={() =>
                          triggerAutosave(currentQuestion.snapshot_question_id, {
                            selected_options: ['True'],
                          })
                        }
                        className={`p-4 rounded-xl border font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                          (currentAnswer?.selected_options || []).includes('True')
                            ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 shadow-md'
                            : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        <CheckCircle2 className="w-5 h-5" />
                        TRUE
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          triggerAutosave(currentQuestion.snapshot_question_id, {
                            selected_options: ['False'],
                          })
                        }
                        className={`p-4 rounded-xl border font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                          (currentAnswer?.selected_options || []).includes('False')
                            ? 'bg-rose-500/20 border-rose-500 text-rose-300 shadow-md'
                            : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        FALSE
                      </button>
                    </div>
                  </div>
                )}

                {/* Short Answer */}
                {currentQuestion.question_type === 'SHORT_ANSWER' && (
                  <div className="space-y-3 font-mono">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                      Your Text Response:
                    </label>
                    <input
                      type="text"
                      value={currentAnswer?.text_response || ''}
                      onChange={(e) =>
                        triggerAutosave(currentQuestion.snapshot_question_id, {
                          text_response: e.target.value,
                        })
                      }
                      placeholder="Type your exact answer here..."
                      className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 text-sm focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                )}

                {/* Coding Problem with Monaco Editor */}
                {currentQuestion.question_type === 'CODING' && currentQuestion.coding_config && (
                  <div className="space-y-4">
                    {/* Constraints & Limits */}
                    <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-slate-400 p-3 rounded-xl bg-slate-900/80 border border-slate-800">
                      <div className="flex items-center gap-3">
                        <Code2 className="w-4 h-4 text-brand-400" />
                        <span>Language:</span>
                        <select
                          value={currentAnswer?.code_language || currentQuestion.coding_config.allowed_languages?.[0] || 'PYTHON'}
                          onChange={(e) =>
                            triggerAutosave(currentQuestion.snapshot_question_id, {
                              code_language: e.target.value,
                              code_response: currentAnswer?.code_response || '',
                            })
                          }
                          className="px-2 py-1 rounded bg-slate-950 border border-slate-700 text-brand-300 font-bold focus:ring-1 focus:ring-brand-500"
                        >
                          {(currentQuestion.coding_config.allowed_languages || ['PYTHON', 'CPP', 'JAVA']).map((lang) => (
                            <option key={lang} value={lang}>{lang}</option>
                          ))}
                        </select>
                      </div>

                      <div className="flex items-center gap-4 text-[11px]">
                        <span>Limit: <strong>{currentQuestion.coding_config.time_limit_ms}ms</strong></span>
                        <span>Mem: <strong>{currentQuestion.coding_config.memory_limit_mb}MB</strong></span>
                      </div>
                    </div>

                    {/* Monaco Code Editor */}
                    <div className="border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
                      <div className="bg-slate-900 px-4 py-2 border-b border-slate-800 text-xs font-mono text-slate-400 flex items-center justify-between">
                        <span>Solution Editor</span>
                        <span className="text-[10px] text-slate-500">Draft saved automatically</span>
                      </div>
                      <Editor
                        height="320px"
                        language={
                          (currentAnswer?.code_language || 'PYTHON').toLowerCase() === 'cpp'
                            ? 'cpp'
                            : (currentAnswer?.code_language || 'PYTHON').toLowerCase() === 'java'
                            ? 'java'
                            : 'python'
                        }
                        theme="vs-dark"
                        value={currentAnswer?.code_response || ''}
                        onChange={(val) =>
                          triggerAutosave(currentQuestion.snapshot_question_id, {
                            code_response: val || '',
                            code_language: currentAnswer?.code_language || currentQuestion.coding_config?.allowed_languages?.[0] || 'PYTHON',
                          })
                        }
                        options={{
                          minimap: { enabled: false },
                          fontSize: 13,
                          lineNumbers: 'on',
                          scrollBeyondLastLine: false,
                        }}
                      />
                    </div>

                    {/* Execution Action Bar */}
                    <div className="flex items-center justify-between gap-3 p-3 bg-slate-900/90 border border-slate-800 rounded-xl">
                      <div className="text-xs font-mono text-slate-400">
                        {executingQuestionId === currentQuestion.snapshot_question_id ? (
                          <span className="text-amber-400 flex items-center gap-2">
                            <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                            {executionMode === 'RUN' ? 'Executing against public tests...' : 'Evaluating authoritative submission...'}
                          </span>
                        ) : executionError[currentQuestion.snapshot_question_id] ? (
                          <span className="text-rose-400">{executionError[currentQuestion.snapshot_question_id]}</span>
                        ) : (
                          <span>Ready to execute or submit.</span>
                        )}
                      </div>

                      <div className="flex items-center gap-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={executingQuestionId !== null}
                          onClick={() => handleRunCode(currentQuestion.snapshot_question_id)}
                        >
                          <Code2 className="w-4 h-4 mr-1 text-cyan-400" />
                          Run Code (Public Tests)
                        </Button>

                        <Button
                          variant="primary"
                          size="sm"
                          disabled={executingQuestionId !== null}
                          onClick={() => handleSubmitCode(currentQuestion.snapshot_question_id)}
                        >
                          <Send className="w-4 h-4 mr-1" />
                          Submit Solution
                        </Button>
                      </div>
                    </div>

                    {/* Live Execution Results Console */}
                    {submissionResults[currentQuestion.snapshot_question_id] && (
                      <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3 font-mono text-xs shadow-xl">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-300">
                              {submissionResults[currentQuestion.snapshot_question_id]?.submission_type === 'RUN' ? 'Test Run Output' : 'Evaluation Verdict'}:
                            </span>
                            <Badge
                              variant={
                                submissionResults[currentQuestion.snapshot_question_id]?.verdict === 'ACCEPTED'
                                  ? 'success'
                                  : submissionResults[currentQuestion.snapshot_question_id]?.verdict === 'COMPILATION_ERROR'
                                  ? 'danger'
                                  : 'warning'
                              }
                            >
                              {submissionResults[currentQuestion.snapshot_question_id]?.verdict || 'COMPLETED'}
                            </Badge>
                          </div>

                          <div className="flex items-center gap-4 text-slate-400 text-[11px]">
                            <span>
                              Passed: <strong className="text-emerald-400">{submissionResults[currentQuestion.snapshot_question_id]?.passed_test_cases}</strong> / {submissionResults[currentQuestion.snapshot_question_id]?.total_test_cases}
                            </span>
                            {submissionResults[currentQuestion.snapshot_question_id]?.submission_type === 'SUBMIT' && (
                              <span>
                                Score: <strong className="text-brand-400">{submissionResults[currentQuestion.snapshot_question_id]?.score_awarded}</strong> / {submissionResults[currentQuestion.snapshot_question_id]?.max_score}
                              </span>
                            )}
                            <span>Time: {submissionResults[currentQuestion.snapshot_question_id]?.execution_time_ms}ms</span>
                            <span>Mem: {submissionResults[currentQuestion.snapshot_question_id]?.memory_used_kb}KB</span>
                          </div>
                        </div>

                        {/* Compilation Error Display */}
                        {submissionResults[currentQuestion.snapshot_question_id]?.compilation_error && (
                          <div className="p-3 bg-rose-950/30 border border-rose-900/50 rounded-lg text-rose-300 space-y-1">
                            <span className="font-bold block text-rose-400">Compilation / Syntax Error:</span>
                            <pre className="text-[11px] overflow-x-auto whitespace-pre-wrap">{submissionResults[currentQuestion.snapshot_question_id]?.compilation_error}</pre>
                          </div>
                        )}

                        {/* Test Cases Tab / List */}
                        {submissionResults[currentQuestion.snapshot_question_id]?.test_cases && (
                          <div className="space-y-2">
                            <div className="flex flex-wrap gap-2">
                              {submissionResults[currentQuestion.snapshot_question_id]?.test_cases.map((tc, idx) => (
                                <button
                                  key={idx}
                                  type="button"
                                  onClick={() => setActiveTestCaseTabs((prev) => ({ ...prev, [currentQuestion.snapshot_question_id]: idx }))}
                                  className={`px-3 py-1.5 rounded-lg font-bold text-[11px] transition-all flex items-center gap-1.5 border ${
                                    (activeTestCaseTabs[currentQuestion.snapshot_question_id] || 0) === idx
                                      ? 'bg-slate-800 border-brand-500 text-white'
                                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                                  }`}
                                >
                                  <span className={`w-2 h-2 rounded-full ${tc.verdict === 'PASSED' ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
                                  {tc.is_hidden ? `Hidden Case #${tc.index}` : `Case #${tc.index}`}
                                </button>
                              ))}
                            </div>

                            {/* Active Tab Details */}
                            {(() => {
                              const activeIdx = activeTestCaseTabs[currentQuestion.snapshot_question_id] || 0;
                              const tc = submissionResults[currentQuestion.snapshot_question_id]?.test_cases[activeIdx];
                              if (!tc) return null;

                              return (
                                <div className="p-3 bg-slate-900/70 border border-slate-800 rounded-lg space-y-2">
                                  <div className="flex items-center justify-between text-[11px]">
                                    <span className="text-slate-400">
                                      Status: <strong className={tc.verdict === 'PASSED' ? 'text-emerald-400' : 'text-rose-400'}>{tc.verdict}</strong>
                                      {tc.is_hidden ? ' (Authoritative Evaluation Test)' : ''}
                                    </span>
                                    <span className="text-slate-500">
                                      Points: {tc.points_awarded} / {tc.max_points} | Exec: {tc.execution_time_ms}ms | Mem: {tc.memory_used_kb}KB
                                    </span>
                                  </div>

                                  {!tc.is_hidden ? (
                                    <div className="grid grid-cols-2 gap-3 text-[11px]">
                                      <div>
                                        <span className="text-slate-500 block text-[10px]">Input (stdin):</span>
                                        <pre className="p-2 rounded bg-slate-950 text-slate-200 overflow-x-auto">{tc.input || '(empty)'}</pre>
                                      </div>
                                      <div>
                                        <span className="text-slate-500 block text-[10px]">Expected Output:</span>
                                        <pre className="p-2 rounded bg-slate-950 text-slate-200 overflow-x-auto">{tc.expected_output}</pre>
                                      </div>
                                      <div className="col-span-2">
                                        <span className="text-slate-500 block text-[10px]">Your Output (stdout):</span>
                                        <pre className={`p-2 rounded bg-slate-950 overflow-x-auto ${tc.verdict === 'PASSED' ? 'text-emerald-300' : 'text-rose-300'}`}>
                                          {tc.actual_output || '(no output)'}
                                        </pre>
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="p-3 bg-slate-950/60 rounded border border-slate-800/80 text-slate-400 text-[11px]">
                                      🔒 <em>Hidden test case inputs and outputs are protected for examination security.</em>
                                    </div>
                                  )}
                                </div>
                              );
                            })()}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Example Public Test Cases */}
                    {currentQuestion.coding_config.public_test_cases && currentQuestion.coding_config.public_test_cases.length > 0 && (
                      <div className="space-y-2 pt-2">
                        <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                          Example Test Cases
                        </h4>
                        <div className="space-y-2">
                          {currentQuestion.coding_config.public_test_cases.map((tc, idx) => (
                            <div key={idx} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-mono space-y-1">
                              <span className="text-slate-500 block">Example Case #{idx + 1} ({tc.points} pts)</span>
                              <div className="grid grid-cols-2 gap-2">
                                <div>
                                  <span className="text-slate-500 block text-[10px]">stdin:</span>
                                  <pre className="p-2 rounded bg-slate-950 text-slate-200 overflow-x-auto">{tc.input_data || '(empty)'}</pre>
                                </div>
                                <div>
                                  <span className="text-slate-500 block text-[10px]">expected stdout:</span>
                                  <pre className="p-2 rounded bg-slate-950 text-slate-200 overflow-x-auto">{tc.expected_output}</pre>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* SQL Query Editor */}
                {currentQuestion.question_type === 'SQL' && currentQuestion.sql_config && (
                  <div className="space-y-4">
                    <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-mono space-y-2">
                      <span className="text-slate-400 font-bold block uppercase tracking-wider">Database Tables & Schema</span>
                      <pre className="p-3 rounded-lg bg-slate-950 text-cyan-300 font-mono text-xs overflow-x-auto border border-slate-800">
                        {currentQuestion.sql_config.schema_setup_sql}
                      </pre>
                    </div>

                    <div className="space-y-2 font-mono text-xs">
                      <label className="text-slate-400 font-bold block uppercase tracking-wider">Your SQL Query:</label>
                      <textarea
                        rows={6}
                        value={currentAnswer?.sql_response || ''}
                        onChange={(e) =>
                          triggerAutosave(currentQuestion.snapshot_question_id, {
                            sql_response: e.target.value,
                          })
                        }
                        placeholder="SELECT * FROM table_name..."
                        className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-cyan-300 font-mono text-xs focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Question Navigation */}
              <div className="flex items-center justify-between pt-6 border-t border-slate-900">
                <Button
                  variant="secondary"
                  size="md"
                  disabled={currentQuestionIndex === 0}
                  onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Previous Question
                </Button>

                <Button
                  variant="primary"
                  size="md"
                  disabled={currentQuestionIndex === questions.length - 1}
                  onClick={() => setCurrentQuestionIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                >
                  Next Question
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          ) : null}
        </main>
      </div>

      {/* Final Submit Confirmation Modal */}
      {isSubmitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
          <Card className="max-w-md w-full p-6 space-y-6 border-slate-800 shadow-2xl relative">
            <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
              <div className="p-2.5 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
                <Send className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white">Submit Assessment</h3>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to finish and submit your assessment? Once submitted, your answers will be permanently locked.
            </p>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 text-xs font-mono space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-400">Total Questions:</span>
                <span className="text-white font-bold">{questions.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Answered Questions:</span>
                <span className="text-emerald-400 font-bold">{answeredCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Unanswered Questions:</span>
                <span className="text-amber-400 font-bold">{questions.length - answeredCount}</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <Button variant="ghost" size="sm" onClick={() => setIsSubmitModalOpen(false)}>
                Continue Exam
              </Button>
              <Button
                variant="primary"
                size="sm"
                isLoading={isSubmitting}
                onClick={handleSubmit}
              >
                Yes, Final Submit
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Hidden Canvas for Video Sampling */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Floating Live Camera Feed */}
      <div className="fixed bottom-4 right-4 z-30 shadow-2xl rounded-xl overflow-hidden border border-slate-700/80 bg-slate-900 w-32 h-24 flex flex-col items-center justify-center">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`w-full h-full object-cover ${cameraStatus === 'CONNECTED' ? 'block' : 'hidden'}`}
        />
        {cameraStatus !== 'CONNECTED' && (
          <div className="flex flex-col items-center gap-1 p-2 text-center">
            <CameraOff className="w-5 h-5 text-amber-400" />
            <span className="text-[9px] text-slate-400">Camera Disabled</span>
          </div>
        )}
        <div className="absolute top-1 left-1.5 flex items-center gap-1 bg-black/60 px-1.5 py-0.5 rounded text-[9px] font-mono text-slate-300">
          <span className={`w-1.5 h-1.5 rounded-full ${cameraStatus === 'CONNECTED' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
          {cameraStatus === 'CONNECTED' ? 'Camera Active' : 'Camera Off'}
        </div>
      </div>

      {/* Non-Accusatory Advisory Notice / Warning Modal */}
      {isWarningModalOpen && activeWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm">
          <Card className="max-w-md w-full p-6 space-y-5 border-amber-800/80 bg-slate-900 shadow-2xl">
            <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
              <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Assessment Advisory Notice</h3>
                <span className="text-[11px] font-mono text-slate-400">Notice ID: {activeWarning.id.slice(0, 8)}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/50 text-xs text-amber-200 leading-relaxed">
              {activeWarning.message}
            </div>

            <p className="text-[11px] text-slate-400">
              Please ensure you stay within the assessment window and keep your face visible in the camera frame to avoid further alerts.
            </p>

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <Button
                variant="primary"
                size="sm"
                onClick={handleAcknowledgeWarning}
              >
                I Understand & Acknowledge
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default StudentTestRoomPage;
