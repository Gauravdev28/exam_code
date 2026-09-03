import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { testAdminAccess, testStudentAccess } from '../api/auth';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import {
  UserCheck,
  ShieldCheck,
  LogOut,
  Key,
  Activity,
  CheckCircle2,
  XCircle
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();

  const [testResult, setTestResult] = useState<{
    endpoint: string;
    status: 'success' | 'error';
    statusCode?: number;
    data?: any;
    message?: string;
  } | null>(null);
  const [testingEndpoint, setTestingEndpoint] = useState<string | null>(null);

  const handleTestAdmin = async () => {
    setTestingEndpoint('admin');
    setTestResult(null);
    try {
      const res = await testAdminAccess();
      setTestResult({
        endpoint: '/api/v1/auth/admin-only/',
        status: 'success',
        statusCode: 200,
        data: res.data,
        message: res.message || 'Access Authorized (200 OK)',
      });
    } catch (err: any) {
      setTestResult({
        endpoint: '/api/v1/auth/admin-only/',
        status: 'error',
        statusCode: 403,
        data: err.error || err,
        message: err.error?.message || 'Access Forbidden (403 Permission Denied)',
      });
    } finally {
      setTestingEndpoint(null);
    }
  };

  const handleTestStudent = async () => {
    setTestingEndpoint('student');
    setTestResult(null);
    try {
      const res = await testStudentAccess();
      setTestResult({
        endpoint: '/api/v1/auth/student-only/',
        status: 'success',
        statusCode: 200,
        data: res.data,
        message: res.message || 'Access Authorized (200 OK)',
      });
    } catch (err: any) {
      setTestResult({
        endpoint: '/api/v1/auth/student-only/',
        status: 'error',
        statusCode: 403,
        data: err.error || err,
        message: err.error?.message || 'Access Forbidden (403 Permission Denied)',
      });
    } finally {
      setTestingEndpoint(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-navy-950 border border-slate-800 p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Badge variant={user?.role === 'ADMIN' ? 'info' : 'success'} dot size="md">
                {user?.role} ROLE
              </Badge>
              <Badge variant={user?.is_active ? 'success' : 'danger'}>
                {user?.is_active ? 'ACCOUNT ACTIVE' : 'ACCOUNT DISABLED'}
              </Badge>
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-white font-sans sm:text-4xl">
              Welcome, {user?.email}
            </h1>
            <p className="text-sm text-slate-400 max-w-2xl font-mono text-xs">
              UUID: {user?.id}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/health">
              <Button variant="secondary" size="md">
                <Activity className="w-4 h-4 text-brand-400" />
                System Health
              </Button>
            </Link>
            <Button variant="outline" size="md" onClick={logout} className="hover:border-red-500/40 hover:text-red-300">
              <LogOut className="w-4 h-4" />
              Sign Out
            </Button>
          </div>
        </div>
      </div>

      {/* User Profile Card & Role Verification Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile Card */}
        <Card className="space-y-6">
          <div className="flex items-center gap-3 pb-4 border-b border-slate-800">
            <div className="p-3 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
              <UserCheck className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-sm">Authenticated Identity</h3>
              <p className="text-xs text-slate-400 font-mono">Session-backed DRF Auth</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
              <span className="text-slate-400">Email Address</span>
              <span className="text-slate-200 font-semibold">{user?.email}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
              <span className="text-slate-400">Role Identifier</span>
              <span className="text-brand-400 font-bold">{user?.role}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
              <span className="text-slate-400">Staff Privileges</span>
              <span className={user?.is_staff ? 'text-blue-400' : 'text-slate-400'}>
                {user?.is_staff ? 'TRUE' : 'FALSE'}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
              <span className="text-slate-400">Account Status</span>
              <span className="text-brand-400 font-semibold">ACTIVE</span>
            </div>
            <div className="flex justify-between py-1.5 font-mono">
              <span className="text-slate-400">Created At</span>
              <span className="text-slate-400">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
              </span>
            </div>
          </div>
        </Card>

        {/* RBAC Verification Card */}
        <Card className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <Key className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-white text-sm">Role-Based Access Control (RBAC) Verification</h3>
                <p className="text-xs text-slate-400">Test server-side authorization enforcement live</p>
              </div>
            </div>
            <Badge variant="neutral">SERVER ENFORCED</Badge>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-slate-900/90 border border-slate-800 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <ShieldCheck className="w-4 h-4 text-blue-400" />
                <span>Admin Resource Test</span>
              </div>
              <p className="text-xs text-slate-400">
                Calls <code className="text-brand-400 font-mono">/api/v1/auth/admin-only/</code> guarded by <code className="text-slate-300 font-mono">IsAdmin</code>.
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleTestAdmin}
                isLoading={testingEndpoint === 'admin'}
                className="w-full"
              >
                Test Admin Authorization
              </Button>
            </div>

            <div className="p-4 rounded-lg bg-slate-900/90 border border-slate-800 space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Student Resource Test</span>
              </div>
              <p className="text-xs text-slate-400">
                Calls <code className="text-brand-400 font-mono">/api/v1/auth/student-only/</code> guarded by <code className="text-slate-300 font-mono">IsStudent</code>.
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleTestStudent}
                isLoading={testingEndpoint === 'student'}
                className="w-full"
              >
                Test Student Authorization
              </Button>
            </div>
          </div>

          {/* Test Result Inspector */}
          {testResult && (
            <div
              className={`p-4 rounded-lg border text-xs space-y-2 font-mono ${
                testResult.status === 'success'
                  ? 'bg-brand-500/10 border-brand-500/30 text-brand-300'
                  : 'bg-red-500/10 border-red-500/30 text-red-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold">
                  {testResult.status === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 text-brand-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400" />
                  )}
                  <span>Endpoint: {testResult.endpoint}</span>
                </div>
                <Badge variant={testResult.status === 'success' ? 'success' : 'danger'}>
                  HTTP {testResult.statusCode}
                </Badge>
              </div>
              <p className="text-slate-300">{testResult.message}</p>
              <pre className="p-3 rounded bg-slate-950/80 border border-slate-800 text-slate-300 overflow-x-auto text-[11px]">
                {JSON.stringify(testResult.data, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default DashboardPage;
