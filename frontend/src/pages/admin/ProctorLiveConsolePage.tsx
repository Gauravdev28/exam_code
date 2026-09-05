import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Shield,
  AlertTriangle,
  Pause,
  Play,
  Camera,
  XCircle,
  RefreshCw,
  Search,
  User,
  Clock,
  Radio,
  Send,
  X,
  Info
} from 'lucide-react';
import { InvigilationAPI } from '../../api/invigilation';
import { TriageCandidate, ProctorIntervention, ProctorChatMessage } from '../../types/invigilation';
import { RiskBand } from '../../types/proctoring';

export const ProctorLiveConsolePage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId: string }>();

  const [candidates, setCandidates] = useState<TriageCandidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<TriageCandidate | null>(null);
  const [interventions, setInterventions] = useState<ProctorIntervention[]>([]);
  const [chatMessages, setChatMessages] = useState<ProctorChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isWebSocketActive, setIsWebSocketActive] = useState(false);
  const [activeTab, setActiveTab] = useState<'chat' | 'audit'>('chat');

  // Modals
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [warningReason, setWarningReason] = useState('SUSPICIOUS_GAZE');
  const [warningMessage, setWarningMessage] = useState('');
  const [warningInternalNotes, setWarningInternalNotes] = useState('');

  const [showTerminateModal, setShowTerminateModal] = useState(false);
  const [terminateReason, setTerminateReason] = useState('UNAUTHORIZED_DEVICE');
  const [terminateJustification, setTerminateJustification] = useState('');
  const [terminateInternalNotes, setTerminateInternalNotes] = useState('');

  const [actionLoading, setActionLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Poll / Load Data
  const loadRoster = async () => {
    if (!assessmentId) return;
    try {
      const data = await InvigilationAPI.getLiveRoster(assessmentId);
      setCandidates(data.candidates);
      if (selectedCandidate) {
        const updated = data.candidates.find(c => c.attempt_id === selectedCandidate.attempt_id);
        if (updated) setSelectedCandidate(updated);
      } else if (data.candidates.length > 0) {
        setSelectedCandidate(data.candidates[0]);
      }
    } catch (err) {
      console.error('Failed to load roster:', err);
    }
  };

  const loadAttemptDetails = async (attemptId: string) => {
    try {
      const [history, chats] = await Promise.all([
        InvigilationAPI.getInterventionHistory(attemptId),
        InvigilationAPI.getChatHistory(attemptId),
      ]);
      setInterventions(history);
      setChatMessages(chats);
    } catch (err) {
      console.error('Failed to load attempt details:', err);
    }
  };

  useEffect(() => {
    loadRoster();
    const interval = setInterval(loadRoster, 5000); // 5s polling fallback

    // Attempt WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/proctor/assessments/${assessmentId}/`;

    try {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => setIsWebSocketActive(true);
      ws.onclose = () => setIsWebSocketActive(false);
      ws.onerror = () => setIsWebSocketActive(false);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'PROCTOR_EVENT') {
            loadRoster();
            if (selectedCandidate) {
              loadAttemptDetails(selectedCandidate.attempt_id);
            }
          }
        } catch (e) {
          // ignore parsing error
        }
      };
      wsRef.current = ws;
    } catch (e) {
      setIsWebSocketActive(false);
    }

    return () => {
      clearInterval(interval);
      if (wsRef.current) wsRef.current.close();
    };
  }, [assessmentId]);

  useEffect(() => {
    if (selectedCandidate) {
      loadAttemptDetails(selectedCandidate.attempt_id);
    }
  }, [selectedCandidate?.attempt_id]);

  // Actions
  const handleIssueWarning = async () => {
    if (!selectedCandidate || !warningMessage) return;
    setActionLoading(true);
    try {
      await InvigilationAPI.issueWarning(selectedCandidate.attempt_id, {
        reason_code: warningReason,
        message: warningMessage,
        internal_notes: warningInternalNotes,
      });
      setShowWarningModal(false);
      setWarningMessage('');
      setWarningInternalNotes('');
      loadAttemptDetails(selectedCandidate.attempt_id);
      loadRoster();
    } catch (err: any) {
      alert(err.response?.data?.message || 'Failed to issue warning');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTogglePause = async () => {
    if (!selectedCandidate) return;
    setActionLoading(true);
    try {
      if (selectedCandidate.is_paused) {
        await InvigilationAPI.resumeAttempt(selectedCandidate.attempt_id, { reason: 'Proctor resumed' });
      } else {
        await InvigilationAPI.pauseAttempt(selectedCandidate.attempt_id, { reason: 'Proctor paused' });
      }
      loadRoster();
      loadAttemptDetails(selectedCandidate.attempt_id);
    } catch (err: any) {
      alert(err.response?.data?.pause_limit || 'Failed to toggle pause');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRequestRoomScan = async () => {
    if (!selectedCandidate) return;
    setActionLoading(true);
    try {
      await InvigilationAPI.requestRoomScan(selectedCandidate.attempt_id, 'Please perform a 360 room scan.');
      loadAttemptDetails(selectedCandidate.attempt_id);
    } catch (err: any) {
      alert('Failed to request room scan');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTerminateAttempt = async () => {
    if (!selectedCandidate || !terminateJustification) return;
    setActionLoading(true);
    try {
      await InvigilationAPI.terminateAttempt(selectedCandidate.attempt_id, {
        reason_code: terminateReason,
        formal_justification: terminateJustification,
        internal_notes: terminateInternalNotes,
      });
      setShowTerminateModal(false);
      setTerminateJustification('');
      setTerminateInternalNotes('');
      loadRoster();
      loadAttemptDetails(selectedCandidate.attempt_id);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to terminate attempt');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCandidate || !chatInput.trim()) return;
    try {
      await InvigilationAPI.sendMessage(selectedCandidate.attempt_id, chatInput.trim());
      setChatInput('');
      loadAttemptDetails(selectedCandidate.attempt_id);
    } catch (err) {
      console.error('Failed to send message:', err);
    }
  };

  const getRiskBadge = (band: RiskBand) => {
    const colors: Record<RiskBand, string> = {
      CRITICAL: 'bg-red-500/20 text-red-400 border-red-500/40',
      HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/40',
      MEDIUM: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
      LOW: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
      NORMAL: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    };
    return (
      <span className={`px-2 py-0.5 text-xs font-semibold rounded border ${colors[band] || colors.NORMAL}`}>
        {band}
      </span>
    );
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const filteredCandidates = candidates.filter(
    c => c.student_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
         c.student_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header */}
      <header className="bg-slate-900/80 border-b border-slate-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-indigo-400" />
          <div>
            <h1 className="text-lg font-bold tracking-tight">Live Proctoring Console</h1>
            <p className="text-xs text-slate-400">Phase 10 Human Invigilation & Live Intervention Engine</p>
          </div>
        </div>

        {/* Advisory Warning */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-md text-amber-300 text-xs">
          <Info className="w-4 h-4 text-amber-400 flex-shrink-0" />
          <span>AI signals are advisory. All binding interventions require explicit human decision.</span>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${isWebSocketActive ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
            <span className="text-slate-400">{isWebSocketActive ? 'WebSocket LIVE' : '5s Polling (Degraded)'}</span>
          </div>
          <button
            onClick={loadRoster}
            className="p-1.5 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 transition"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Prioritized Triage Queue */}
        <div className="w-80 border-r border-slate-800 bg-slate-900/40 flex flex-col">
          <div className="p-3 border-b border-slate-800">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search candidates..."
                className="w-full bg-slate-950 border border-slate-800 rounded pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex justify-between items-center mt-2 text-xs text-slate-400">
              <span>Active Candidates: {candidates.length}</span>
              <span className="text-red-400 font-medium">Critical: {candidates.filter(c => c.risk_band === 'CRITICAL').length}</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
            {filteredCandidates.map(c => {
              const isSelected = selectedCandidate?.attempt_id === c.attempt_id;
              return (
                <div
                  key={c.attempt_id}
                  onClick={() => setSelectedCandidate(c)}
                  className={`p-3 cursor-pointer transition flex flex-col gap-1.5 ${
                    isSelected ? 'bg-indigo-950/40 border-l-4 border-indigo-500' : 'hover:bg-slate-800/40'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-200 truncate">{c.student_name}</span>
                    {getRiskBadge(c.risk_band)}
                  </div>
                  <div className="text-xs text-slate-400 truncate">{c.student_email}</div>
                  <div className="flex items-center justify-between text-xs text-slate-400 mt-1">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      {formatTimer(c.remaining_seconds)}
                    </span>
                    {c.is_paused ? (
                      <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 rounded text-2xs font-semibold">
                        PAUSED
                      </span>
                    ) : (
                      <span className="text-2xs text-emerald-400 font-medium">IN PROGRESS</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Center: Selected Candidate & Live Keyframe */}
        <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
          {selectedCandidate ? (
            <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
              {/* Candidate Info Header */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                    {selectedCandidate.student_name}
                    {getRiskBadge(selectedCandidate.risk_band)}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {selectedCandidate.student_email} • Roll: {selectedCandidate.roll_number || 'N/A'} • Risk Score: {selectedCandidate.risk_score.toFixed(1)}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-xs text-slate-400">Remaining Time</div>
                  <div className="text-xl font-mono font-bold text-indigo-400">
                    {formatTimer(selectedCandidate.remaining_seconds)}
                  </div>
                </div>
              </div>

              {/* Live Simulated Keyframe Display */}
              <div className="relative aspect-video bg-slate-900 border border-slate-800 rounded-lg overflow-hidden flex items-center justify-center shadow-lg">
                <div className="absolute top-3 left-3 flex items-center gap-2 px-2.5 py-1 bg-slate-950/80 backdrop-blur rounded border border-slate-700 text-xs">
                  <Radio className="w-3.5 h-3.5 text-red-500 animate-pulse" />
                  <span className="font-mono">KEYFRAME STREAM • 0.2 FPS</span>
                </div>

                <div className="text-center p-8">
                  <div className="w-20 h-20 mx-auto rounded-full bg-slate-800 flex items-center justify-center text-slate-400 mb-3 border border-slate-700">
                    <User className="w-10 h-10" />
                  </div>
                  <p className="text-sm font-medium text-slate-300">{selectedCandidate.student_name}</p>
                  <p className="text-xs text-slate-400 mt-1">Transient proctor stream rendered directly in browser memory</p>
                </div>

                {selectedCandidate.is_paused && (
                  <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center">
                    <Pause className="w-12 h-12 text-amber-400 mb-2" />
                    <span className="text-base font-bold text-amber-300">ATTEMPT TEMPORARILY PAUSED</span>
                    <span className="text-xs text-slate-400 mt-1">Countdown timer suspended</span>
                  </div>
                )}
              </div>

              {/* Action Toolbar */}
              <div className="grid grid-cols-4 gap-3">
                <button
                  onClick={() => setShowWarningModal(true)}
                  disabled={actionLoading}
                  className="flex items-center justify-center gap-2 py-2.5 px-4 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded text-xs transition shadow-sm"
                >
                  <AlertTriangle className="w-4 h-4" />
                  Issue Warning
                </button>

                <button
                  onClick={handleTogglePause}
                  disabled={actionLoading}
                  className={`flex items-center justify-center gap-2 py-2.5 px-4 font-semibold rounded text-xs transition shadow-sm ${
                    selectedCandidate.is_paused
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                      : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                  }`}
                >
                  {selectedCandidate.is_paused ? (
                    <>
                      <Play className="w-4 h-4" />
                      Resume Attempt
                    </>
                  ) : (
                    <>
                      <Pause className="w-4 h-4" />
                      Pause (Max 15m)
                    </>
                  )}
                </button>

                <button
                  onClick={handleRequestRoomScan}
                  disabled={actionLoading}
                  className="flex items-center justify-center gap-2 py-2.5 px-4 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold rounded text-xs transition"
                >
                  <Camera className="w-4 h-4" />
                  Request Room Scan
                </button>

                <button
                  onClick={() => setShowTerminateModal(true)}
                  disabled={actionLoading}
                  className="flex items-center justify-center gap-2 py-2.5 px-4 bg-red-600 hover:bg-red-500 text-white font-semibold rounded text-xs transition shadow-sm"
                >
                  <XCircle className="w-4 h-4" />
                  Terminate Attempt
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
              Select a candidate from the triage list to inspect and intervene.
            </div>
          )}
        </div>

        {/* Right: Bilateral Chat & Audit Drawer */}
        <div className="w-96 border-l border-slate-800 bg-slate-900/40 flex flex-col">
          <div className="flex border-b border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 py-3 text-center font-semibold border-b-2 transition ${
                activeTab === 'chat'
                  ? 'border-indigo-500 text-indigo-400 bg-slate-900/60'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Candidate Chat
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className={`flex-1 py-3 text-center font-semibold border-b-2 transition ${
                activeTab === 'audit'
                  ? 'border-indigo-500 text-indigo-400 bg-slate-900/60'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              Audit History ({interventions.length})
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {activeTab === 'chat' ? (
              chatMessages.length === 0 ? (
                <div className="text-center text-slate-500 text-xs py-8">No messages exchanged yet.</div>
              ) : (
                chatMessages.map(msg => (
                  <div
                    key={msg.id}
                    className={`flex flex-col max-w-[85%] ${
                      msg.sender_role === 'PROCTOR' || msg.sender_role === 'ADMIN'
                        ? 'ml-auto items-end'
                        : 'mr-auto items-start'
                    }`}
                  >
                    <span className="text-2xs text-slate-500 mb-0.5">{msg.sender_email}</span>
                    <div
                      className={`px-3 py-2 rounded-lg text-xs ${
                        msg.sender_role === 'PROCTOR' || msg.sender_role === 'ADMIN'
                          ? 'bg-indigo-600 text-white rounded-br-none'
                          : 'bg-slate-800 text-slate-200 rounded-bl-none'
                      }`}
                    >
                      {msg.message_text}
                    </div>
                  </div>
                ))
              )
            ) : (
              interventions.map(it => (
                <div key={it.id} className="p-2.5 bg-slate-950/60 border border-slate-800 rounded text-xs space-y-1">
                  <div className="flex items-center justify-between font-semibold">
                    <span className="text-indigo-400">{it.event_type}</span>
                    <span className="text-2xs text-slate-500">{new Date(it.issued_at).toLocaleTimeString()}</span>
                  </div>
                  {it.reason_text && <p className="text-slate-300">{it.reason_text}</p>}
                  {it.internal_notes && (
                    <div className="p-1.5 bg-amber-500/10 border border-amber-500/20 rounded text-2xs text-amber-300">
                      <strong>Internal Note:</strong> {it.internal_notes}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {activeTab === 'chat' && (
            <form onSubmit={handleSendChat} className="p-3 border-t border-slate-800 flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                placeholder="Type message to candidate..."
                className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                className="p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs transition"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Warning Modal */}
      {showWarningModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                Issue Candidate Warning
              </h3>
              <button onClick={() => setShowWarningModal(false)} className="text-slate-400 hover:text-slate-200">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Reason Code</label>
                <select
                  value={warningReason}
                  onChange={e => setWarningReason(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="SUSPICIOUS_GAZE">Suspicious Gaze / Looking Away</option>
                  <option value="MULTIPLE_FACES">Multiple Faces Detected</option>
                  <option value="VOICE_DETECTED">Voice / Acoustic Activity</option>
                  <option value="UNAUTHORIZED_MATERIAL">Unauthorized Materials</option>
                  <option value="OTHER">Other Compliance Anomaly</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Warning Message (Candidate Visible)</label>
                <textarea
                  value={warningMessage}
                  onChange={e => setWarningMessage(e.target.value)}
                  placeholder="Please maintain eye contact with the screen."
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Internal Investigation Remarks (Excluded from DSAR)</label>
                <textarea
                  value={warningInternalNotes}
                  onChange={e => setWarningInternalNotes(e.target.value)}
                  placeholder="Notes for proctoring review team..."
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowWarningModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition"
              >
                Cancel
              </button>
              <button
                onClick={handleIssueWarning}
                disabled={actionLoading || !warningMessage.trim()}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded text-xs transition disabled:opacity-50"
              >
                Issue Warning
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Termination Modal */}
      {showTerminateModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-red-500/40 rounded-lg max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-red-400 flex items-center gap-2">
                <XCircle className="w-5 h-5" />
                Terminate Attempt With Cause
              </h3>
              <button onClick={() => setShowTerminateModal(false)} className="text-slate-400 hover:text-slate-200">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-300">
              <strong>CRITICAL ACTION:</strong> This will transition the test attempt to CANCELLED and trigger Phase 8 academic finalization. This action is irreversible.
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Reason Code</label>
                <select
                  value={terminateReason}
                  onChange={e => setTerminateReason(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-red-500"
                >
                  <option value="UNAUTHORIZED_DEVICE">Secondary Computer / Phone</option>
                  <option value="IMPERSONATION">Impersonation / Alternate Candidate</option>
                  <option value="COLLUSION">Third-Party Assistance / Collusion</option>
                  <option value="REFUSAL_TO_COOPERATE">Refusal to Perform Room Scan</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Formal Justification (Official Record)</label>
                <textarea
                  value={terminateJustification}
                  onChange={e => setTerminateJustification(e.target.value)}
                  placeholder="State detailed factual findings justifying disqualification..."
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2.5 text-xs text-slate-200 focus:outline-none focus:border-red-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Internal Investigation Remarks</label>
                <textarea
                  value={terminateInternalNotes}
                  onChange={e => setTerminateInternalNotes(e.target.value)}
                  placeholder="Internal audit notes..."
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2.5 text-xs text-slate-200 focus:outline-none focus:border-red-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowTerminateModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs transition"
              >
                Cancel
              </button>
              <button
                onClick={handleTerminateAttempt}
                disabled={actionLoading || !terminateJustification.trim()}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-semibold rounded text-xs transition disabled:opacity-50"
              >
                Confirm Termination
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
