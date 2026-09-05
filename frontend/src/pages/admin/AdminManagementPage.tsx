import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { AdminAPI } from '../../api/admin';
import { Administrator, CreateAdminPayload, ResetPasswordPayload } from '../../types/admin';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { ResetPasswordModal } from '../../components/admin/ResetPasswordModal';
import { SecurityAuditTab } from '../../components/admin/SecurityAuditTab';
import { AdminDetailsModal } from '../../components/admin/AdminDetailsModal';
import {
  ShieldCheck,
  Plus,
  Search,
  UserCheck,
  AlertCircle,
  X,
  Lock,
  Mail,
  Shield,
  CheckCircle2,
  Power,
  KeyRound,
  History,
  Wand2,
  Eye,
  EyeOff,
  User,
  Trash2,
  ShieldAlert,
} from 'lucide-react';

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

export const AdminManagementPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'directory' | 'audit'>('directory');
  const [admins, setAdmins] = useState<Administrator[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modal State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [resetTargetAdmin, setResetTargetAdmin] = useState<Administrator | null>(null);
  const [selectedAdminForDetails, setSelectedAdminForDetails] = useState<Administrator | null>(null);
  const [deleteTargetAdmin, setDeleteTargetAdmin] = useState<Administrator | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Bulk Selection State
  const [selectedAdminIds, setSelectedAdminIds] = useState<Set<string>>(new Set());
  const [isBulkDeleteModalOpen, setIsBulkDeleteModalOpen] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [bulkDeleteError, setBulkDeleteError] = useState<string | null>(null);
  const [bulkDeleteResult, setBulkDeleteResult] = useState<{
    total: number;
    success_count: number;
    failure_count: number;
    results: Array<{ id: string; email?: string; admin_id?: string; success: boolean; error?: string }>;
  } | null>(null);

  const [formData, setFormData] = useState<CreateAdminPayload>({
    email: '',
    display_name: '',
    password: '',
    confirm_password: '',
    is_active: true,
  });
  const [showCreatePassword, setShowCreatePassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  useEffect(() => {
    loadAdmins();
  }, []);

  const loadAdmins = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await AdminAPI.getAdministrators();
      setAdmins(res.administrators || []);
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.error?.message ||
        err.error?.message ||
        err.message ||
        'Failed to load administrator accounts.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateAdminPassword = () => {
    const pwd = generateSecurePassword();
    setFormData((prev) => ({
      ...prev,
      password: pwd,
      confirm_password: pwd,
    }));
    setShowCreatePassword(true);
    setModalError(null);
  };

  const handleCreateAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);

    if (formData.password !== formData.confirm_password) {
      setModalError('Password and confirmation do not match.');
      return;
    }

    if (formData.password.length < 8) {
      setModalError('Password must be at least 8 characters long.');
      return;
    }

    setIsSubmitting(true);

    try {
      await AdminAPI.createAdministrator(formData);
      setIsCreateModalOpen(false);
      setFormData({
        email: '',
        display_name: '',
        password: '',
        confirm_password: '',
        is_active: true,
      });
      setShowCreatePassword(false);
      setSuccessMessage('Administrator account created successfully.');
      await loadAdmins();
    } catch (err: any) {
      setModalError(
        err.response?.data?.error?.message ||
        err.error?.message ||
        err.message ||
        'Failed to create administrator account.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleStatus = async (admin: Administrator) => {
    if (admin.id === user?.id) {
      setErrorMessage('You cannot deactivate your own administrator account.');
      return;
    }

    if (admin.admin_id === 'EUAD-GAURAV-099') {
      setErrorMessage('The Primary Administrator account cannot be deactivated.');
      return;
    }

    const isDeactivating = admin.is_active;
    const reason = window.prompt(
      isDeactivating
        ? `Reason for deactivating administrator ${admin.email}:`
        : `Reason for activating administrator ${admin.email}:`,
      isDeactivating ? 'Administrative suspension' : 'Reinstated account'
    );
    if (reason === null) return;

    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const updated = await AdminAPI.toggleAdministratorStatus(admin.id, !admin.is_active, reason);
      setAdmins((prev) =>
        prev.map((a) => (a.id === admin.id ? { ...a, is_active: updated.is_active } : a))
      );
      setSuccessMessage(`Administrator ${admin.email} is now ${updated.is_active ? 'Active' : 'Disabled'}.`);
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.error?.message ||
        err.error?.message ||
        err.message ||
        'Failed to update administrator status.'
      );
    }
  };

  const handleResetAdminPassword = async (payload: ResetPasswordPayload): Promise<void> => {
    if (!resetTargetAdmin) throw new Error('No administrator selected.');
    await AdminAPI.resetAdminPassword(resetTargetAdmin.id, payload);
    setSuccessMessage(`Password reset successfully for ${resetTargetAdmin.display_name || resetTargetAdmin.email}.`);
    loadAdmins();
  };

  const handleDeleteSecondaryAdmin = async () => {
    if (!deleteTargetAdmin) return;
    setIsDeleting(true);
    setErrorMessage(null);
    try {
      await AdminAPI.deleteAdministrator(deleteTargetAdmin.id);
      setAdmins((prev) => prev.filter((a) => a.id !== deleteTargetAdmin.id));
      setSuccessMessage(`Administrator ${deleteTargetAdmin.email} (${deleteTargetAdmin.admin_id}) deleted successfully.`);
      setDeleteTargetAdmin(null);
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        err.error?.message ||
        err.message ||
        'Failed to delete administrator account.'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredAdmins = admins.filter((a) => {
    const q = searchQuery.toLowerCase();
    return (
      a.email.toLowerCase().includes(q) ||
      a.display_name.toLowerCase().includes(q) ||
      a.admin_id.toLowerCase().includes(q)
    );
  });

  const currentUserIsPrimary = user?.admin_id === 'EUAD-GAURAV-099';

  useEffect(() => {
    setSelectedAdminIds(new Set());
  }, [searchQuery]);

  const selectableAdmins = filteredAdmins.filter(
    (a) => !a.is_primary && a.admin_id !== 'EUAD-GAURAV-099' && a.id !== user?.id
  );

  const allSelectableChecked =
    selectableAdmins.length > 0 &&
    selectableAdmins.every((a) => selectedAdminIds.has(a.id));

  const handleSelectAllAdmins = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedAdminIds(new Set(selectableAdmins.map((a) => a.id)));
    } else {
      setSelectedAdminIds(new Set());
    }
  };

  const handleToggleSelectAdmin = (id: string) => {
    setSelectedAdminIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleExecuteBulkDeleteAdmins = async () => {
    if (selectedAdminIds.size === 0) return;
    setIsBulkDeleting(true);
    setBulkDeleteError(null);
    try {
      const res = await AdminAPI.bulkDeleteAdministrators(Array.from(selectedAdminIds));
      setBulkDeleteResult(res);
      if (res.success_count > 0) {
        setSuccessMessage(`Successfully deleted ${res.success_count} administrator account(s).`);
        loadAdmins();
      }
      const successfulIds = new Set(
        res.results.filter((r: any) => r.success).map((r: any) => r.id)
      );
      setSelectedAdminIds((prev) => {
        const next = new Set(prev);
        successfulIds.forEach((id) => next.delete(id));
        return next;
      });
    } catch (err: any) {
      setBulkDeleteError(
        err.response?.data?.error?.message ||
        err.response?.data?.message ||
        err.message ||
        'Failed to execute bulk administrator deletion.'
      );
    } finally {
      setIsBulkDeleting(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 border border-purple-200 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Administrator Management</h1>
            <p className="text-xs text-slate-500">
              Manage authorized administrative identities, security controls, and audit trails
            </p>
          </div>
        </div>

        {activeTab === 'directory' && (
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setModalError(null);
                setFormData({
                  email: '',
                  display_name: '',
                  password: '',
                  confirm_password: '',
                  is_active: true,
                });
                setShowCreatePassword(false);
                setIsCreateModalOpen(true);
              }}
              className="flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>Add Administrator</span>
            </Button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('directory')}
          className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
            activeTab === 'directory'
              ? 'bg-purple-50 text-purple-700 border border-purple-200'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <UserCheck className="w-4 h-4" />
          <span>Administrators Directory ({admins.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
            activeTab === 'audit'
              ? 'bg-purple-50 text-purple-700 border border-purple-200'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Security Audit Trail</span>
        </button>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Tab 1: Administrators Directory */}
      {activeTab === 'directory' && (
        <>
          {/* Search & Stats Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search administrators..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>
            <div className="text-xs text-slate-500 self-end sm:self-center font-mono">
              Showing <strong className="text-slate-800">{filteredAdmins.length}</strong> of {admins.length} administrators
            </div>
          </div>

          {/* Bulk Action Toolbar */}
          {selectedAdminIds.size > 0 && (
            <div className="bg-slate-900 border border-slate-800 text-white px-5 py-3 rounded-xl shadow-xl flex items-center justify-between animate-in fade-in slide-in-from-top-2">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2.5 py-1 rounded-md">
                  {selectedAdminIds.size} administrator{selectedAdminIds.size === 1 ? '' : 's'} selected
                </span>
                <span className="text-xs text-slate-300">of {selectableAdmins.length} eligible</span>
              </div>
              <div className="flex items-center gap-2.5">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedAdminIds(new Set())}
                  className="text-slate-300 hover:text-white text-xs"
                >
                  Deselect All
                </Button>
                {currentUserIsPrimary && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      setBulkDeleteError(null);
                      setBulkDeleteResult(null);
                      setIsBulkDeleteModalOpen(true);
                    }}
                    className="bg-rose-600 hover:bg-rose-700 text-white text-xs flex items-center gap-1.5 font-semibold shadow-sm"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete Selected ({selectedAdminIds.size})</span>
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* Administrators Table */}
          <Card className="p-0 overflow-hidden">
            {isLoading ? (
              <div className="p-10 text-center text-xs text-slate-500">Loading administrator directory...</div>
            ) : errorMessage ? (
              <div className="p-10 text-center space-y-2">
                <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
                <div className="text-sm font-semibold text-rose-800">Failed to Load Administrators</div>
                <p className="text-xs text-rose-600 max-w-md mx-auto">{errorMessage}</p>
                <Button variant="outline" size="sm" onClick={loadAdmins} className="mt-2">
                  Retry
                </Button>
              </div>
            ) : filteredAdmins.length === 0 ? (
              <div className="p-10 text-center space-y-2">
                <UserCheck className="w-8 h-8 text-slate-300 mx-auto" />
                <div className="text-sm font-semibold text-slate-800">No Administrators Found</div>
                <p className="text-xs text-slate-500">No accounts match your current filter query.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                    <tr>
                      {currentUserIsPrimary && (
                        <th className="px-4 py-3 w-10 text-center">
                          <input
                            type="checkbox"
                            checked={allSelectableChecked}
                            onChange={handleSelectAllAdmins}
                            disabled={selectableAdmins.length === 0}
                            className="rounded border-slate-300 text-purple-600 focus:ring-purple-500 h-4 w-4 cursor-pointer disabled:opacity-40"
                            title="Select all eligible secondary administrators"
                          />
                        </th>
                      )}
                      <th className="px-5 py-3">Admin ID</th>
                      <th className="px-5 py-3">Name</th>
                      <th className="px-5 py-3">Email</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredAdmins.map((admin) => {
                      const isCurrent = admin.id === user?.id;
                      const isPrimary = admin.admin_id === 'EUAD-GAURAV-099' || admin.is_primary;
                      const isSelected = selectedAdminIds.has(admin.id);

                      return (
                        <tr
                          key={admin.id}
                          className={`hover:bg-slate-50/70 transition-colors ${
                            isSelected ? 'bg-purple-50/40' : ''
                          }`}
                        >
                          {currentUserIsPrimary && (
                            <td className="px-4 py-3.5 text-center">
                              {isPrimary ? (
                                <input
                                  type="checkbox"
                                  disabled
                                  className="rounded border-slate-200 text-slate-300 h-4 w-4 cursor-not-allowed opacity-30"
                                  title="Primary Administrator is protected and cannot be deleted"
                                />
                              ) : isCurrent ? (
                                <input
                                  type="checkbox"
                                  disabled
                                  className="rounded border-slate-200 text-slate-300 h-4 w-4 cursor-not-allowed opacity-30"
                                  title="You cannot select your own account for deletion"
                                />
                              ) : (
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => handleToggleSelectAdmin(admin.id)}
                                  className="rounded border-slate-300 text-purple-600 focus:ring-purple-500 h-4 w-4 cursor-pointer"
                                />
                              )}
                            </td>
                          )}
                          <td className="px-5 py-3.5 font-mono font-bold text-slate-900">
                            {admin.admin_id}
                          </td>
                          <td className="px-5 py-3.5 font-medium text-slate-900">
                            <div className="flex items-center gap-2">
                              <span>{admin.display_name}</span>
                              {isCurrent && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                                  You
                                </span>
                              )}
                              {isPrimary && (
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-bold border border-purple-200 uppercase tracking-wider">
                                  PRIMARY / PROTECTED
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-5 py-3.5 text-slate-600 font-mono">
                            {admin.email}
                          </td>
                          <td className="px-5 py-3.5">
                            <Badge variant={admin.is_active ? 'success' : 'danger'} size="sm">
                              {admin.is_active ? 'Active' : 'Disabled'}
                            </Badge>
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedAdminForDetails(admin)}
                                className="text-slate-600 hover:text-slate-900 px-2 py-1 flex items-center gap-1 text-[11px]"
                                title="View Details"
                              >
                                <Eye className="w-3.5 h-3.5" />
                                <span>View</span>
                              </Button>

                              {isCurrent ? (
                                <span className="text-[11px] text-slate-400 italic px-2">Self</span>
                              ) : isPrimary ? (
                                <span className="text-[11px] text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded font-medium">
                                  Protected
                                </span>
                              ) : (
                                <>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setResetTargetAdmin(admin)}
                                    className="text-amber-700 border-amber-300 hover:bg-amber-50 px-2 py-1 flex items-center gap-1 text-[11px]"
                                  >
                                    <KeyRound className="w-3 h-3 text-amber-600" />
                                    <span>Reset</span>
                                  </Button>

                                  <Button
                                    variant={admin.is_active ? 'outline' : 'secondary'}
                                    size="sm"
                                    onClick={() => handleToggleStatus(admin)}
                                    className="px-2 py-1 flex items-center gap-1 text-[11px]"
                                  >
                                    <Power className="w-3 h-3" />
                                    <span>{admin.is_active ? 'Deactivate' : 'Activate'}</span>
                                  </Button>

                                  {currentUserIsPrimary && (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => setDeleteTargetAdmin(admin)}
                                      className="text-rose-700 border-rose-300 hover:bg-rose-50 px-2 py-1 flex items-center gap-1 text-[11px]"
                                      title="Delete Administrator"
                                    >
                                      <Trash2 className="w-3 h-3 text-rose-600" />
                                      <span>Delete</span>
                                    </Button>
                                  )}
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      {/* Tab 2: Security Audit Trail */}
      {activeTab === 'audit' && <SecurityAuditTab />}

      {/* Admin Details Modal */}
      {selectedAdminForDetails && (
        <AdminDetailsModal
          isOpen={!!selectedAdminForDetails}
          admin={selectedAdminForDetails}
          currentUserIsPrimary={currentUserIsPrimary}
          currentUserId={user?.id}
          onClose={() => setSelectedAdminForDetails(null)}
          onUpdate={(updated) => {
            setAdmins((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
            setSelectedAdminForDetails(updated);
          }}
          onDelete={(deletedId) => {
            setAdmins((prev) => prev.filter((a) => a.id !== deletedId));
            setSelectedAdminForDetails(null);
            setSuccessMessage("Administrator account deleted successfully.");
          }}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deleteTargetAdmin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <Card className="max-w-md w-full p-6 space-y-4 bg-white border border-rose-200 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900">Delete Administrator</h4>
                <p className="text-xs text-slate-500 font-mono">{deleteTargetAdmin.admin_id} ({deleteTargetAdmin.email})</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to permanently delete this administrator account? All active sessions will be invalidated immediately. Historical audit trail records will be preserved with immutable identity snapshots.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDeleteTargetAdmin(null)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteSecondaryAdmin}
                isLoading={isDeleting}
              >
                Confirm Delete
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Reset Password Modal */}
      {resetTargetAdmin && (
        <ResetPasswordModal
          isOpen={!!resetTargetAdmin}
          onClose={() => setResetTargetAdmin(null)}
          targetName={resetTargetAdmin.display_name}
          targetIdentity={resetTargetAdmin.admin_id}
          targetEmail={resetTargetAdmin.email}
          targetRole="Administrator"
          onReset={handleResetAdminPassword}
        />
      )}

      {/* Add Administrator Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <Card className="max-w-md w-full p-6 space-y-5 bg-white border border-slate-200 shadow-2xl rounded-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-purple-600" />
                <h3 className="text-base font-bold text-slate-900">Add Administrator</h3>
              </div>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateAdmin} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="block font-semibold text-slate-700">Display Name / Full Name</label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={formData.display_name || ''}
                    onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                    placeholder="e.g. John Doe"
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block font-semibold text-slate-700">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="coordinator@institution.edu"
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="block font-semibold text-slate-700">Temporary Password</label>
                  <button
                    type="button"
                    onClick={handleGenerateAdminPassword}
                    className="text-[11px] text-purple-600 hover:text-purple-700 font-semibold flex items-center gap-1 hover:underline"
                  >
                    <Wand2 className="w-3 h-3" />
                    <span>Generate Secure Password</span>
                  </button>
                </div>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type={showCreatePassword ? 'text' : 'password'}
                    required
                    minLength={8}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="At least 8 characters"
                    className="w-full pl-9 pr-10 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCreatePassword(!showCreatePassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showCreatePassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="block font-semibold text-slate-700">Confirm Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type={showCreatePassword ? 'text' : 'password'}
                    required
                    minLength={8}
                    value={formData.confirm_password}
                    onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                    placeholder="Confirm temporary password"
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-mono"
                  />
                </div>
              </div>

              <p className="text-[11px] text-slate-500 leading-normal pt-1">
                The server will automatically generate and assign a unique sequential Admin ID (e.g. CG-ADM-XXXXXX) upon account creation.
              </p>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsCreateModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isSubmitting}
                >
                  Create Administrator
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Bulk Delete Administrators Modal */}
      {isBulkDeleteModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-slate-200 animate-in zoom-in-95">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-rose-50/50">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-rose-100 text-rose-700 rounded-xl">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Delete {selectedAdminIds.size} Administrator Account{selectedAdminIds.size === 1 ? '' : 's'}
                  </h3>
                  <p className="text-xs text-slate-500">
                    Confirm removal of secondary administrator privileges
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  if (!isBulkDeleting) {
                    setIsBulkDeleteModalOpen(false);
                    setBulkDeleteResult(null);
                  }
                }}
                disabled={isBulkDeleting}
                className="text-slate-400 hover:text-slate-600 disabled:opacity-50"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {bulkDeleteError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-lg flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
                  <span>{bulkDeleteError}</span>
                </div>
              )}

              {bulkDeleteResult ? (
                <div className="space-y-3">
                  <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
                    <div className="font-semibold text-slate-900">Deletion Summary:</div>
                    <div className="text-emerald-700 font-mono">
                      ✓ Succeeded: {bulkDeleteResult.success_count}
                    </div>
                    {bulkDeleteResult.failure_count > 0 && (
                      <div className="text-rose-700 font-mono">
                        ✕ Failed: {bulkDeleteResult.failure_count}
                      </div>
                    )}
                  </div>

                  {bulkDeleteResult.failure_count > 0 && (
                    <div className="max-h-48 overflow-y-auto space-y-2 border border-slate-200 rounded-lg p-3 text-xs bg-white">
                      <div className="font-semibold text-slate-800 mb-1">Errors:</div>
                      {bulkDeleteResult.results
                        .filter((r) => !r.success)
                        .map((r) => (
                          <div key={r.id} className="p-2 bg-rose-50 rounded border border-rose-100 text-rose-800">
                            <span className="font-mono font-bold">{r.admin_id || r.id}:</span> {r.error}
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-900 space-y-1">
                    <p className="font-semibold">⚠️ Revocation Warning</p>
                    <p>
                      This will permanently delete the selected administrator credentials and revoke all administrative
                      access to CODEGUARD. All actions will be logged in the immutable security audit trail.
                    </p>
                  </div>

                  <div className="text-xs font-semibold text-slate-700">Selected Administrators:</div>
                  <div className="max-h-48 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg bg-slate-50/50">
                    {admins
                      .filter((a) => selectedAdminIds.has(a.id))
                      .map((a) => (
                        <div key={a.id} className="p-2.5 flex items-center justify-between text-xs">
                          <div>
                            <span className="font-mono font-bold text-slate-900 mr-2">{a.admin_id}</span>
                            <span className="font-medium text-slate-700">{a.display_name}</span>
                            <div className="text-[11px] text-slate-500 font-mono">{a.email}</div>
                          </div>
                          <Badge variant={a.is_active ? 'success' : 'neutral'} size="sm">
                            {a.is_active ? 'Active' : 'Disabled'}
                          </Badge>
                        </div>
                      ))}
                  </div>
                </>
              )}
            </div>

            <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-2.5">
              {bulkDeleteResult ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setIsBulkDeleteModalOpen(false);
                    setBulkDeleteResult(null);
                  }}
                >
                  Close
                </Button>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsBulkDeleteModalOpen(false)}
                    disabled={isBulkDeleting}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleExecuteBulkDeleteAdmins}
                    disabled={isBulkDeleting}
                    className="bg-rose-600 hover:bg-rose-700 text-white flex items-center gap-1.5"
                  >
                    {isBulkDeleting ? (
                      <>
                        <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Deleting...</span>
                      </>
                    ) : (
                      <>
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Confirm Delete</span>
                      </>
                    )}
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminManagementPage;
