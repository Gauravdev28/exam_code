import React, { useState, useEffect } from 'react';
import { disableStudent, enableStudent, updateStudent, resetStudentPassword, deleteStudentAccount } from '../../api/students';
import { fetchSections } from '../../api/sections';
import { Section } from '../../types/section';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { ResetPasswordModal } from './ResetPasswordModal';
import {
  User,
  AlertCircle,
  X,
  Power,
  Edit2,
  Check,
  Lock,
  KeyRound,
  Trash2,
  ShieldAlert,
} from 'lucide-react';
import { StudentProfile } from '../../types/student';
import { ResetPasswordPayload } from '../../types/admin';

interface StudentDetailsModalProps {
  student: StudentProfile | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdate: (updated: StudentProfile) => void;
  onDelete?: (studentId: string) => void;
}

export const StudentDetailsModal: React.FC<StudentDetailsModalProps> = ({
  student,
  isOpen,
  onClose,
  onUpdate,
  onDelete,
}) => {
  const [currentStudent, setCurrentStudent] = useState<StudentProfile | null>(student);
  const [isEditing, setIsEditing] = useState(false);
  const [editEmail, setEditEmail] = useState('');
  const [editSectionId, setEditSectionId] = useState<string>('');
  const [sections, setSections] = useState<Section[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  useEffect(() => {
    setCurrentStudent(student);
    if (student) {
      setEditEmail(student.email);
      setEditSectionId(student.section?.id || '');
    }
  }, [student]);

  useEffect(() => {
    if (isOpen) {
      fetchSections({ active_only: true })
        .then((res) => {
          if (res.data) setSections(res.data);
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen || !currentStudent) return null;

  const handleToggleStatus = async () => {
    const isDisabling = currentStudent.is_active;
    const promptMsg = isDisabling
      ? 'Reason for disabling student account (e.g. academic integrity hold):'
      : 'Reason for enabling student account (e.g. reinstated after review):';
    const reason = window.prompt(promptMsg, isDisabling ? 'Administrative suspension' : 'Reinstated account');
    if (reason === null) {
      return; // Admin cancelled
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = isDisabling
        ? await disableStudent(currentStudent.id, reason)
        : await enableStudent(currentStudent.id, reason);
      if (res.data) {
        setCurrentStudent(res.data);
        onUpdate(res.data);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to toggle account status.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await updateStudent(currentStudent.id, {
        email: editEmail.trim(),
        section_id: editSectionId ? editSectionId : null,
      });
      if (res.data) {
        setCurrentStudent(res.data);
        onUpdate(res.data);
        setIsEditing(false);
      }
    } catch (err: any) {
      const msg =
        err.error?.details?.email?.[0] ||
        err.error?.details?.section_id?.[0] ||
        err.error?.message ||
        'Failed to update student details.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPasswordAction = async (payload: ResetPasswordPayload): Promise<void> => {
    const res = await resetStudentPassword(currentStudent.id, payload);
    if (res.data) {
      setCurrentStudent((prev) => (prev ? { ...prev, first_login_required: true } : null));
    }
  };

  const handleDeleteStudent = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await deleteStudentAccount(currentStudent.id);
      setIsDeleteConfirmOpen(false);
      if (onDelete) {
        onDelete(currentStudent.id);
      }
      onClose();
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to delete student account.');
      setIsDeleteConfirmOpen(false);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
        <Card className="max-w-lg w-full p-6 space-y-6 bg-white border border-slate-200 shadow-2xl rounded-2xl relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>

          {/* Header */}
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
              <User className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900">{currentStudent.roll_number}</h3>
                <Badge variant={currentStudent.is_active ? 'success' : 'danger'} size="sm">
                  {currentStudent.is_active ? 'ACTIVE' : 'DISABLED'}
                </Badge>
                {currentStudent.section && (
                  <Badge variant="purple" size="sm" className="font-mono font-bold">
                    {currentStudent.section.code}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-slate-600 font-medium">Authoritative Student Account Details</p>
            </div>
          </div>

          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2.5 text-xs text-rose-700">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Student Profile Attributes */}
          <div className="space-y-4">
            {isEditing ? (
              <div className="space-y-3 p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                <div className="space-y-1.5 pb-3 border-b border-slate-200">
                  <div className="flex justify-between">
                    <span className="text-slate-700 font-semibold">Roll Number</span>
                    <span className="text-slate-900 font-mono font-bold">{currentStudent.roll_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-700 font-semibold">Exam Unique ID (EUID)</span>
                    <span className="text-emerald-700 font-mono font-bold">{currentStudent.euid}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-600 font-medium pt-2 border-t border-slate-200">
                    <Lock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span>Roll Number and EUID are permanently immutable academic identity records.</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-slate-800 font-bold">Editable Email Address</label>
                  <input
                    type="email"
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-500 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-xs font-sans"
                    placeholder="student@university.edu"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="block text-slate-800 font-bold">Academic Section</label>
                  <select
                    value={editSectionId}
                    onChange={(e) => setEditSectionId(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  >
                    <option value="">None / Unassigned</option>
                    {sections.map((sec) => (
                      <option key={sec.id} value={sec.id}>
                        {sec.code} - {sec.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-slate-500">
                    Moving student sections will not revoke historical assessments already taken.
                  </p>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" size="sm" onClick={() => setIsEditing(false)}>
                    Cancel
                  </Button>
                  <Button variant="primary" size="sm" onClick={handleSaveEdit} isLoading={isLoading}>
                    <Check className="w-3.5 h-3.5 mr-1" />
                    Save Changes
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                <div className="flex justify-between py-2 border-b border-slate-100">
                  <span className="text-slate-700 font-semibold">Email Address</span>
                  <span className="text-slate-900 font-bold">{currentStudent.email}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-100">
                  <span className="text-slate-700 font-semibold">Exam Unique ID</span>
                  <span className="text-emerald-700 font-mono font-bold">{currentStudent.euid}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-100">
                  <span className="text-slate-700 font-semibold">Roll Number</span>
                  <span className="text-slate-900 font-mono font-bold">{currentStudent.roll_number}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-100 items-center">
                  <span className="text-slate-700 font-semibold">Academic Section</span>
                  {currentStudent.section ? (
                    <Badge variant="purple" size="sm" className="font-mono font-bold">
                      {currentStudent.section.code} - {currentStudent.section.name}
                    </Badge>
                  ) : (
                    <span className="text-slate-400 font-mono text-xs bg-slate-100 px-2 py-0.5 rounded">
                      Unassigned
                    </span>
                  )}
                </div>
                <div className="flex justify-between py-2 border-b border-slate-100 items-center">
                  <span className="text-slate-700 font-semibold">First Login Password Reset</span>
                  <span className={currentStudent.first_login_required ? 'text-amber-900 font-bold bg-amber-50 px-2 py-0.5 rounded border border-amber-300' : 'text-slate-700 font-semibold bg-slate-100 px-2 py-0.5 rounded border border-slate-200'}>
                    {currentStudent.first_login_required ? 'REQUIRED (PENDING)' : 'SATISFIED (COMPLETED)'}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-100">
                  <span className="text-slate-700 font-semibold">Enrolled On</span>
                  <span className="text-slate-900 font-mono font-semibold">{new Date(currentStudent.created_at).toLocaleString()}</span>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="pt-3 flex flex-wrap items-center justify-between border-t border-slate-200 gap-2">
            <div className="flex items-center gap-2">
              <Button
                variant={currentStudent.is_active ? 'danger' : 'primary'}
                size="sm"
                onClick={handleToggleStatus}
                isLoading={isLoading}
              >
                <Power className="w-3.5 h-3.5 mr-1.5" />
                {currentStudent.is_active ? 'Disable Account' : 'Enable Account'}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsResetModalOpen(true)}
                className="text-amber-700 border-amber-300 hover:bg-amber-50"
              >
                <KeyRound className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
                Reset Password
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDeleteConfirmOpen(true)}
                className="text-rose-700 border-rose-300 hover:bg-rose-50"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1.5 text-rose-600" />
                Delete Account
              </Button>
            </div>

            {!isEditing && (
              <Button variant="secondary" size="sm" onClick={() => setIsEditing(true)}>
                <Edit2 className="w-3.5 h-3.5 mr-1.5" />
                Edit Email
              </Button>
            )}
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
                <h4 className="text-base font-bold text-slate-900">Delete Student Account</h4>
                <p className="text-xs text-slate-500 font-mono">{currentStudent.roll_number} ({currentStudent.euid})</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to delete this student account? If this student has active assessments, examination records, historical results, or active legal holds, deletion will be blocked in accordance with Phase 9 retention rules.
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
                onClick={handleDeleteStudent}
                isLoading={isLoading}
              >
                Confirm Delete
              </Button>
            </div>
          </Card>
        </div>
      )}

      <ResetPasswordModal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        targetName={`Student (${currentStudent.roll_number})`}
        targetIdentity={currentStudent.euid}
        targetEmail={currentStudent.email}
        targetRole="Student"
        onReset={handleResetPasswordAction}
      />
    </>
  );
};

export default StudentDetailsModal;

