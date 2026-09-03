import React, { useEffect, useState } from 'react';
import { fetchSystemHealth } from '../api/health';
import { SystemHealthData } from '../types/api';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import {
  Server,
  Database,
  Zap,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Cpu,
  Layers,
  Lock,
  Code2,
  Clock,
  Archive,
  Eye
} from 'lucide-react';

export const HealthCheckPage: React.FC = () => {
  const [healthData, setHealthData] = useState<SystemHealthData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadHealth = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const response = await fetchSystemHealth();
      if (response.data) {
        setHealthData(response.data);
      }
      setLastChecked(new Date());
    } catch (err: any) {
      setErrorMsg(err.message || 'Unable to connect to CODEGUARD backend API');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
    // Auto-refresh diagnostics every 30s
    const timer = setInterval(loadHealth, 30000);
    return () => clearInterval(timer);
  }, []);

  const architectureChecklist = [
    { title: 'Question Versioning & Snapshots', desc: 'Immutable QuestionVersion & AssessmentSnapshot guarantee zero historical drift.', icon: Layers, status: 'Ready' },
    { title: 'Server-Authoritative Timer', desc: 'Exam deadline strictly enforced; 15s grace period reserved exclusively for state sync.', icon: Clock, status: 'Ready' },
    { title: 'Judge0 & SQL Sandbox Isolation', desc: 'Isolated cgroup execution for code; ephemeral container databases for SQL questions.', icon: Code2, status: 'Ready' },
    { title: 'Weighted Partial Scoring Engine', desc: 'Strict server validation enforcing sum(test_case.points) == question.total_points.', icon: Cpu, status: 'Ready' },
    { title: 'Secure WebSocket Authentication', desc: 'HttpOnly cookie handshake with independent per-connection consumer authorization.', icon: Lock, status: 'Ready' },
    { title: 'Staged 30-Day Data Retention', desc: 'Celery Beat automated purge with AssessmentSummary rollup & RetentionHold overrides.', icon: Archive, status: 'Ready' },
    { title: 'Proctoring Risk Engine', desc: 'Browser signals & non-blocking AI telemetry emitting weighted risk scores (0-100).', icon: Eye, status: 'Ready' },
    { title: 'Immutable Audit Log Service', desc: 'Application-enforced append-only audit trail intercepting all administrative events.', icon: ShieldCheck, status: 'Ready' },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-navy-950 border border-slate-800 p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Badge variant="success" dot size="md">
                Phase 1: Foundation Active
              </Badge>
              <span className="text-xs font-mono text-slate-400">
                Django 5.1 + React 18 + MySQL 8 + Redis 7
              </span>
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-white font-sans sm:text-4xl">
              CODEGUARD Core Gateway
            </h1>
            <p className="text-sm text-slate-400 max-w-2xl">
              Infrastructure foundation, base domain models, ASGI WebSocket channels, modular settings, and real-time health telemetry.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="md"
              onClick={loadHealth}
              isLoading={isLoading}
              className="bg-slate-900/80 backdrop-blur"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh Status
            </Button>
          </div>
        </div>
      </div>

      {/* Diagnostics Section */}
      <section id="diagnostics" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Server className="w-5 h-5 text-brand-400" />
            Live System Diagnostics
          </h2>
          {lastChecked && (
            <span className="text-xs text-slate-500 font-mono">
              Last probe: {lastChecked.toLocaleTimeString()}
            </span>
          )}
        </div>

        {errorMsg ? (
          <Card className="border-red-500/30 bg-red-500/5 p-6 flex items-start gap-4">
            <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-red-300">Backend Connection Notice</h3>
              <p className="text-xs text-red-200/80">{errorMsg}</p>
              <p className="text-xs text-slate-400 mt-2 font-mono">
                Verify that Django server is running on <code className="text-brand-400">http://127.0.0.1:8000</code>.
              </p>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Primary API Gateway */}
            <Card className="hover:border-brand-500/30 transition-colors">
              <div className="flex items-start justify-between">
                <div className="p-3 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
                  <Server className="w-6 h-6" />
                </div>
                <Badge variant={healthData?.status === 'healthy' ? 'success' : 'warning'} dot>
                  {healthData?.status?.toUpperCase() || 'CONNECTING'}
                </Badge>
              </div>
              <div className="mt-4 space-y-1">
                <h3 className="font-semibold text-slate-100 text-sm">Django ASGI Gateway</h3>
                <p className="text-xs text-slate-400">REST API & Channels WebSocket Router</p>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
                <span>Version</span>
                <span className="text-brand-400">{healthData?.version || '1.0.0-phase1'}</span>
              </div>
            </Card>

            {/* MySQL Database */}
            <Card className="hover:border-brand-500/30 transition-colors">
              <div className="flex items-start justify-between">
                <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  <Database className="w-6 h-6" />
                </div>
                <Badge
                  variant={healthData?.services?.database?.status === 'healthy' ? 'success' : 'danger'}
                  dot
                >
                  {healthData?.services?.database?.status?.toUpperCase() || 'PROBING'}
                </Badge>
              </div>
              <div className="mt-4 space-y-1">
                <h3 className="font-semibold text-slate-100 text-sm">MySQL Database</h3>
                <p className="text-xs text-slate-400">Relational persistence & strict invariants</p>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
                <span>Latency</span>
                <span className="text-blue-400">
                  {healthData?.services?.database?.latency_ms !== undefined
                    ? `${healthData.services.database.latency_ms} ms`
                    : 'N/A'}
                </span>
              </div>
            </Card>

            {/* Redis & Channels */}
            <Card className="hover:border-brand-500/30 transition-colors">
              <div className="flex items-start justify-between">
                <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Zap className="w-6 h-6" />
                </div>
                <Badge
                  variant={healthData?.services?.redis?.status === 'healthy' ? 'success' : 'warning'}
                  dot
                >
                  {healthData?.services?.redis?.status?.toUpperCase() || 'PROBING'}
                </Badge>
              </div>
              <div className="mt-4 space-y-1">
                <h3 className="font-semibold text-slate-100 text-sm">Redis & Celery Broker</h3>
                <p className="text-xs text-slate-400">Channel layer, cache & evaluation queues</p>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
                <span>Mode</span>
                <span className="text-emerald-400">
                  {healthData?.services?.redis?.mode ||
                    (healthData?.services?.redis?.latency_ms !== undefined
                      ? `${healthData.services.redis.latency_ms} ms`
                      : 'Active')}
                </span>
              </div>
            </Card>
          </div>
        )}
      </section>

      {/* Phase 1 Architecture Blueprint Section */}
      <section id="architecture" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-emerald-400" />
            Architecture Blueprint Specifications
          </h2>
          <span className="text-xs font-mono text-brand-400">8 / 8 Specifications Approved</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {architectureChecklist.map((item, idx) => {
            const Icon = item.icon;
            return (
              <Card key={idx} className="p-5 hover:border-slate-700 transition-all flex items-start gap-4">
                <div className="p-2.5 rounded-lg bg-slate-800/80 text-brand-400 border border-slate-700/60 flex-shrink-0">
                  <Icon className="w-5 h-5" />
                </div>
                <div className="space-y-1 flex-1">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-100">{item.title}</h4>
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-brand-400">
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-400" />
                      {item.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
                </div>
              </Card>
            );
          })}
        </div>
      </section>
    </div>
  );
};
