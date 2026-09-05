import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { changeUserPassword } from '../../api/students';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { KeyRound, Lock, AlertCircle } from 'lucide-react';

export const ForcePasswordChangeModal: React.FC = () => {
  const { user, refreshUser, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!user || !user.first_login_required) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (newPassword !== confirmPassword) {
      setErrorMessage('New password and confirmation password do not match.');
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage('New password must be at least 8 characters long.');
      return;
    }

    if (newPassword === currentPassword) {
      setErrorMessage('New password must be different from your current temporary password.');
      return;
    }

    setIsLoading(true);
    try {
      await changeUserPassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      await refreshUser();
    } catch (err: any) {
      const msg =
        err.error?.details?.new_password?.[0] ||
        err.error?.details?.current_password?.[0] ||
        err.error?.message ||
        err.message ||
        'Failed to change password. Please check your credentials.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const isStudent = user?.role === 'STUDENT';
  const isAdmin = user?.role === 'ADMIN';
  const isProctor = user?.role === 'PROCTOR';

  const roleTitle = "First Login: Password Reset Required";
  const roleExplanation = isStudent
    ? "Your initial temporary password is your roll number. Replace it before continuing."
    : isAdmin
    ? "Your temporary administrator password must be replaced before continuing."
    : isProctor
    ? "Your temporary invigilator password must be replaced before continuing."
    : "For academic integrity and account security, you must replace your initial temporary password before continuing.";

  const currentPasswordLabel = isStudent
    ? <>Current Temporary Password <span className="text-slate-500 font-normal">(Your Roll Number)</span></>
    : <>Current Temporary Password</>;

  const currentPasswordPlaceholder = isStudent
    ? "Initial Roll Number"
    : isAdmin
    ? "Temporary Administrator Password"
    : isProctor
    ? "Temporary Proctor Password"
    : "Temporary Password";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
      <Card className="max-w-md w-full p-8 border border-slate-200 shadow-xl space-y-6 bg-white">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-700 border border-amber-200 flex items-center justify-center mx-auto">
            <KeyRound className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">{roleTitle}</h2>
          <p className="text-xs text-slate-500">
            {roleExplanation}
          </p>
        </div>

        {errorMessage && (
          <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="block text-xs font-semibold text-slate-700">
              {currentPasswordLabel}
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder={currentPasswordPlaceholder}
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-semibold text-slate-700">
              New Personal Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-semibold text-slate-700">
              Confirm New Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="pt-2 space-y-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isLoading}
              className="w-full"
            >
              Update Password & Unlock Account
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={logout}
              className="w-full text-slate-500 hover:text-rose-600 text-xs"
            >
              Cancel & Sign Out
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default ForcePasswordChangeModal;
