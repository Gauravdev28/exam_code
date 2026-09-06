import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getAssessmentAttendance,
  exportAssessmentAttendance,
  AssessmentAttendanceData,
  AttendanceFilterParams,
} from '../../api/assessments';
import { fetchSections } from '../../api/sections';
import { Section } from '../../types/section';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import {
  Users,
  ArrowLeft,
  Search,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  FileText,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Layers,
} from 'lucide-react';

export const AdminAssessmentAttendancePage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId: string }>();

  const [data, setData] = useState<AssessmentAttendanceData | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters
  const [selectedSection, setSelectedSection] = useState<string>('ALL');
  const [attendanceStatus, setAttendanceStatus] = useState<string>('ALL');
  const [attemptStatus, setAttemptStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  // Export states
  const [isExportingXlsx, setIsExportingXlsx] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  // Load available sections for filter
  useEffect(() => {
    fetchSections({ active_only: true })
      .then((res) => {
        if (res.data) setSections(res.data);
      })
      .catch(() => {});
  }, []);

  const loadAttendance = useCallback(async () => {
    if (!assessmentId) return;
    setIsLoading(true);
    setErrorMessage(null);

    const params: AttendanceFilterParams = {
      page: currentPage,
      page_size: pageSize,
    };
    if (selectedSection !== 'ALL') params.section_id = selectedSection;
    if (attendanceStatus !== 'ALL') params.attendance_status = attendanceStatus;
    if (attemptStatus !== 'ALL') params.attempt_status = attemptStatus;
    if (searchQuery.trim()) params.search = searchQuery.trim();

    try {
      const res = await getAssessmentAttendance(assessmentId, params);
      if (res.data) {
        setData(res.data);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || err.message || 'Failed to load assessment attendance.');
    } finally {
      setIsLoading(false);
    }
  }, [assessmentId, currentPage, pageSize, selectedSection, attendanceStatus, attemptStatus, searchQuery]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const handleExport = async (format: 'xlsx' | 'pdf') => {
    if (!assessmentId) return;
    if (format === 'xlsx') setIsExportingXlsx(true);
    else setIsExportingPdf(true);

    const params: AttendanceFilterParams = {};
    if (selectedSection !== 'ALL') params.section_id = selectedSection;
    if (attendanceStatus !== 'ALL') params.attendance_status = attendanceStatus;
    if (attemptStatus !== 'ALL') params.attempt_status = attemptStatus;
    if (searchQuery.trim()) params.search = searchQuery.trim();

    try {
      const blob = await exportAssessmentAttendance(assessmentId, format, params);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `attendance_${assessmentId}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.error?.message || err.message || `Failed to export ${format.toUpperCase()} report.`);
    } finally {
      if (format === 'xlsx') setIsExportingXlsx(false);
      else setIsExportingPdf(false);
    }
  };

  const formatDuration = (seconds: number | null): string => {
    if (seconds === null || seconds === undefined) return 'N/A';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m === 0) return `${s}s`;
    return `${m}m ${s}s`;
  };

  const getAttendanceBadge = (status: string) => {
    if (status === 'ATTENDED') {
      return (
        <Badge variant="success" size="sm" className="font-semibold flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" /> Attended
        </Badge>
      );
    }
    return (
      <Badge variant="neutral" size="sm" className="font-semibold">
        Not Attended
      </Badge>
    );
  };

  const getAttemptBadge = (status: string) => {
    switch (status) {
      case 'SUBMITTED':
        return <Badge variant="success" size="sm">Submitted</Badge>;
      case 'IN_PROGRESS':
        return <Badge variant="info" size="sm">In Progress</Badge>;
      case 'EXPIRED':
        return <Badge variant="warning" size="sm">Expired</Badge>;
      case 'CANCELLED':
        return <Badge variant="danger" size="sm">Cancelled</Badge>;
      case 'NOT_STARTED':
      default:
        return <Badge variant="neutral" size="sm">Not Started</Badge>;
    }
  };

  const summary = data?.summary;
  const assessment = data?.assessment;
  const sectionsSummary = data?.sections || [];
  const rows = data?.results || [];
  const totalCount = data?.total_count || 0;
  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <div className="container mx-auto px-4 py-8 space-y-6 max-w-7xl">
      {/* Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <Link
            to="/admin/assessments"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors mb-2"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Assessments
          </Link>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-50 border border-teal-200 text-teal-600">
              <ClipboardList className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                  Assessment Attendance & Roster
                </h1>
                {assessment && (
                  <Badge variant={assessment.status === 'PUBLISHED' ? 'success' : 'neutral'} size="sm">
                    {assessment.status}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5 font-mono">
                {assessment?.title || 'Loading assessment...'}
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => handleExport('xlsx')}
            isLoading={isExportingXlsx}
            title="Download formatted Excel roster report"
          >
            <FileSpreadsheet className="w-4 h-4 mr-1.5 text-emerald-600" />
            Export XLSX
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => handleExport('pdf')}
            isLoading={isExportingPdf}
            title="Download printable PDF attendance scorecard"
          >
            <FileText className="w-4 h-4 mr-1.5 text-rose-600" />
            Export PDF
          </Button>
        </div>
      </div>

      {/* Pre-Exam Context Alert */}
      {summary?.is_pre_exam && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3 text-amber-900 text-xs">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-bold">Assessment Has Not Started Yet (Pre-Exam Window)</span>
            <p className="text-amber-800">
              This assessment is scheduled to start on {new Date(assessment!.start_datetime).toLocaleString()}. Students who have not yet started are awaiting the scheduled start time and are not considered absent.
            </p>
          </div>
        </div>
      )}

      {/* Error Notice */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
        <Card className="p-4 space-y-1">
          <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Total Assigned</span>
          <div className="text-2xl font-extrabold text-slate-900 font-mono">
            {summary ? summary.total_assigned : '-'}
          </div>
          <span className="text-[10px] text-slate-400">Authoritative assignments</span>
        </Card>

        <Card className="p-4 space-y-1 bg-emerald-50/50 border-emerald-200">
          <span className="text-[10px] text-emerald-800 font-semibold uppercase tracking-wider">Attended</span>
          <div className="text-2xl font-extrabold text-emerald-700 font-mono">
            {summary ? summary.total_attended : '-'}
          </div>
          <span className="text-[10px] text-emerald-600 font-semibold">
            {summary ? `${summary.attendance_percentage}%` : '0.0%'} attendance rate
          </span>
        </Card>

        <Card className="p-4 space-y-1 bg-blue-50/50 border-blue-200">
          <span className="text-[10px] text-blue-800 font-semibold uppercase tracking-wider">In Progress</span>
          <div className="text-2xl font-extrabold text-blue-700 font-mono">
            {summary ? summary.total_in_progress : '-'}
          </div>
          <span className="text-[10px] text-blue-600">Active test attempts</span>
        </Card>

        <Card className="p-4 space-y-1 bg-purple-50/50 border-purple-200">
          <span className="text-[10px] text-purple-800 font-semibold uppercase tracking-wider">Submitted</span>
          <div className="text-2xl font-extrabold text-purple-700 font-mono">
            {summary ? summary.total_submitted : '-'}
          </div>
          <span className="text-[10px] text-purple-600">Completed attempts</span>
        </Card>

        <Card className="p-4 space-y-1">
          <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
            {summary?.is_pre_exam ? 'Awaiting Start' : 'Not Attended'}
          </span>
          <div className="text-2xl font-extrabold text-slate-700 font-mono">
            {summary ? summary.total_not_attended : '-'}
          </div>
          <span className="text-[10px] text-slate-400">
            {summary?.is_pre_exam ? 'Scheduled candidates' : 'No attempt started'}
          </span>
        </Card>

        <Card className="p-4 space-y-1 bg-slate-50 border-slate-200">
          <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Attendance %</span>
          <div className="text-2xl font-extrabold text-slate-900 font-mono">
            {summary ? `${summary.attendance_percentage}%` : '0.0%'}
          </div>
          <span className="text-[10px] text-slate-500">Student deduplicated</span>
        </Card>
      </div>

      {/* Section Breakdown Card */}
      {sectionsSummary.length > 0 && (
        <Card className="p-5 space-y-3">
          <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
            <Layers className="w-4 h-4 text-purple-600" />
            <h2 className="text-sm font-bold text-slate-900">Academic Section Breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-3 py-2">Section Name</th>
                  <th className="px-3 py-2 text-center">Assigned</th>
                  <th className="px-3 py-2 text-center">Attended</th>
                  <th className="px-3 py-2 text-center">In Progress</th>
                  <th className="px-3 py-2 text-center">Submitted</th>
                  <th className="px-3 py-2 text-center">Not Attended</th>
                  <th className="px-3 py-2 text-right">Attendance %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {sectionsSummary.map((sec, idx) => (
                  <tr key={sec.section_id || `sec-${idx}`} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-3 py-2 font-sans font-bold text-slate-900">{sec.section_name}</td>
                    <td className="px-3 py-2 text-center font-bold">{sec.assigned}</td>
                    <td className="px-3 py-2 text-center text-emerald-700 font-bold">{sec.attended}</td>
                    <td className="px-3 py-2 text-center text-blue-700">{sec.in_progress}</td>
                    <td className="px-3 py-2 text-center text-purple-700">{sec.submitted}</td>
                    <td className="px-3 py-2 text-center text-slate-500">{sec.not_attended}</td>
                    <td className="px-3 py-2 text-right font-bold text-emerald-700">{sec.attendance_percentage}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Filter & Search Bar */}
      <Card className="p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search student, roll number, email..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          <div>
            <select
              value={selectedSection}
              onChange={(e) => {
                setSelectedSection(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="ALL">All Sections</option>
              {sections.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.code})
                </option>
              ))}
              <option value="unassigned">Direct / Unassigned Section</option>
            </select>
          </div>

          <div>
            <select
              value={attendanceStatus}
              onChange={(e) => {
                setAttendanceStatus(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="ALL">All Attendance Statuses</option>
              <option value="ATTENDED">Attended (Started Attempt)</option>
              <option value="NOT_ATTENDED">Not Attended</option>
            </select>
          </div>

          <div>
            <select
              value={attemptStatus}
              onChange={(e) => {
                setAttemptStatus(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="ALL">All Attempt Statuses</option>
              <option value="NOT_STARTED">Not Started</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="EXPIRED">Expired</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Student Attendance Roster Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-500 font-mono">Loading authoritative attendance roster...</p>
          </div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <Users className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-slate-600 text-sm font-semibold">No assigned students matching the selected criteria.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="px-4 py-3.5">Student / EUID</th>
                  <th className="px-4 py-3.5">Roll Number</th>
                  <th className="px-4 py-3.5">Section</th>
                  <th className="px-4 py-3.5">Attendance</th>
                  <th className="px-4 py-3.5">Attempt Status</th>
                  <th className="px-4 py-3.5">Started At</th>
                  <th className="px-4 py-3.5">Submitted At</th>
                  <th className="px-4 py-3.5 text-right">Time Used</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {rows.map((r) => (
                  <tr key={r.student_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3.5 max-w-xs">
                      <div className="font-sans font-bold text-slate-900 text-sm truncate">
                        {r.student_name}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate">{r.email}</div>
                      {r.euid && (
                        <div className="text-[10px] text-teal-700 font-mono font-semibold">
                          EUID: {r.euid}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3.5 font-bold text-slate-900">
                      {r.roll_number || 'N/A'}
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 font-semibold text-[11px]">
                        {r.section}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      {getAttendanceBadge(r.attendance_status)}
                    </td>
                    <td className="px-4 py-3.5">
                      {getAttemptBadge(r.attempt_status)}
                    </td>
                    <td className="px-4 py-3.5 text-slate-600">
                      {r.started_at ? new Date(r.started_at).toLocaleString() : '-'}
                    </td>
                    <td className="px-4 py-3.5 text-slate-600">
                      {r.submitted_at ? new Date(r.submitted_at).toLocaleString() : '-'}
                    </td>
                    <td className="px-4 py-3.5 text-right font-bold text-slate-900">
                      {formatDuration(r.duration_seconds)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-200 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-500">
              Showing {(currentPage - 1) * pageSize + 1} to{' '}
              {Math.min(currentPage * pageSize, totalCount)} of {totalCount} assigned students
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                Previous
              </Button>
              <span className="text-slate-700 font-bold px-2">
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
                <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default AdminAssessmentAttendancePage;
