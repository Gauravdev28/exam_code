import React, { useState } from 'react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { KeyRound, ShieldAlert, Copy, Check, Eye, EyeOff, AlertCircle, Lock, Wand2 } from 'lucide-react';
import { ResetPasswordPayload } from '../../types/admin';

interface ResetPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetName: string;
  targetIdentity: string;
  targetEmail: string;
  targetRole: 'Student' | 'Administrator';
  onReset: (payload: ResetPasswordPayload) => Promise<void>;
}

function generateSecurePassword(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%&*+?';
  const array = new Uint32Array(16);
  crypto.getRandomValues(array);
  let pwd = '';
  for (let i = 0; i < 16; i++) {
    pwd += chars[array[i] % chars.length];
  }
  if (
    /[a-z]/.test(pwd) &&
    /[A-Z]/.test(pwd) &&
    /[0-9]/.test(pwd) &&
    /[!@#$%&*+?]/.test(pwd)
  ) {
    return pwd;
  }
  return generateSecurePassword();
}

export const ResetPasswordModal: React.FC<ResetPasswordModalProps> = ({
  isOpen,
  onClose,
  targetName,
  targetIdentity,
  targetEmail,
  targetRole,
  onReset,
}) => {
  const [reason, setReason] = useState('');
  const [temporaryPassword, setTemporaryPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [wasGenerated, setWasGenerated] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState(false);
  const [isRevealed, setIsRevealed] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  if (!isOpen) return null;

  const handleGeneratePassword = () => {
    const generated = generateSecurePassword();
    setTemporaryPassword(generated);
    setConfirmPassword(generated);
    setWasGenerated(true);
    setShowPassword(true);
    setError(null);
  };

  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!reason.trim()) {
      setError('Please provide an administrative reason for resetting the password.');
      return;
    }

    if (!temporaryPassword) {
      setError('Temporary password is required.');
      return;
    }

    if (temporaryPassword.length < 8) {
      setError('Temporary password must be at least 8 characters long.');
      return;
    }

    if (temporaryPassword !== confirmPassword) {
      setError('Temporary password and confirmation do not match.');
      return;
    }

    setIsLoading(true);

    try {
      await onReset({
        reason: reason.trim(),
        temporary_password: temporaryPassword,
        confirm_temporary_password: confirmPassword,
      });
      setIsCompleted(true);
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message ||
        err.error?.message ||
        err.message ||
        'Failed to reset password. Please verify permissions.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = () => {
    if (temporaryPassword) {
      navigator.clipboard.writeText(temporaryPassword);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2500);
    }
  };

  const handleClose = () => {
    setReason('');
    setTemporaryPassword('');
    setConfirmPassword('');
    setShowPassword(false);
    setWasGenerated(false);
    setError(null);
    setIsCompleted(false);
    setIsRevealed(false);
    setIsCopied(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
      <Card className="max-w-md w-full p-6 border border-slate-200 shadow-2xl bg-white space-y-5 rounded-2xl">
        {/* Step 1: Confirmation & Password Entry Form */}
        {!isCompleted ? (
          <>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 border border-amber-200 flex items-center justify-center flex-shrink-0">
                <KeyRound className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Reset {targetRole} Password</h3>
                <p className="text-xs text-slate-500">
                  Set or generate a single-use temporary password
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Account:</span>
                <span className="font-semibold text-slate-800">{targetName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Identity ID:</span>
                <span className="font-mono text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">{targetIdentity}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Email:</span>
                <span className="text-slate-700 font-mono">{targetEmail}</span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold">Security Safeguards:</p>
                <ul className="list-disc pl-4 space-y-0.5 text-amber-700">
                  <li>Active authenticated sessions for this account will be revoked immediately.</li>
                  <li>User will be required to choose a new password upon next sign in.</li>
                  <li>This administrative action is recorded in the immutable security audit trail.</li>
                </ul>
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleConfirmReset} className="space-y-3.5">
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-700">
                  Reason for Password Reset <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. User forgot password before exam session"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-slate-700">
                    Temporary Password <span className="text-rose-500">*</span>
                  </label>
                  <button
                    type="button"
                    onClick={handleGeneratePassword}
                    className="text-[11px] text-emerald-700 hover:text-emerald-800 font-semibold flex items-center gap-1 transition-colors"
                  >
                    <Wand2 className="w-3 h-3" />
                    Generate Secure Password
                  </button>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    minLength={8}
                    placeholder="Enter temporary password"
                    value={temporaryPassword}
                    onChange={(e) => {
                      setTemporaryPassword(e.target.value);
                      setWasGenerated(false);
                    }}
                    className="w-full px-3 py-2 pr-10 rounded-lg border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-semibold text-slate-700">
                  Confirm Temporary Password <span className="text-rose-500">*</span>
                </label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={8}
                  placeholder="Re-enter temporary password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleClose}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isLoading}
                  className="bg-amber-600 hover:bg-amber-700 text-white"
                >
                  Reset Password
                </Button>
              </div>
            </form>
          </>
        ) : wasGenerated ? (
          /* Step 2A: One-Time Reveal Dialog for Generated Passwords */
          <>
            <div className="text-center space-y-2">
              <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center mx-auto">
                <Lock className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Password Reset Completed</h3>
              <p className="text-xs text-slate-500">
                A single-use temporary password has been generated for <span className="font-semibold text-slate-700">{targetEmail}</span>.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span className="font-medium">
                Save this credential securely. It will <strong>NOT</strong> be shown again.
              </span>
            </div>

            {/* Credential Box */}
            <div className="p-4 rounded-xl bg-slate-900 text-white space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Temporary Credential</span>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30">
                  Single-Use Required
                </span>
              </div>

              <div className="flex items-center justify-between gap-3 bg-slate-800/80 px-3 py-2.5 rounded-lg border border-slate-700">
                <span className="font-mono text-sm tracking-wider font-semibold text-emerald-400 select-all">
                  {isRevealed ? temporaryPassword : '••••••••••••••••'}
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setIsRevealed(!isRevealed)}
                    className="p-1.5 text-slate-400 hover:text-white rounded transition-colors"
                    title={isRevealed ? 'Hide Password' : 'Show Password'}
                  >
                    {isRevealed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="p-1.5 text-slate-400 hover:text-white rounded transition-colors"
                    title="Copy to Clipboard"
                  >
                    {isCopied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="text-[11px] text-slate-400 leading-relaxed">
                Upon sign-in, the user will be automatically required to configure a permanent secure password.
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleClose}
                className="w-full bg-slate-900 hover:bg-slate-800 text-white"
              >
                Done (Dismiss)
              </Button>
            </div>
          </>
        ) : (
          /* Step 2B: Confirmation for Manually Entered Passwords (Do not show password again) */
          <>
            <div className="text-center space-y-2">
              <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center mx-auto">
                <Check className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">Temporary Password Set</h3>
              <p className="text-xs text-slate-600">
                Temporary password has been successfully configured for <span className="font-semibold text-slate-800">{targetEmail}</span>.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-2">
              <p>
                <strong>Security note:</strong> The previous password has been invalidated, active sessions were terminated, and the user will be prompted to choose a new password upon their next sign in.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleClose}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                Done
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
};
