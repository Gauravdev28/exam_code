import React, { useState, useRef } from 'react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  FileSpreadsheet,
  Download,
  UploadCloud,
  CheckCircle2,
  XCircle,
  X,
  FileText,
  RefreshCw,
} from 'lucide-react';
import {
  downloadImportTemplate,
  previewSpreadsheetImport,
  confirmSpreadsheetImport,
} from '../../api/questions';

interface ImportQuestionsSpreadsheetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ImportQuestionsSpreadsheetModal: React.FC<ImportQuestionsSpreadsheetModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [previewData, setPreviewData] = useState<any | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successCount, setSuccessCount] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDownloadTemplate = async (format: 'csv' | 'xlsx') => {
    try {
      const blob = await downloadImportTemplate(format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `codeguard_questions_template.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert('Failed to download template. Please try again.');
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'csv' && ext !== 'xlsx') {
      setErrorMessage('Please upload a valid .csv or .xlsx spreadsheet file.');
      return;
    }

    setSelectedFile(file);
    setErrorMessage(null);
    setIsLoading(true);

    try {
      const res = await previewSpreadsheetImport(file);
      if (res.data) {
        setPreviewData(res.data);
      }
    } catch (err: any) {
      setErrorMessage(
        err.error?.message || err.message || 'Failed to parse spreadsheet.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!previewData || !previewData.rows) return;

    // Filter to rows that are VALID or DUPLICATE_WARNING (exclude ERROR)
    const validRows = previewData.rows.filter(
      (r: any) => r.status === 'VALID' || r.status === 'DUPLICATE_WARNING'
    );

    if (validRows.length === 0) {
      setErrorMessage('No valid rows available to import.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res = await confirmSpreadsheetImport(validRows);
      if (res.data) {
        setSuccessCount(res.data.created_count);
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 1200);
      }
    } catch (err: any) {
      setErrorMessage(
        err.error?.message || err.message || 'Failed to import questions.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setSelectedFile(null);
    setPreviewData(null);
    setErrorMessage(null);
    setSuccessCount(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <Card className="max-w-4xl w-full max-h-[90vh] flex flex-col p-6 space-y-5 bg-white border border-slate-200 shadow-2xl relative">
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-50 text-purple-700 border border-purple-200">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">Import Questions from Excel / CSV</h3>
              <p className="text-xs text-slate-600 font-medium">
                Upload a structured spreadsheet to batch-create questions in <strong className="text-slate-800">DRAFT</strong> state.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => handleDownloadTemplate('csv')}
              className="text-xs text-slate-700"
            >
              <Download className="w-3.5 h-3.5 mr-1" />
              CSV Template
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => handleDownloadTemplate('xlsx')}
              className="text-xs text-slate-700"
            >
              <Download className="w-3.5 h-3.5 mr-1" />
              Excel (.xlsx)
            </Button>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2.5 text-rose-800 text-xs">
            <XCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span className="font-semibold">{errorMessage}</span>
          </div>
        )}

        {successCount !== null && (
          <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center gap-2.5 text-emerald-800 text-xs">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            <span className="font-bold">
              Successfully imported {successCount} questions as DRAFTS into the Question Bank!
            </span>
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {!previewData ? (
            /* Upload Zone */
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-300 hover:border-purple-500 bg-slate-50/70 hover:bg-purple-50/30 rounded-xl p-8 text-center cursor-pointer transition-colors space-y-3"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                onChange={handleFileChange}
                className="hidden"
              />
              <div className="w-12 h-12 rounded-full bg-purple-100 text-purple-700 mx-auto flex items-center justify-center">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-bold text-slate-800">
                  Click to select or drag and drop your spreadsheet here
                </p>
                <p className="text-xs text-slate-600 font-medium">
                  Supports .csv and .xlsx files (up to 10MB)
                </p>
              </div>
            </div>
          ) : (
            /* Validation Summary & Preview Table */
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-2 text-xs">
                  <FileText className="w-4 h-4 text-slate-500" />
                  <span className="font-bold text-slate-900 font-mono">{selectedFile?.name}</span>
                  <span className="text-slate-500">
                    ({(selectedFile?.size || 0) / 1024 < 1024
                      ? `${Math.round((selectedFile?.size || 0) / 1024)} KB`
                      : `${((selectedFile?.size || 0) / (1024 * 1024)).toFixed(1)} MB`})
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setPreviewData(null);
                    setSelectedFile(null);
                  }}
                  className="text-xs text-slate-600 hover:text-slate-900"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1" />
                  Change File
                </Button>
              </div>

              {/* Counters */}
              <div className="grid grid-cols-4 gap-3">
                <div className="p-3 rounded-lg bg-slate-100 border border-slate-200 text-center">
                  <div className="text-lg font-bold text-slate-900">{previewData.total_rows}</div>
                  <div className="text-[11px] font-semibold text-slate-600 uppercase">Total Rows</div>
                </div>
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
                  <div className="text-lg font-bold text-emerald-700">{previewData.valid_count}</div>
                  <div className="text-[11px] font-semibold text-emerald-800 uppercase">Valid Rows</div>
                </div>
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-center">
                  <div className="text-lg font-bold text-amber-700">{previewData.duplicate_count}</div>
                  <div className="text-[11px] font-semibold text-amber-800 uppercase">Possible Duplicates</div>
                </div>
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-center">
                  <div className="text-lg font-bold text-rose-700">{previewData.error_count}</div>
                  <div className="text-[11px] font-semibold text-rose-800 uppercase">Rows with Errors</div>
                </div>
              </div>

              {/* Table of Rows */}
              <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                <div className="max-h-64 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-700 font-bold border-b border-slate-200 uppercase tracking-wider sticky top-0">
                      <tr>
                        <th className="p-2.5">Row</th>
                        <th className="p-2.5">Title</th>
                        <th className="p-2.5">Type</th>
                        <th className="p-2.5">Difficulty</th>
                        <th className="p-2.5">Points</th>
                        <th className="p-2.5">Validation Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-800">
                      {previewData.rows.map((row: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="p-2.5 font-mono text-slate-600">{row.row_number}</td>
                          <td className="p-2.5 font-semibold text-slate-900 max-w-xs truncate">
                            {row.data.title || '(No Title)'}
                          </td>
                          <td className="p-2.5 font-mono">
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[11px] font-semibold">
                              {row.data.question_type || '-'}
                            </span>
                          </td>
                          <td className="p-2.5">{row.data.difficulty || '-'}</td>
                          <td className="p-2.5 font-mono font-semibold">{row.data.points ?? 10}</td>
                          <td className="p-2.5">
                            {row.status === 'VALID' ? (
                              <Badge variant="success" size="sm">
                                VALID
                              </Badge>
                            ) : row.status === 'DUPLICATE_WARNING' ? (
                              <div className="space-y-1">
                                <Badge variant="warning" size="sm">
                                  POSSIBLE DUPLICATE
                                </Badge>
                                <div className="text-[10px] text-amber-800 font-medium">
                                  Matches: "{row.duplicate_of}"
                                </div>
                              </div>
                            ) : (
                              <div className="space-y-1">
                                <Badge variant="danger" size="sm">
                                  ERROR
                                </Badge>
                                <ul className="text-[10px] text-rose-700 font-semibold list-disc list-inside">
                                  {row.errors.map((e: string, i: number) => (
                                    <li key={i}>{e}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <p className="text-[11px] text-slate-600 font-medium">
                Questions are always saved in <strong className="text-slate-800">DRAFT</strong> state. Existing questions are never overwritten.
              </p>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
          <Button variant="secondary" size="sm" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          {previewData && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleConfirmImport}
              isLoading={isLoading}
              disabled={previewData.valid_count === 0}
            >
              Import {previewData.valid_count} Valid Questions as Drafts
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
};
