import React, { useState, useEffect } from 'react';
import { AdminAPI } from '../../api/admin';
import { SecurityAuditLog } from '../../types/admin';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { ShieldCheck, RefreshCw, Filter, Clock, Search, ChevronLeft, ChevronRight } from 'lucide-react';

export const SecurityAuditTab: React.FC = () => {
  const [logs, setLogs] = useState<SecurityAuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [actionFilter, setActionFilter] = useState<string>('ALL');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const loadAuditLogs = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {
        limit: pageSize,
        offset: (page - 1) * pageSize,
      };
      if (actionFilter !== 'ALL') {
        params.action = actionFilter;
      }
      if (roleFilter !== 'ALL') {
        params.role = roleFilter;
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }
      const data = await AdminAPI.getSecurityAuditLogs(params);
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to load security audit logs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAuditLogs();
  }, [actionFilter, roleFilter, page]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadAuditLogs();
  };

  const getActionBadgeVariant = (action: string): 'warning' | 'danger' | 'success' | 'info' | 'neutral' => {
    switch (action) {
      case 'PASSWORD_RESET':
      case 'PASSWORD_CHANGED':
        return 'warning';
      case 'STUDENT_DISABLED':
      case 'ADMIN_DISABLED':
      case 'ADMIN_DELETED':
      case 'STUDENT_DELETED':
        return 'danger';
      case 'STUDENT_ENABLED':
      case 'ADMIN_ENABLED':
        return 'success';
      case 'ADMIN_CREATED':
      case 'STUDENT_CREATED':
      case 'ADMIN_UPDATED':
      case 'STUDENT_UPDATED':
        return 'info';
      default:
        return 'neutral';
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Top Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-900">Security Audit Ledger</h4>
            <p className="text-xs text-slate-500">
              Append-only immutable record of credentials and account lifecycle actions ({total} total events)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Search Form */}
          <form onSubmit={handleSearchSubmit} className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search audit trail..."
              className="pl-8 pr-3 py-1.5 text-xs rounded-lg bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 w-44 sm:w-56"
            />
          </form>

          {/* Role Filter */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg text-xs">
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
                setPage(1);
              }}
              className="bg-transparent text-slate-700 font-medium text-xs border-0 focus:ring-0 cursor-pointer pr-3"
            >
              <option value="ALL">All Roles</option>
              <option value="ADMIN">Admin</option>
              <option value="STUDENT">Student</option>
            </select>
          </div>

          {/* Action Filter */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-500 ml-1.5" />
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              className="bg-transparent text-slate-700 font-medium text-xs border-0 focus:ring-0 cursor-pointer pr-4"
            >
              <option value="ALL">All Actions</option>
              <option value="PASSWORD_RESET">Password Resets</option>
              <option value="PASSWORD_CHANGED">Password Changed</option>
              <option value="ADMIN_CREATED">Admin Created</option>
              <option value="ADMIN_UPDATED">Admin Updated</option>
              <option value="ADMIN_DELETED">Admin Deleted</option>
              <option value="ADMIN_DISABLED">Admin Disabled</option>
              <option value="ADMIN_ENABLED">Admin Enabled</option>
              <option value="STUDENT_CREATED">Student Created</option>
              <option value="STUDENT_UPDATED">Student Updated</option>
              <option value="STUDENT_DELETED">Student Deleted</option>
              <option value="STUDENT_DISABLED">Student Disabled</option>
              <option value="STUDENT_ENABLED">Student Enabled</option>
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={loadAuditLogs}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Logs Table */}
      <Card className="overflow-hidden border border-slate-200 bg-white">
        {isLoading && logs.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-5 h-5 animate-spin text-emerald-600" />
            Loading security activity...
          </div>
        ) : logs.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs">
            No security audit records match the current filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Performed By (Actor)</th>
                  <th className="py-3 px-4">Affected Account</th>
                  <th className="py-3 px-4">Administrative Reason</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4 text-right">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4 whitespace-nowrap">
                      <Badge variant={getActionBadgeVariant(log.action)}>
                        {log.action.replace('_', ' ')}
                      </Badge>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="space-y-0.5">
                        <div className="font-semibold text-slate-900">{log.actor_name}</div>
                        {log.actor_admin_id && (
                          <span className="font-mono text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                            {log.actor_admin_id}
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="space-y-0.5">
                        <div className="text-slate-800 font-mono text-[11px]">{log.target_email || log.target_id}</div>
                        {log.target_identity && (
                          <span className="font-mono text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded border border-emerald-200">
                            {log.target_identity}
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-4 max-w-xs">
                      <p className="text-slate-600 truncate" title={log.reason || 'No reason provided'}>
                        {log.reason || <span className="text-slate-400 italic">None specified</span>}
                      </p>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap text-slate-500">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span>{formatDate(log.created_at)}</span>
                      </div>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap text-right">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        log.result === 'SUCCESS' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'
                      }`}>
                        {log.result}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        {total > pageSize && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 border-t border-slate-200 bg-slate-50 text-xs">
            <span className="text-slate-500 font-mono">
              Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} events
            </span>
            <div className="flex items-center gap-2 self-end sm:self-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || isLoading}
                className="px-2.5 py-1 text-xs flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Previous</span>
              </Button>
              <span className="font-mono text-slate-700 px-2">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || isLoading}
                className="px-2.5 py-1 text-xs flex items-center gap-1"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
