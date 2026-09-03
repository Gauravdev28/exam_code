import React, { useState } from 'react';
import { createStudent } from '../../api/students';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { UserPlus, Mail, Hash, AlertCircle, X } from 'lucide-react';
import { StudentProfile } from '../../types/student';

interface AddStudentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (student: StudentProfile) => void;
}

export const AddStudentModal: React.FC<AddStudentModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [email, setEmail] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!email.trim() || !rollNumber.trim()) {
      setErrorMessage('Both email and academic roll number are required.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await createStudent({
        email: email.trim(),
        roll_number: rollNumber.trim(),
      });
      if (res.data) {
        onSuccess(res.data);
        onClose();
      }
    } catch (err: any) {
      const msg =
        err.error?.details?.email?.[0] ||
        err.error?.details?.roll_number?.[0] ||
        err.error?.message ||
        err.message ||
        'Failed to create student account.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <Card className="max-w-md w-full p-6 space-y-5 border-slate-800 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
            <UserPlus className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Enroll New Student</h3>
            <p className="text-xs text-slate-400">Generates EUID & initial hashed password automatically</p>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start gap-2.5 text-red-300 text-xs">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="block text-xs font-medium text-slate-300">
              Academic Roll Number / Registration ID
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                <Hash className="w-4 h-4" />
              </div>
              <input
                type="text"
                required
                value={rollNumber}
                onChange={(e) => setRollNumber(e.target.value)}
                placeholder="e.g. BETN1AI25099"
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 placeholder-slate-500 text-xs focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <p className="text-[11px] text-slate-500">
              EUID will be generated as <code className="text-brand-400">CG-&#123;ROLL&#125;</code> and initial password set to this roll number.
            </p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-medium text-slate-300">
              Official Student Email Address
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                <Mail className="w-4 h-4" />
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="student@university.edu"
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 placeholder-slate-500 text-xs focus:ring-1 focus:ring-brand-500"
              />
            </div>
          </div>

          <div className="pt-3 flex items-center justify-end gap-3 border-t border-slate-800">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isLoading}>
              Create Account
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default AddStudentModal;
