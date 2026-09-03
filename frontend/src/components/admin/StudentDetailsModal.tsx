import React, { useState } from 'react';
import { disableStudent, enableStudent, updateStudent } from '../../api/students';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  User,
  AlertCircle,
  X,
  Power,
  Edit2,
  Check,
  Lock,
} from 'lucide-react';
import { StudentProfile } from '../../types/student';

interface StudentDetailsModalProps {
  student: StudentProfile | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdate: (updated: StudentProfile) => void;
}

export const StudentDetailsModal: React.FC<StudentDetailsModalProps> = ({
  student,
  isOpen,
  onClose,
  onUpdate,
}) => {
  const [currentStudent, setCurrentStudent] = useState<StudentProfile | null>(student);
  const [isEditing, setIsEditing] = useState(false);
  const [editEmail, setEditEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  React.useEffect(() => {
    setCurrentStudent(student);
    if (student) {
      setEditEmail(student.email);
    }
  }, [student]);

  if (!isOpen || !currentStudent) return null;

  const handleToggleStatus = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = currentStudent.is_active
        ? await disableStudent(currentStudent.id)
        : await enableStudent(currentStudent.id);
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
      });
      if (res.data) {
        setCurrentStudent(res.data);
        onUpdate(res.data);
        setIsEditing(false);
      }
    } catch (err: any) {
      const msg =
        err.error?.details?.email?.[0] ||
        err.error?.message ||
        'Failed to update student email.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <Card className="max-w-lg w-full p-6 space-y-6 border-slate-800 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white font-mono">{currentStudent.roll_number}</h3>
              <p className="text-xs text-brand-400 font-mono">{currentStudent.euid}</p>
            </div>
          </div>
          <Badge variant={currentStudent.is_active ? 'success' : 'danger'}>
            {currentStudent.is_active ? 'ACTIVE' : 'DISABLED'}
          </Badge>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start gap-2.5 text-red-300 text-xs">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Student Details or Edit Form */}
        {isEditing ? (
          <div className="space-y-4 text-xs font-mono">
            <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Roll Number</span>
                <span className="text-slate-200 font-bold">{currentStudent.roll_number}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Exam Unique ID</span>
                <span className="text-brand-400 font-bold">{currentStudent.euid}</span>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-slate-500 pt-1 border-t border-slate-800/60">
                <Lock className="w-3 h-3 text-slate-500" />
                <span>Roll Number and EUID are permanently immutable academic identity records.</span>
              </div>
            </div>

            <div className="space-y-1">
              <label className="block text-slate-300 font-medium">Editable Email Address</label>
              <input
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 focus:ring-1 focus:ring-brand-500"
                placeholder="student@university.edu"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={handleSaveEdit} isLoading={isLoading}>
                <Check className="w-3.5 h-3.5 mr-1" />
                Save Email
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3 text-xs font-mono">
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Email Address</span>
              <span className="text-slate-200 font-semibold">{currentStudent.email}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Exam Unique ID</span>
              <span className="text-brand-400 font-bold">{currentStudent.euid}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Roll Number</span>
              <span className="text-slate-200">{currentStudent.roll_number}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">First Login Password Reset</span>
              <span className={currentStudent.first_login_required ? 'text-amber-400 font-semibold' : 'text-slate-500'}>
                {currentStudent.first_login_required ? 'REQUIRED (PENDING)' : 'SATISFIED (COMPLETED)'}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Enrolled On</span>
              <span className="text-slate-400">{new Date(currentStudent.created_at).toLocaleString()}</span>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="pt-3 flex items-center justify-between border-t border-slate-800">
          <Button
            variant={currentStudent.is_active ? 'danger' : 'primary'}
            size="sm"
            onClick={handleToggleStatus}
            isLoading={isLoading}
          >
            <Power className="w-3.5 h-3.5 mr-1.5" />
            {currentStudent.is_active ? 'Disable Account' : 'Enable Account'}
          </Button>

          {!isEditing && (
            <Button variant="secondary" size="sm" onClick={() => setIsEditing(true)}>
              <Edit2 className="w-3.5 h-3.5 mr-1.5" />
              Edit Email
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
};

export default StudentDetailsModal;
