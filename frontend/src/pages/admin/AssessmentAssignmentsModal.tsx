import React, { useState, useEffect } from 'react';
import {
  getAssessmentAssignments,
  assignStudentsToAssessment,
  revokeStudentAssignment,
} from '../../api/assessments';
import { fetchStudents } from '../../api/students';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { X, Users, UserPlus, Trash2, Search, AlertCircle } from 'lucide-react';
import { AssessmentAssignmentItem } from '../../types/assessment';
import { StudentProfile } from '../../types/student';

interface AssessmentAssignmentsModalProps {
  assessmentId: string | null;
  assessmentTitle: string;
  isOpen: boolean;
  onClose: () => void;
  onAssignmentsUpdated?: () => void;
}

export const getCanonicalStudentUserId = (student: StudentProfile): string => {
  return student.user_id || student.id;
};

export const getCanonicalAssignmentUserId = (assignment: AssessmentAssignmentItem): string => {
  return assignment.user_id || assignment.student_id;
};

export const AssessmentAssignmentsModal: React.FC<AssessmentAssignmentsModalProps> = ({
  assessmentId,
  assessmentTitle,
  isOpen,
  onClose,
  onAssignmentsUpdated,
}) => {
  const [assignments, setAssignments] = useState<AssessmentAssignmentItem[]>([]);
  const [availableStudents, setAvailableStudents] = useState<StudentProfile[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && assessmentId) {
      loadData(assessmentId);
    } else {
      setAssignments([]);
      setAvailableStudents([]);
      setSelectedStudentIds([]);
      setErrorMessage(null);
    }
  }, [isOpen, assessmentId]);

  const loadData = async (aId: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [assignRes, studentsRes] = await Promise.all([
        getAssessmentAssignments(aId),
        fetchStudents({ page_size: 100, is_active: true }),
      ]);
      if (assignRes.data) {
        setAssignments(assignRes.data);
      }
      if (studentsRes.data) {
        setAvailableStudents(studentsRes.data.results);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load assignment data.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAssignSelected = async () => {
    if (!assessmentId || selectedStudentIds.length === 0) return;
    setIsAssigning(true);
    setErrorMessage(null);
    try {
      await assignStudentsToAssessment(assessmentId, selectedStudentIds);
      setSelectedStudentIds([]);
      await loadData(assessmentId);
      onAssignmentsUpdated?.();
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to assign students.');
    } finally {
      setIsAssigning(false);
    }
  };

  const handleRevoke = async (studentId: string) => {
    if (!assessmentId) return;
    try {
      await revokeStudentAssignment(assessmentId, studentId);
      await loadData(assessmentId);
      onAssignmentsUpdated?.();
    } catch (err: any) {
      alert(err.error?.message || 'Failed to revoke assignment.');
    }
  };

  if (!isOpen) return null;

  const assignedStudentIdSet = new Set(
    assignments.filter((a) => a.status === 'ASSIGNED').map(getCanonicalAssignmentUserId)
  );

  const filteredUnassignedStudents = availableStudents.filter((st) => {
    const canonicalUserId = getCanonicalStudentUserId(st);
    if (assignedStudentIdSet.has(canonicalUserId)) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      st.email.toLowerCase().includes(q) ||
      (st.roll_number && st.roll_number.toLowerCase().includes(q))
    );
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm overflow-y-auto">
      <Card className="max-w-3xl w-full p-6 space-y-6 bg-white border border-slate-200 shadow-2xl relative my-8">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
          <div className="p-2.5 rounded-xl bg-purple-50 text-purple-700 border border-purple-200">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Student Assignments</h3>
            <p className="text-xs text-slate-500">
              Manage student authorizations for: <strong className="text-slate-900">{assessmentTitle}</strong>
            </p>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-500">Loading students & assignments...</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Section 1: Assign New Students */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                  <UserPlus className="w-4 h-4 text-emerald-600" />
                  Assign Active Students
                </span>
                {selectedStudentIds.length > 0 && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleAssignSelected}
                    isLoading={isAssigning}
                  >
                    Assign Selected ({selectedStudentIds.length})
                  </Button>
                )}
              </div>

              {/* Search Bar */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter available students by email or roll number..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-white border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {/* Student Pick List */}
              <div className="max-h-40 overflow-y-auto border border-slate-200 rounded-lg divide-y divide-slate-100 bg-white text-xs">
                {filteredUnassignedStudents.length === 0 ? (
                  <div className="p-3 text-center text-slate-500 text-xs">
                    No matching unassigned students found.
                  </div>
                ) : (
                  filteredUnassignedStudents.map((st) => {
                    const canonicalUserId = getCanonicalStudentUserId(st);
                    const isSelected = selectedStudentIds.includes(canonicalUserId);
                    return (
                      <div
                        key={st.id}
                        onClick={() => {
                          if (isSelected) {
                            setSelectedStudentIds(selectedStudentIds.filter((id) => id !== canonicalUserId));
                          } else {
                            setSelectedStudentIds([...selectedStudentIds, canonicalUserId]);
                          }
                        }}
                        className={`flex items-center justify-between p-2.5 cursor-pointer transition-colors ${
                          isSelected ? 'bg-emerald-50 text-emerald-900' : 'hover:bg-slate-50 text-slate-800'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="rounded text-emerald-600 focus:ring-emerald-500 h-3.5 w-3.5 bg-white border-slate-300"
                          />
                          <span className="font-medium text-slate-900">{st.email}</span>
                          {st.roll_number && (
                            <span className="text-[10px] text-slate-600 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded font-mono">
                              {st.roll_number}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Section 2: Currently Assigned Roster */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Currently Assigned Students ({assignments.filter((a) => a.status === 'ASSIGNED').length})
              </h4>
              <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-xl divide-y divide-slate-100 bg-white text-xs">
                {assignments.length === 0 ? (
                  <div className="p-6 text-center text-slate-500 text-xs">
                    No students currently assigned to this assessment.
                  </div>
                ) : (
                  assignments.map((a) => {
                    const isRevoked = a.status === 'REVOKED';
                    return (
                      <div key={a.id} className="flex items-center justify-between p-3 hover:bg-slate-50 transition-colors">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className={`font-medium ${isRevoked ? 'line-through text-slate-400' : 'text-slate-900'}`}>
                              {a.student_email}
                            </span>
                            {a.student_roll_number && (
                              <span className="text-[10px] text-slate-600 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded font-mono">
                                {a.student_roll_number}
                              </span>
                            )}
                            <Badge variant={isRevoked ? 'neutral' : 'success'} size="sm">
                              {a.status}
                            </Badge>
                          </div>
                          <span className="text-[10px] text-slate-500">
                            Assigned on: {new Date(a.assigned_at).toLocaleDateString()}
                          </span>
                        </div>

                        {!isRevoked && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRevoke(getCanonicalAssignmentUserId(a))}
                            title="Revoke Assignment"
                            className="text-slate-400 hover:text-rose-600"
                          >
                            <Trash2 className="w-3.5 h-3.5 mr-1" />
                            Revoke
                          </Button>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}

        <div className="pt-3 flex justify-end border-t border-slate-200">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Done
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default AssessmentAssignmentsModal;
