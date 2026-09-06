import React, { useState, useEffect } from 'react';
import { createStudent } from '../../api/students';
import { fetchSections } from '../../api/sections';
import { Section } from '../../types/section';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { UserPlus, Mail, Hash, AlertCircle, X, Check, Copy, KeyRound, CheckCircle2, Layers } from 'lucide-react';
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
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [sectionId, setSectionId] = useState('');
  const [sections, setSections] = useState<Section[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Success reveal state
  const [createdResult, setCreatedResult] = useState<{
    profile: StudentProfile;
    temporaryPassword: string;
  } | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchSections({ active_only: true })
        .then((res) => {
          if (res.data) setSections(res.data);
        })
        .catch(() => {});
    }
  }, [isOpen]);

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
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        section_id: sectionId ? sectionId : null,
      });
      if (res.data) {
        const student = res.data as any;
        setCreatedResult({
          profile: student,
          temporaryPassword: student.temporary_password || student.roll_number,
        });
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

  const handleCopyPassword = () => {
    if (createdResult) {
      navigator.clipboard.writeText(createdResult.temporaryPassword);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2500);
    }
  };

  const handleFinish = () => {
    if (createdResult) {
      onSuccess(createdResult.profile);
    }
    setEmail('');
    setRollNumber('');
    setCreatedResult(null);
    setIsCopied(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
      <Card className="max-w-md w-full p-6 space-y-5 bg-white border border-slate-200 shadow-2xl rounded-2xl relative">
        <button
          onClick={createdResult ? handleFinish : onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
        >
          <X className="w-5 h-5" />
        </button>

        {!createdResult ? (
          <>
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                <UserPlus className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Enroll New Student</h3>
                <p className="text-xs text-slate-600 font-medium">Generates EUID & initial hashed password automatically</p>
              </div>
            </div>

            {errorMessage && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs">
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <span className="font-semibold">{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-slate-800">
                    First Name
                  </label>
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="e.g. Gaurav"
                    className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-500 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-medium"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-slate-800">
                    Last Name
                  </label>
                  <input
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="e.g. Agarwal"
                    className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-500 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-medium"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-800">
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
                    placeholder="e.g. BETN1AI25988"
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-500 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-mono font-medium"
                  />
                </div>
                <p className="text-[11px] text-slate-600 font-medium">
                  EUID will be generated as <code className="text-emerald-700 font-bold font-mono">CG-&#123;ROLL&#125;</code> and initial password set to this roll number.
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-800">
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
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-500 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-medium"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-800">
                  Academic Section (Optional)
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <Layers className="w-4 h-4" />
                  </div>
                  <select
                    value={sectionId}
                    onChange={(e) => setSectionId(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs focus:ring-2 focus:ring-purple-500 focus:border-purple-500 font-medium"
                  >
                    <option value="">None / Unassigned</option>
                    {sections.map((sec) => (
                      <option key={sec.id} value={sec.id}>
                        {sec.code} - {sec.name}
                      </option>
                    ))}
                  </select>
                </div>
                <p className="text-[11px] text-slate-500">
                  Assign student to an academic section for cohort assessment targeting.
                </p>
              </div>

              <div className="pt-3 flex items-center justify-end gap-3 border-t border-slate-200">
                <Button type="button" variant="secondary" size="sm" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" size="sm" isLoading={isLoading}>
                  Create Account
                </Button>
              </div>
            </form>
          </>
        ) : (
          /* Step 2: One-time Onboarding Reveal */
          <div className="space-y-5 animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-6 h-6 text-emerald-600" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Student Account Created</h3>
                <p className="text-xs text-slate-500">
                  Initial credentials established with first-login requirement
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-200">
                <span className="text-slate-500 font-medium">Roll Number</span>
                <span className="font-mono font-bold text-slate-900">{createdResult.profile.roll_number}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200">
                <span className="text-slate-500 font-medium">EUID (Login ID)</span>
                <span className="font-mono font-bold text-emerald-700">{createdResult.profile.euid}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200">
                <span className="text-slate-500 font-medium">Institutional Email</span>
                <span className="font-mono text-slate-700">{createdResult.profile.email}</span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-500 font-medium">Temporary Password</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-amber-900 bg-amber-50 px-2 py-0.5 rounded border border-amber-300">
                    {createdResult.temporaryPassword}
                  </span>
                  <button
                    onClick={handleCopyPassword}
                    className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200"
                    title="Copy Temporary Password"
                  >
                    {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 flex items-start gap-2.5 text-[11px] text-amber-900">
              <KeyRound className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <p>
                <strong>Security Notice:</strong> The temporary password is set to the student's Roll Number.
                The student must sign in with their <strong>Email</strong> or <strong>EUID</strong> and this password, then immediately choose a permanent password.
              </p>
            </div>

            <div className="pt-3 flex justify-end border-t border-slate-100">
              <Button variant="primary" size="sm" onClick={handleFinish}>
                Done
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default AddStudentModal;
