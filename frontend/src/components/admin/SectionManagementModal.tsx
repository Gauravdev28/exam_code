import React, { useState, useEffect, useCallback } from 'react';
import { fetchSections, createSection, updateSection, deleteSection } from '../../api/sections';
import { Section } from '../../types/section';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  Layers,
  Plus,
  Search,
  X,
  Power,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Users,
} from 'lucide-react';

interface SectionManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSectionsChanged?: () => void;
}

export const SectionManagementModal: React.FC<SectionManagementModalProps> = ({
  isOpen,
  onClose,
  onSectionsChanged,
}) => {
  const [sections, setSections] = useState<Section[]>([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // New section form state
  const [isAdding, setIsAdding] = useState(false);
  const [newCode, setNewCode] = useState('');
  const [newName, setNewName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadSections = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await fetchSections({ search: search.trim() || undefined });
      if (res.data) {
        setSections(res.data);
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || 'Failed to load sections.');
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    if (isOpen) {
      loadSections();
    }
  }, [isOpen, loadSections]);

  if (!isOpen) return null;

  const handleCreateSection = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    const cleanCode = newCode.trim().toUpperCase();
    const cleanName = newName.trim();

    if (!cleanCode || !cleanName) {
      setErrorMessage('Both Section Code and Section Name are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await createSection({
        code: cleanCode,
        name: cleanName,
        is_active: true,
      });
      if (res.data) {
        setSuccessMessage(`Section '${res.data.code}' created successfully.`);
        setNewCode('');
        setNewName('');
        setIsAdding(false);
        loadSections();
        if (onSectionsChanged) onSectionsChanged();
      }
    } catch (err: any) {
      const msg =
        err.error?.details?.code?.[0] ||
        err.error?.message ||
        err.message ||
        'Failed to create section.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (sec: Section) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const updated = await updateSection(sec.id, { is_active: !sec.is_active });
      if (updated.data) {
        const updatedSec = updated.data;
        setSections((prev) =>
          prev.map((s) => (s.id === sec.id ? { ...s, is_active: updatedSec.is_active } : s))
        );
        setSuccessMessage(
          `Section '${sec.code}' ${updatedSec.is_active ? 'activated' : 'deactivated'} successfully.`
        );
        if (onSectionsChanged) onSectionsChanged();
      }
    } catch (err: any) {
      setErrorMessage(err.error?.message || 'Failed to update section status.');
    }
  };

  const handleDelete = async (sec: Section) => {
    setErrorMessage(null);
    setSuccessMessage(null);

    if (sec.student_count && sec.student_count > 0) {
      const confirmDeact = window.confirm(
        `Section '${sec.code}' has ${sec.student_count} enrolled students and cannot be deleted.\n\nWould you like to DEACTIVATE this section instead?`
      );
      if (confirmDeact) {
        handleToggleActive(sec);
      }
      return;
    }

    const confirmed = window.confirm(
      `Are you sure you want to permanently delete section '${sec.code}'? This cannot be undone.`
    );
    if (!confirmed) return;

    try {
      await deleteSection(sec.id);
      setSections((prev) => prev.filter((s) => s.id !== sec.id));
      setSuccessMessage(`Section '${sec.code}' deleted successfully.`);
      if (onSectionsChanged) onSectionsChanged();
    } catch (err: any) {
      const msg = err.error?.details?.detail || err.error?.message || 'Failed to delete section.';
      setErrorMessage(msg);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
      <Card className="max-w-3xl w-full p-6 space-y-5 bg-white border border-slate-200 shadow-2xl rounded-2xl relative max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-50 text-purple-700 border border-purple-200">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Academic Sections</h2>
              <p className="text-xs text-slate-500">
                Classify students into sections for cohort targeted assessments.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Alerts */}
        {errorMessage && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2.5 text-xs text-rose-700">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}
        {successMessage && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2.5 text-xs text-emerald-700">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Action & Search Bar */}
        <div className="flex items-center justify-between gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by code (e.g. AIML-A) or name..."
              className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-purple-500"
            />
          </div>
          <Button
            variant={isAdding ? 'secondary' : 'primary'}
            size="sm"
            onClick={() => setIsAdding(!isAdding)}
          >
            {isAdding ? <X className="w-4 h-4 mr-1" /> : <Plus className="w-4 h-4 mr-1" />}
            {isAdding ? 'Cancel' : 'New Section'}
          </Button>
        </div>

        {/* Inline Create Form */}
        {isAdding && (
          <form
            onSubmit={handleCreateSection}
            className="p-4 bg-purple-50/50 border border-purple-100 rounded-xl space-y-3"
          >
            <div className="text-xs font-semibold text-purple-900">Add Academic Section</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Section Code <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                  placeholder="e.g. AIML-A"
                  required
                  className="w-full px-3 py-1.5 font-mono text-xs uppercase bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Section Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. AI & Machine Learning - Sec A"
                  required
                  className="w-full px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setIsAdding(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>
                Save Section
              </Button>
            </div>
          </form>
        )}

        {/* Sections List */}
        <div className="flex-1 overflow-y-auto min-h-[220px]">
          {isLoading ? (
            <div className="py-12 text-center text-slate-400 text-xs font-mono">
              Loading sections...
            </div>
          ) : sections.length === 0 ? (
            <div className="py-12 text-center text-slate-500 space-y-2">
              <Layers className="w-8 h-8 mx-auto text-slate-400" />
              <p className="text-xs font-semibold text-slate-700">No sections found</p>
              <p className="text-[11px] text-slate-400">
                Click "New Section" to create your first section.
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase font-semibold text-[10px] tracking-wider">
                <tr>
                  <th className="py-2.5 px-3">Code</th>
                  <th className="py-2.5 px-3">Name</th>
                  <th className="py-2.5 px-3">Students</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sections.map((sec) => (
                  <tr key={sec.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-2.5 px-3">
                      <Badge variant="purple" size="sm" className="font-mono font-bold">
                        {sec.code}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-800">{sec.name}</td>
                    <td className="py-2.5 px-3 text-slate-600 font-mono">
                      <span className="inline-flex items-center gap-1">
                        <Users className="w-3.5 h-3.5 text-slate-400" />
                        {sec.student_count ?? 0}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant={sec.is_active ? 'success' : 'neutral'} size="sm">
                        {sec.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          onClick={() => handleToggleActive(sec)}
                          title={sec.is_active ? 'Deactivate section' : 'Activate section'}
                          className={`p-1 rounded-md transition-colors ${
                            sec.is_active
                              ? 'text-amber-600 hover:bg-amber-50'
                              : 'text-emerald-600 hover:bg-emerald-50'
                          }`}
                        >
                          <Power className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(sec)}
                          title="Delete section"
                          className="p-1 rounded-md text-rose-500 hover:bg-rose-50 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 pt-3 flex justify-end">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </Card>
    </div>
  );
};
