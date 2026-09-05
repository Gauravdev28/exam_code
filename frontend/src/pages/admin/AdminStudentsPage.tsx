import React, { useState, useEffect, useCallback } from 'react';
import { fetchStudents, disableStudent, enableStudent } from '../../api/students';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { PageHeader } from '../../components/common/PageHeader';
import { AddStudentModal } from '../../components/admin/AddStudentModal';
import { BulkImportModal } from '../../components/admin/BulkImportModal';
import { StudentDetailsModal } from '../../components/admin/StudentDetailsModal';
import {
  Users,
  UserPlus,
  UploadCloud,
  Search,
  Filter,
  Eye,
  Power,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { StudentProfile } from '../../types/student';

export const AdminStudentsPage: React.FC = () => {
  const [students, setStudents] = useState<StudentProfile[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize] = useState<number>(15);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<StudentProfile | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  const loadStudents = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const activeParam =
        statusFilter === 'active' ? true : statusFilter === 'disabled' ? false : undefined;

      const res = await fetchStudents({
        page: currentPage,
        page_size: pageSize,
        search: searchTerm.trim() || undefined,
        is_active: activeParam,
      });

      if (res.data) {
        setStudents(res.data.results);
        setTotalCount(res.data.count);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || 'Failed to fetch student records.');
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, pageSize, searchTerm, statusFilter]);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    loadStudents();
  };

  const handleQuickToggleStatus = async (student: StudentProfile) => {
    try {
      const res = student.is_active
        ? await disableStudent(student.id)
        : await enableStudent(student.id);
      if (res.data) {
        setStudents((prev) =>
          prev.map((s) => (s.id === student.id ? { ...s, is_active: res.data!.is_active } : s))
        );
      }
    } catch (err: any) {
      alert(err.error?.message || 'Failed to update account status.');
    }
  };

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Banner */}
      <PageHeader
        icon={<Users className="w-6 h-6" />}
        title="Student Management"
        badge={<Badge variant="neutral" size="sm">ADMIN</Badge>}
        description="Enroll students, generate EUIDs, oversee account states, and manage bulk CSV/Excel rosters."
        actions={
          <div className="flex items-center gap-3">
            <Button variant="secondary" size="md" onClick={() => setIsImportOpen(true)}>
              <UploadCloud className="w-4 h-4 text-purple-600 mr-1.5" />
              Bulk Import
            </Button>
            <Button variant="primary" size="md" onClick={() => setIsAddOpen(true)}>
              <UserPlus className="w-4 h-4 mr-1.5" />
              Enroll Student
            </Button>
          </div>
        }
      />

      {/* Filter & Search Bar */}
      <Card className="p-4">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-4 justify-between">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Search className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by Roll Number, EUID, or Email address..."
              className="w-full pl-10 pr-4 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 text-xs focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <Filter className="w-3.5 h-3.5" />
              <span className="font-medium">Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="bg-white border border-slate-300 text-slate-800 py-1.5 px-3 rounded-lg text-xs font-medium focus:ring-2 focus:ring-emerald-500"
              >
                <option value="all">All Accounts</option>
                <option value="active">Active Only</option>
                <option value="disabled">Disabled Only</option>
              </select>
            </div>
            <Button type="submit" variant="secondary" size="sm">
              Apply
            </Button>
          </div>
        </form>
      </Card>

      {/* Students Table */}
      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-500 space-y-3">
            <svg className="animate-spin h-7 w-7 text-emerald-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-xs font-mono">Loading student roster...</span>
          </div>
        ) : errorMessage ? (
          <div className="py-16 text-center text-rose-600 text-xs space-y-2">
            <ShieldAlert className="w-8 h-8 mx-auto" />
            <p>{errorMessage}</p>
          </div>
        ) : students.length === 0 ? (
          <div className="py-20 text-center text-slate-500 space-y-3">
            <Users className="w-10 h-10 mx-auto text-slate-400" />
            <p className="text-sm font-semibold text-slate-800">No students found.</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Get started by enrolling a student individually or importing a class roster via CSV/XLSX.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto text-xs">
            <table className="w-full text-left font-mono">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="p-3.5">Roll Number</th>
                  <th className="p-3.5">EUID</th>
                  <th className="p-3.5">Email</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">First Login</th>
                  <th className="p-3.5">Enrolled Date</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {students.map((student) => (
                  <tr key={student.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">{student.roll_number}</td>
                    <td className="p-3.5 text-emerald-700 font-semibold">{student.euid}</td>
                    <td className="p-3.5 text-slate-800 font-sans">{student.email}</td>
                    <td className="p-3.5">
                      <Badge variant={student.is_active ? 'success' : 'danger'} size="sm">
                        {student.is_active ? 'ACTIVE' : 'DISABLED'}
                      </Badge>
                    </td>
                    <td className="p-3.5">
                      <span className={student.first_login_required ? 'text-amber-800 font-semibold bg-amber-50 px-2 py-0.5 rounded border border-amber-200' : 'text-slate-700 font-semibold bg-slate-100 px-2 py-0.5 rounded border border-slate-200'}>
                        {student.first_login_required ? 'Pending' : 'Completed'}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-700 font-semibold font-sans">
                      {new Date(student.created_at).toLocaleDateString()}
                    </td>
                    <td className="p-3.5 text-right space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelectedStudent(student);
                          setIsDetailsOpen(true);
                        }}
                        className="text-slate-600 hover:text-slate-900"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" />
                        View
                      </Button>
                      <Button
                        variant={student.is_active ? 'ghost' : 'secondary'}
                        size="sm"
                        onClick={() => handleQuickToggleStatus(student)}
                        className={student.is_active ? 'text-rose-600 hover:bg-rose-50' : 'text-emerald-700'}
                      >
                        <Power className="w-3.5 h-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {!isLoading && students.length > 0 && (
          <div className="flex items-center justify-between p-4 border-t border-slate-200 text-xs text-slate-500">
            <span>
              Showing <strong className="text-slate-900">{(currentPage - 1) * pageSize + 1}</strong> to{' '}
              <strong className="text-slate-900">{Math.min(currentPage * pageSize, totalCount)}</strong> of{' '}
              <strong className="text-slate-900">{totalCount}</strong> students
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="font-mono text-slate-700 font-medium">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Modals */}
      <AddStudentModal
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        onSuccess={() => {
          loadStudents();
        }}
      />

      <BulkImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onSuccess={() => {
          loadStudents();
        }}
      />

      <StudentDetailsModal
        student={selectedStudent}
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        onUpdate={() => {
          loadStudents();
        }}
        onDelete={() => {
          loadStudents();
        }}
      />
    </div>
  );
};

export default AdminStudentsPage;
