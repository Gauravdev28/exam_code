import React, { useState, useEffect, useCallback } from 'react';
import { fetchSections } from '../../api/sections';
import { fetchStudents } from '../../api/students';
import {
  fetchAssessmentAudience,
  configureAssessmentAudience,
  previewAssessmentAudience,
} from '../../api/assessments';
import { Section } from '../../types/section';
import { StudentProfile } from '../../types/student';
import { AudienceResolution } from '../../types/assessment';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  Users,
  Layers,
  UserPlus,
  Search,
  X,
  AlertCircle,
  CheckCircle2,
  Lock,
  Sparkles,
  UserCheck,
} from 'lucide-react';

interface AssessmentAudiencePanelProps {
  assessmentId: string | null;
  isLocked: boolean;
  onAudienceChanged?: (resolution: AudienceResolution) => void;
  onValidationChange?: (isValid: boolean, totalEligible: number) => void;
}

export const AssessmentAudiencePanel: React.FC<AssessmentAudiencePanelProps> = ({
  assessmentId,
  isLocked,
  onAudienceChanged,
  onValidationChange,
}) => {
  const [sections, setSections] = useState<Section[]>([]);
  const [selectedSectionIds, setSelectedSectionIds] = useState<string[]>([]);
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [resolution, setResolution] = useState<AudienceResolution | null>(null);

  // Student search & picker state
  const [availableStudents, setAvailableStudents] = useState<StudentProfile[]>([]);
  const [studentSearch, setStudentSearch] = useState('');
  const [isStudentPickerOpen, setIsStudentPickerOpen] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Initial load: active sections
  useEffect(() => {
    fetchSections({ active_only: true })
      .then((res) => {
        if (res.data) setSections(res.data);
      })
      .catch(() => {});
  }, []);

  // Initial load: existing audience for assessment
  useEffect(() => {
    if (!assessmentId) return;

    setIsLoading(true);
    fetchAssessmentAudience(assessmentId)
      .then((res) => {
        if (res.data) {
          const r = res.data;
          setResolution(r);
          setSelectedSectionIds(r.sections.map((s) => s.id));
          setSelectedStudentIds(r.additional_students.map((s) => s.id));
          if (onValidationChange) {
            onValidationChange(r.total_eligible > 0, r.total_eligible);
          }
        }
      })
      .catch((err: any) => {
        console.error('Failed to load audience configuration:', err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [assessmentId, onValidationChange]);

  // Load students for picker when opened
  useEffect(() => {
    if (isStudentPickerOpen && availableStudents.length === 0) {
      fetchStudents({ page_size: 100, is_active: true })
        .then((res) => {
          if (res.data?.results) setAvailableStudents(res.data.results);
        })
        .catch(() => {});
    }
  }, [isStudentPickerOpen, availableStudents.length]);

  // Preview audience whenever selections change
  const runPreview = useCallback(
    async (secIds: string[], stuIds: string[]) => {
      if (!assessmentId) return;
      try {
        const res = await previewAssessmentAudience(assessmentId, {
          target_section_ids: secIds,
          target_student_ids: stuIds,
        });
        if (res.data) {
          setResolution(res.data);
          if (onValidationChange) {
            onValidationChange(res.data.total_eligible > 0, res.data.total_eligible);
          }
        }
      } catch (err: any) {
        console.error('Failed to preview audience resolution:', err);
      }
    },
    [assessmentId, onValidationChange]
  );

  const handleToggleSection = (sectionId: string) => {
    if (isLocked) return;
    const updated = selectedSectionIds.includes(sectionId)
      ? selectedSectionIds.filter((id) => id !== sectionId)
      : [...selectedSectionIds, sectionId];

    setSelectedSectionIds(updated);
    setSaveSuccess(false);
    runPreview(updated, selectedStudentIds);
  };

  const handleSelectAllSections = () => {
    if (isLocked) return;
    const allIds = sections.map((s) => s.id);
    setSelectedSectionIds(allIds);
    setSaveSuccess(false);
    runPreview(allIds, selectedStudentIds);
  };

  const handleClearAllSections = () => {
    if (isLocked) return;
    setSelectedSectionIds([]);
    setSaveSuccess(false);
    runPreview([], selectedStudentIds);
  };

  const handleAddStudent = (student: StudentProfile) => {
    if (isLocked) return;
    const studentUserId = student.user_id || student.id;
    if (!selectedStudentIds.includes(studentUserId)) {
      const updated = [...selectedStudentIds, studentUserId];
      setSelectedStudentIds(updated);
      setSaveSuccess(false);
      runPreview(selectedSectionIds, updated);
    }
  };

  const handleRemoveStudent = (studentId: string) => {
    if (isLocked) return;
    const updated = selectedStudentIds.filter((id) => id !== studentId);
    setSelectedStudentIds(updated);
    setSaveSuccess(false);
    runPreview(selectedSectionIds, updated);
  };

  const handleSaveAudience = async () => {
    if (!assessmentId || isLocked) return;

    setIsSaving(true);
    setErrorMessage(null);
    setSaveSuccess(false);
    try {
      const res = await configureAssessmentAudience(assessmentId, {
        target_section_ids: selectedSectionIds,
        target_student_ids: selectedStudentIds,
      });
      if (res.data) {
        setResolution(res.data);
        setSaveSuccess(true);
        if (onAudienceChanged) onAudienceChanged(res.data);
        if (onValidationChange) {
          onValidationChange(res.data.total_eligible > 0, res.data.total_eligible);
        }
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err: any) {
      const msg = err.error?.message || err.message || 'Failed to update target audience.';
      setErrorMessage(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const totalEligible = resolution ? resolution.total_eligible : 0;
  const isZeroAudience = totalEligible === 0;

  return (
    <Card className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-600" />
            <h2 className="text-base font-bold text-slate-900">Target Audience & Classification</h2>
            {isLocked ? (
              <Badge variant="neutral" size="sm" className="flex items-center gap-1">
                <Lock className="w-3 h-3" /> Locked & Authoritative
              </Badge>
            ) : (
              <Badge variant="purple" size="sm">
                Targeting Setup
              </Badge>
            )}
            {isLoading && (
              <span className="text-[11px] text-slate-400 font-mono animate-pulse">Loading audience...</span>
            )}
          </div>
          <p className="text-xs text-slate-500">
            Target complete academic sections, individual students, or any combination.
            Eligible students will automatically receive authoritative Assessment Assignments upon publication.
          </p>
        </div>

        {!isLocked && assessmentId && (
          <div className="flex items-center gap-2">
            {saveSuccess && (
              <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" /> Audience Saved
              </span>
            )}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleSaveAudience}
              isLoading={isSaving}
            >
              Save Audience
            </Button>
          </div>
        )}
      </div>

      {errorMessage && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2.5 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Target Sections Selection */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-purple-600" />
            Academic Sections
          </label>
          {!isLocked && (
            <div className="flex items-center gap-2 text-[11px]">
              <button
                type="button"
                onClick={handleSelectAllSections}
                className="text-purple-600 hover:text-purple-800 font-semibold"
              >
                Select All
              </button>
              <span className="text-slate-300">•</span>
              <button
                type="button"
                onClick={handleClearAllSections}
                className="text-slate-500 hover:text-slate-700 font-medium"
              >
                Clear All
              </button>
            </div>
          )}
        </div>

        {sections.length === 0 ? (
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-500 text-center">
            No active sections found. You can create sections in Student Management.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
            {sections.map((sec) => {
              const isSelected = selectedSectionIds.includes(sec.id);
              return (
                <button
                  key={sec.id}
                  type="button"
                  disabled={isLocked}
                  onClick={() => handleToggleSection(sec.id)}
                  className={`p-3 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
                    isSelected
                      ? 'bg-purple-50/80 border-purple-300 ring-2 ring-purple-500/20 shadow-sm'
                      : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60'
                  } ${isLocked ? 'cursor-not-allowed opacity-90' : 'cursor-pointer'}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono font-bold text-xs text-slate-900">{sec.code}</span>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={isLocked}
                      onChange={() => {}}
                      className="rounded text-purple-600 focus:ring-purple-500 h-3.5 w-3.5 pointer-events-none"
                    />
                  </div>
                  <span className="text-[11px] text-slate-500 truncate" title={sec.name}>
                    {sec.name}
                  </span>
                  <span className="text-[10px] text-slate-400 mt-1 font-mono">
                    {sec.student_count ?? 0} students
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Target Individual Students */}
      <div className="space-y-3 pt-2 border-t border-slate-100">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
            <UserPlus className="w-4 h-4 text-purple-600" />
            Specific Individual Students
            {selectedStudentIds.length > 0 && (
              <span className="text-[11px] font-mono text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full font-semibold">
                {selectedStudentIds.length} added
              </span>
            )}
          </label>
          {!isLocked && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsStudentPickerOpen(!isStudentPickerOpen)}
              className="text-purple-700 border-purple-200 hover:bg-purple-50 text-xs"
            >
              {isStudentPickerOpen ? 'Close Picker' : '+ Add Specific Students'}
            </Button>
          )}
        </div>

        {/* Searchable Picker Dropdown */}
        {isStudentPickerOpen && !isLocked && (
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3 animate-fade-in">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
              <input
                type="text"
                value={studentSearch}
                onChange={(e) => setStudentSearch(e.target.value)}
                placeholder="Search students by roll number, email, or EUID..."
                className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-purple-500 bg-white"
              />
            </div>

            <div className="max-h-48 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg bg-white text-xs">
              {availableStudents
                .filter((st) => {
                  const query = studentSearch.toLowerCase();
                  return (
                    st.email.toLowerCase().includes(query) ||
                    st.roll_number.toLowerCase().includes(query) ||
                    st.euid.toLowerCase().includes(query)
                  );
                })
                .slice(0, 30)
                .map((st) => {
                  const studentUserId = st.user_id || st.id;
                  const isAdded = selectedStudentIds.includes(studentUserId);
                  return (
                    <div
                      key={st.id}
                      className="p-2.5 flex items-center justify-between hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-slate-900">{st.roll_number}</span>
                        <span className="text-slate-600 text-[11px]">{st.email}</span>
                        {st.section && (
                          <Badge variant="purple" size="sm">
                            {st.section.code}
                          </Badge>
                        )}
                      </div>
                      <Button
                        type="button"
                        variant={isAdded ? 'ghost' : 'secondary'}
                        size="sm"
                        disabled={isAdded}
                        onClick={() => handleAddStudent(st)}
                        className="text-xs h-7 px-2.5"
                      >
                        {isAdded ? (
                          <span className="text-emerald-600 font-semibold flex items-center gap-1">
                            <UserCheck className="w-3.5 h-3.5" /> Added
                          </span>
                        ) : (
                          '+ Add'
                        )}
                      </Button>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Selected Additional Students Pills */}
        {resolution && resolution.additional_students && resolution.additional_students.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {resolution.additional_students.map((st) => (
              <div
                key={st.id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-mono text-slate-800"
              >
                <span className="font-bold">{st.roll_number || st.email}</span>
                {st.section && (
                  <span className="text-[10px] text-purple-700 font-semibold bg-purple-50 px-1 rounded">
                    {st.section}
                  </span>
                )}
                {!isLocked && (
                  <button
                    type="button"
                    onClick={() => handleRemoveStudent(st.id)}
                    className="text-slate-400 hover:text-rose-600 p-0.5 rounded"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sticky / Compact Live Audience Summary Box */}
      <div
        className={`p-4 rounded-xl border transition-all ${
          isZeroAudience
            ? 'bg-amber-50/80 border-amber-300 text-amber-900'
            : 'bg-gradient-to-r from-purple-50/60 to-slate-50 border-purple-200 text-slate-800'
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-600" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Authoritative Audience Summary
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-slate-900">{totalEligible}</span>
              <span className="text-xs font-semibold text-slate-600">Total Eligible Students</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
            <div className="text-slate-600">
              <span className="font-semibold text-slate-900">
                {selectedSectionIds.length}
              </span>{' '}
              Sections ({resolution ? resolution.section_student_count : 0} enrolled)
            </div>
            <span className="text-slate-300">•</span>
            <div className="text-slate-600">
              <span className="font-semibold text-slate-900">
                {resolution ? resolution.individual_student_count : 0}
              </span>{' '}
              Specific Students
            </div>
            {resolution && resolution.overlap_count > 0 && (
              <>
                <span className="text-slate-300">•</span>
                <div className="text-slate-500">
                  <span className="font-semibold text-slate-700">
                    {resolution.overlap_count}
                  </span>{' '}
                  deduplicated overlap
                </div>
              </>
            )}
          </div>
        </div>

        {/* Warning if 0 students eligible */}
        {isZeroAudience && (
          <div className="mt-3 pt-3 border-t border-amber-200/80 flex items-center gap-2 text-xs font-semibold text-amber-800">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              Select at least one academic section or student before this assessment can be published.
            </span>
          </div>
        )}
      </div>
    </Card>
  );
};
