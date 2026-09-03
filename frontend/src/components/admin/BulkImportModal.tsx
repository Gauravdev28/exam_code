import React, { useState } from 'react';
import { previewStudentImport, confirmStudentImport } from '../../api/students';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  UploadCloud,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  FileText,
  X,
  ArrowRight,
  Download,
} from 'lucide-react';
import { ImportPreviewReport, ImportConfirmResult } from '../../types/student';

interface BulkImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const BulkImportModal: React.FC<BulkImportModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewReport, setPreviewReport] = useState<ImportPreviewReport | null>(null);
  const [importResult, setImportResult] = useState<ImportConfirmResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setErrorMessage(null);
    }
  };

  const handleDownloadSample = () => {
    const csvContent = "data:text/csv;charset=utf-8,Roll Number,Email\nBETN1AI25001,student1@university.edu\nBETN1AI25002,student2@university.edu\nBETN1AI25003,student3@university.edu";
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "codeguard_student_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleUploadAndPreview = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select a CSV or Excel file to upload.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await previewStudentImport(selectedFile);
      if (res.data) {
        setPreviewReport(res.data);
        setStep(2);
      }
    } catch (err: any) {
      const msg = err.error?.message || err.message || 'Failed to parse and validate file.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!previewReport) return;

    // Filter only valid rows
    const validStudents = previewReport.rows
      .filter((r) => r.status === 'VALID')
      .map((r) => ({
        email: r.email,
        roll_number: r.roll_number,
      }));

    if (validStudents.length === 0) {
      setErrorMessage('No valid rows available to import.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await confirmStudentImport({
        filename: selectedFile?.name || 'import.csv',
        students: validStudents,
      });
      if (res.data) {
        setImportResult(res.data);
        setStep(3);
        onSuccess();
      }
    } catch (err: any) {
      const msg = err.error?.message || err.message || 'Failed to create student accounts.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setStep(1);
    setSelectedFile(null);
    setPreviewReport(null);
    setImportResult(null);
    setErrorMessage(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm">
      <Card className="max-w-3xl w-full p-6 space-y-6 border-slate-800 shadow-2xl relative max-h-[90vh] flex flex-col">
        <button
          onClick={handleReset}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Wizard Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Bulk Student Account Import</h3>
              <p className="text-xs text-slate-400">Step {step} of 3 — CSV & Excel Wizard</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className={`px-2 py-0.5 rounded ${step >= 1 ? 'bg-brand-500/20 text-brand-400' : 'text-slate-600'}`}>1. Upload</span>
            <ArrowRight className="w-3 h-3 text-slate-600" />
            <span className={`px-2 py-0.5 rounded ${step >= 2 ? 'bg-brand-500/20 text-brand-400' : 'text-slate-600'}`}>2. Preview</span>
            <ArrowRight className="w-3 h-3 text-slate-600" />
            <span className={`px-2 py-0.5 rounded ${step === 3 ? 'bg-brand-500/20 text-brand-400' : 'text-slate-600'}`}>3. Complete</span>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start gap-2.5 text-red-300 text-xs">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* STEP 1: Upload */}
        {step === 1 && (
          <div className="space-y-5 py-4">
            <div className="border-2 border-dashed border-slate-800 hover:border-brand-500/50 rounded-2xl p-8 text-center space-y-4 bg-slate-900/40 transition-colors">
              <div className="w-12 h-12 rounded-full bg-brand-500/10 text-brand-400 flex items-center justify-center mx-auto">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-white">Select Student Roster File</p>
                <p className="text-xs text-slate-400">Supports .CSV and .XLSX files up to 5 MB</p>
              </div>
              <input
                type="file"
                accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                onChange={handleFileChange}
                className="block w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-brand-400 hover:file:bg-slate-700 cursor-pointer max-w-xs mx-auto"
              />
              {selectedFile && (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 text-xs font-mono text-emerald-400 border border-emerald-500/20">
                  <FileText className="w-3.5 h-3.5" />
                  <span>{selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={handleDownloadSample}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-brand-400 font-mono transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download Sample CSV Template</span>
              </button>
              <Button
                variant="primary"
                size="md"
                onClick={handleUploadAndPreview}
                isLoading={isLoading}
                disabled={!selectedFile}
              >
                Parse & Preview Roster
              </Button>
            </div>
          </div>
        )}

        {/* STEP 2: Preview & Validation Table */}
        {step === 2 && previewReport && (
          <div className="space-y-4 flex-1 flex flex-col overflow-hidden">
            {/* Stat Pill Summary */}
            <div className="grid grid-cols-4 gap-3 text-center text-xs">
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-400">Total Rows</span>
                <p className="text-base font-bold text-white font-mono">{previewReport.total_rows}</p>
              </div>
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <span className="text-emerald-400 font-medium">Valid for Creation</span>
                <p className="text-base font-bold text-emerald-400 font-mono">{previewReport.valid_count}</p>
              </div>
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <span className="text-amber-400 font-medium">Duplicates Found</span>
                <p className="text-base font-bold text-amber-400 font-mono">{previewReport.duplicate_count}</p>
              </div>
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <span className="text-red-400 font-medium">Invalid Rows</span>
                <p className="text-base font-bold text-red-400 font-mono">{previewReport.invalid_count}</p>
              </div>
            </div>

            {/* Scrollable Table */}
            <div className="flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/60 max-h-64 text-xs">
              <table className="w-full text-left font-mono">
                <thead className="sticky top-0 bg-slate-900 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="p-2.5">Row</th>
                    <th className="p-2.5">Roll Number</th>
                    <th className="p-2.5">Email</th>
                    <th className="p-2.5">EUID Preview</th>
                    <th className="p-2.5">Status</th>
                    <th className="p-2.5">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {previewReport.rows.map((row) => (
                    <tr key={row.row_number} className={row.status !== 'VALID' ? 'bg-red-500/5' : ''}>
                      <td className="p-2.5 text-slate-500">#{row.row_number}</td>
                      <td className="p-2.5 font-semibold text-white">{row.roll_number}</td>
                      <td className="p-2.5">{row.email}</td>
                      <td className="p-2.5 text-brand-400">{row.euid || 'N/A'}</td>
                      <td className="p-2.5">
                        <Badge
                          variant={
                            row.status === 'VALID'
                              ? 'success'
                              : row.status === 'DUPLICATE'
                              ? 'warning'
                              : 'danger'
                          }
                          size="sm"
                        >
                          {row.status}
                        </Badge>
                      </td>
                      <td className="p-2.5 text-slate-400 max-w-xs truncate">
                        {row.errors.length > 0 ? row.errors.join('; ') : 'Ready to create'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800">
              <Button variant="ghost" size="sm" onClick={() => setStep(1)}>
                Back to Upload
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleConfirmImport}
                isLoading={isLoading}
                disabled={previewReport.valid_count === 0}
              >
                Confirm & Create {previewReport.valid_count} Students
              </Button>
            </div>
          </div>
        )}

        {/* STEP 3: Complete / Summary */}
        {step === 3 && importResult && (
          <div className="space-y-6 py-6 text-center">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/10">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xl font-bold text-white">Import Complete!</h3>
              <p className="text-xs text-slate-400">
                Successfully created <span className="text-emerald-400 font-bold">{importResult.created_count}</span> student accounts.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 max-w-sm mx-auto text-xs font-mono">
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-slate-400">Total Submitted</span>
                <p className="text-base font-bold text-white">{importResult.total_submitted}</p>
              </div>
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <span className="text-emerald-400">Accounts Created</span>
                <p className="text-base font-bold text-emerald-400">{importResult.created_count}</p>
              </div>
            </div>

            <Button variant="primary" size="md" onClick={handleReset} className="mx-auto">
              Close & Return to Student List
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
};

export default BulkImportModal;
