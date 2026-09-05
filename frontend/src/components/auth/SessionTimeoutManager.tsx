import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { getSessionStatus, refreshSession } from '../../api/auth';
import { Clock, AlertTriangle, ShieldCheck, LogOut } from 'lucide-react';

const THROTTLE_REFRESH_MS = 60 * 1000; // Call server refresh at most once every 60 seconds
const STATUS_CHECK_INTERVAL_MS = 25 * 1000; // Check server session status every 25 seconds

export const SessionTimeoutManager: React.FC = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [showWarningModal, setShowWarningModal] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(120);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const lastServerRefreshRef = useRef<number>(Date.now());
  const countdownIntervalRef = useRef<any>(null);

  // Check if current route is an active student assessment room
  const isAssessmentRoute = location.pathname.startsWith('/student/room/');

  // Handler to extend the session
  const handleExtendSession = useCallback(async () => {
    try {
      setIsRefreshing(true);
      await refreshSession();
      lastServerRefreshRef.current = Date.now();
      setShowWarningModal(false);
      try {
        localStorage.setItem('cg_last_activity', Date.now().toString());
      } catch {}
    } catch (err) {
      console.warn('Failed to refresh session:', err);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  const handleManualLogout = useCallback(async () => {
    setShowWarningModal(false);
    await logout();
    navigate('/login');
  }, [logout, navigate]);

  // Handle session expiration
  const handleSessionExpired = useCallback(() => {
    setShowWarningModal(false);
    logout().catch(() => {});
    navigate('/login?reason=inactivity');
  }, [logout, navigate]);

  // Check server session status
  const checkStatus = useCallback(async () => {
    if (!isAuthenticated || !user) return;

    // Active student assessments are strictly exempt from idle logout
    if (isAssessmentRoute) {
      if (showWarningModal) setShowWarningModal(false);
      return;
    }

    try {
      const res = await getSessionStatus();
      if (!res.data) return;

      const data = res.data;

      // If server reports student is in an active assessment, never warn or logout
      if (data.is_in_active_assessment) {
        if (showWarningModal) setShowWarningModal(false);
        return;
      }

      if (data.is_idle_expired) {
        handleSessionExpired();
        return;
      }

      const remaining = data.time_remaining_seconds;
      const warningThreshold = data.warning_threshold_seconds || 120;

      if (remaining <= warningThreshold && remaining > 0) {
        setSecondsRemaining(Math.max(1, Math.round(remaining)));
        setShowWarningModal(true);
      } else if (remaining > warningThreshold) {
        setShowWarningModal(false);
      }
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.status_code === 401) {
        handleSessionExpired();
      }
    }
  }, [isAuthenticated, user, isAssessmentRoute, showWarningModal, handleSessionExpired]);

  // Throttled client activity listener
  useEffect(() => {
    if (!isAuthenticated || isAssessmentRoute) return;

    const handleUserInteraction = () => {
      const now = Date.now();
      try {
        localStorage.setItem('cg_last_activity', now.toString());
      } catch {}

      // If warning modal is not shown and throttle elapsed, refresh on server
      if (!showWarningModal && now - lastServerRefreshRef.current >= THROTTLE_REFRESH_MS) {
        lastServerRefreshRef.current = now;
        refreshSession().catch(() => {});
      }
    };

    const events = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart'];
    const throttledHandler = () => {
      handleUserInteraction();
    };

    events.forEach((evt) => window.addEventListener(evt, throttledHandler, { passive: true }));

    // Storage event for multi-tab activity synchronization
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'cg_last_activity' && e.newValue) {
        lastServerRefreshRef.current = parseInt(e.newValue, 10) || Date.now();
        if (showWarningModal) {
          setShowWarningModal(false);
        }
      }
    };
    window.addEventListener('storage', handleStorage);

    return () => {
      events.forEach((evt) => window.removeEventListener(evt, throttledHandler));
      window.removeEventListener('storage', handleStorage);
    };
  }, [isAuthenticated, isAssessmentRoute, showWarningModal]);

  // Periodic server check polling
  useEffect(() => {
    if (!isAuthenticated || isAssessmentRoute) return;

    checkStatus();
    const interval = setInterval(checkStatus, STATUS_CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isAuthenticated, isAssessmentRoute, checkStatus]);

  // Countdown timer when warning modal is active
  useEffect(() => {
    if (!showWarningModal) {
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
      }
      return;
    }

    countdownIntervalRef.current = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(countdownIntervalRef.current);
          handleSessionExpired();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
      }
    };
  }, [showWarningModal, handleSessionExpired]);

  if (!showWarningModal || isAssessmentRoute) {
    return null;
  }

  const minutes = Math.floor(secondsRemaining / 60);
  const seconds = secondsRemaining % 60;
  const formattedTime = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="inactivity-warning-title"
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-amber-200 max-w-md w-full overflow-hidden text-slate-900">
        <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-4 flex items-center gap-3 text-white">
          <AlertTriangle className="h-6 w-6 shrink-0" />
          <h3 id="inactivity-warning-title" className="text-lg font-bold">
            Session Inactivity Warning
          </h3>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-sm text-slate-600 leading-relaxed">
            You have been inactive for a while. For security reasons, your session will automatically expire in:
          </p>

          <div className="flex items-center justify-center gap-2 py-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900">
            <Clock className="h-6 w-6 text-amber-600 animate-pulse" />
            <span className="text-3xl font-extrabold tracking-wider font-mono">
              {formattedTime}
            </span>
          </div>

          <p className="text-xs text-slate-700">
            Click <strong className="text-slate-900">Continue Session</strong> to keep working, or click Log Out if you are finished.
          </p>

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleExtendSession}
              disabled={isRefreshing}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-xl shadow-sm transition disabled:opacity-50"
            >
              <ShieldCheck className="h-4 w-4" />
              {isRefreshing ? 'Refreshing...' : 'Continue Session'}
            </button>
            <button
              onClick={handleManualLogout}
              className="flex items-center justify-center gap-1.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-semibold rounded-xl transition"
            >
              <LogOut className="h-4 w-4" />
              Log Out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
