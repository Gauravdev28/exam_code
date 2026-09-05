import React, { useState, useEffect } from 'react';
import { Administrator, ResetPasswordPayload } from '../../types/admin';
import { AdminAPI } from '../../api/admin';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { ResetPasswordModal } from './ResetPasswordModal';
import {
  ShieldCheck,
  AlertCircle,
  X,
  Power,
  Lock,
  KeyRound,
  Trash2,
  ShieldAlert,
} from 'lucide-react';

interface AdminDetailsModalProps {
  admin: Administrator | null;
  isOpen: boolean;
  currentUserIsPrimary: boolean;
  currentUserId?: string;
  onClose: () => void;
  onUpdate: (updated: Administrator) => void;
  onDelete: (adminId: string) => void;
}

export const AdminDetailsModal: React.FC<AdminDetailsModalProps> = ({
  admin,
  isOpen,
  currentUserIsPrimary,
  currentUserId,
  onClose,
  onUpdate,
  onDelete,
}) => {
  const [currentAdmin, setCurrentAdmin] = useState<Administrator | null>(admin);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  useEffect(() => {
    setCurrentAdmin(admin);
    if (admin) {
      setErrorMessage(null);
      setIsDeleteConfirmOpen(false);
    }
  }, [admin]);

  if (!isOpen || !currentAdmin) return null;

  const isPrimary = currentAdmin.admin_id === 'EUAD-GAURAV-099' || currentAdmin.is_primary;
  const isCurrent = currentAdmin.id === currentUserId;
  const canModify = currentUserIsPrimary || isCurrent;
  const canDeleteOrDeactivate = currentUserIsPrimary && !isPrimary && !isCurrent;

  const handleToggleStatus = async () => {
    if (isPrimary) {
      setErrorMessage('The Primary Administrator account cannot be deactivated.');
      return;
    }
    if (isCurrent) {
      setErrorMessage('You cannot deactivate your own administrator account.');
      return;
    }

    const isDeactivating = currentAdmin.is_active;
    const promptMsg = isDeactivating
      ? `Reason for deactivating administrator ${currentAdmin.email}:`
      : `Reason for activating administrator ${currentAdmin.email}:`;
    const reason = window.prompt(promptMsg, isDeactivating ? 'Administrative suspension' : 'Reinstated account');
    if (reason === null) return;

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const updated = await AdminAPI.toggleAdministratorStatus(currentAdmin.id, !currentAdmin.is_active, reason);
      setCurrentAdmin(updated);
      onUpdate(updated);
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.error?.message ||
        err.error?.message ||
        err.message ||
        'Failed to toggle administrator status.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteAdmin = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await AdminAPI.deleteAdministrator(currentAdmin.id);
      setIsDeleteConfirmOpen(false);
      onDelete(currentAdmin.id);
      onClose();
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        err.error?.message ||
        err.message ||
        'Failed to delete administrator account.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPasswordAction = async (payload: ResetPasswordPayload): Promise<void> => {
    await AdminAPI.resetAdminPassword(currentAdmin.id, payload);
    setCurrentAdmin((prev) => (prev ? { ...prev, first_login_required: true } : null));
    onUpdate({ ...currentAdmin, first_login_required: true });
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return 'Never';
    try {
      return new Date(isoString).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
        <Card className="max-w-lg w-full p-6 space-y-6 bg-white border border-slate-200 shadow-2xl relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>

          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-200 pb-4">
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl border ${
                isPrimary
                  ? 'bg-purple-50 text-purple-700 border-purple-200'
                  : 'bg-slate-50 text-slate-700 border-slate-200'
              }`}>
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900 font-mono">{currentAdmin.admin_id}</h3>
                  {isPrimary ? (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-bold border border-purple-200 uppercase tracking-wide">
                      PRIMARY / PROTECTED
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-bold border border-slate-200 uppercase tracking-wide">
                      ADMINISTRATOR
                    </span>
                  )}
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200 uppercase tracking-wide flex items-center gap-1">
                    <Lock className="w-2.5 h-2.5" />
                    IMMUTABLE IDENTITY
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-medium">{currentAdmin.display_name}</p>
              </div>
            </div>
            <Badge variant={currentAdmin.is_active ? 'success' : 'danger'}>
              {currentAdmin.is_active ? 'ACTIVE' : 'DISABLED'}
            </Badge>
          </div>

          {errorMessage && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Details Read-Only View */}
          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between text-slate-600">
              <span className="flex items-center gap-1.5 font-medium">
                <Lock className="w-3.5 h-3.5 text-slate-400" />
                Administrator identity fields (UUID, Admin ID, Email, Display Name, Role) are permanently immutable.
              </span>
            </div>

            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-700 font-semibold">Display Name</span>
              <span className="text-slate-900 font-bold">{currentAdmin.display_name}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-700 font-semibold">Email Address</span>
              <span className="text-slate-900 font-mono font-medium">{currentAdmin.email}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-700 font-semibold">Role & Authority</span>
              <span className="text-slate-900 font-semibold font-mono">
                {isPrimary ? 'PRIMARY ADMINISTRATOR' : 'SECONDARY ADMINISTRATOR'}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100 items-center">
              <span className="text-slate-700 font-semibold">First Login Password Status</span>
              <span className={currentAdmin.first_login_required ? 'text-amber-900 font-bold bg-amber-50 px-2 py-0.5 rounded border border-amber-300' : 'text-slate-700 font-semibold bg-slate-100 px-2 py-0.5 rounded border border-slate-200'}>
                {currentAdmin.first_login_required ? 'REQUIRED (PENDING)' : 'SATISFIED'}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-700 font-semibold">Created At</span>
              <span className="text-slate-900 font-mono font-medium">{formatDate(currentAdmin.created_at)}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100">
              <span className="text-slate-700 font-semibold">Last Login</span>
              <span className="text-slate-900 font-mono font-medium">{formatDate(currentAdmin.last_login)}</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-3 flex flex-wrap items-center justify-between border-t border-slate-200 gap-2">
            <div className="flex items-center gap-2">
              {canDeleteOrDeactivate && (
                <Button
                  variant={currentAdmin.is_active ? 'danger' : 'primary'}
                  size="sm"
                  onClick={handleToggleStatus}
                  isLoading={isLoading}
                >
                  <Power className="w-3.5 h-3.5 mr-1.5" />
                  {currentAdmin.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              )}

              {canModify && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsResetModalOpen(true)}
                  className="text-amber-700 border-amber-300 hover:bg-amber-50"
                >
                  <KeyRound className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
                  Reset Password
                </Button>
              )}

              {canDeleteOrDeactivate && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsDeleteConfirmOpen(true)}
                  className="text-rose-700 border-rose-300 hover:bg-rose-50"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5 text-rose-600" />
                  Delete
                </Button>
              )}
            </div>

            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </Card>
      </div>

      {/* Delete Confirmation Modal */}
      {isDeleteConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <Card className="max-w-md w-full p-6 space-y-4 bg-white border border-rose-200 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900">Delete Administrator</h4>
                <p className="text-xs text-slate-500 font-mono">{currentAdmin.admin_id} ({currentAdmin.email})</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to permanently delete this administrator account? All active sessions will be invalidated immediately. Historical audit trail records will be preserved with immutable identity snapshots.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsDeleteConfirmOpen(false)}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteAdmin}
                isLoading={isLoading}
              >
                Confirm Delete
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Reset Password Modal */}
      <ResetPasswordModal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        targetName={currentAdmin.display_name}
        targetIdentity={currentAdmin.admin_id}
        targetEmail={currentAdmin.email}
        targetRole="Administrator"
        onReset={handleResetPasswordAction}
      />
    </>
  );
};

export default AdminDetailsModal;
