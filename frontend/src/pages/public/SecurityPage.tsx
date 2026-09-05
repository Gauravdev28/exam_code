import React from 'react';
import { Shield, Lock, Cpu, Clock, Database, Key, UserCheck, FileText } from 'lucide-react';
import { Card } from '../../components/common/Card';

export const SecurityPage: React.FC = () => {
  const securityPillars = [
    {
      icon: Key,
      title: 'Secure Authentication & RBAC',
      description: 'Role-based access control strictly enforced on the server. Administrative, proctoring, and student capabilities are completely isolated with session-based authentication.',
    },
    {
      icon: Cpu,
      title: 'Controlled Code Execution',
      description: 'Candidate code submissions run in isolated sandbox environments with restricted resources, memory limits, and non-root execution identities.',
    },
    {
      icon: Clock,
      title: 'Server-Authoritative Timing',
      description: 'Examination start, end, and duration clocks are maintained authoritatively on the server to protect against local device clock manipulation.',
    },
    {
      icon: Lock,
      title: 'Assessment Data Protection',
      description: 'Questions, test suites, and candidate submissions are protected in transit and at rest, with strict authorization checks guarding each attempt.',
    },
    {
      icon: UserCheck,
      title: 'Human-Centered Review',
      description: 'Intelligent monitoring provides objective behavioral indicators to assist authorized proctors. Disciplinary outcomes require human judgment and cause recording.',
    },
    {
      icon: Database,
      title: 'Data Retention & Governance',
      description: 'Scheduled data lifecycle policies ensure assessment telemetry is retained only for required institutional periods, with support for formal legal holds.',
    },
    {
      icon: FileText,
      title: 'Encrypted Privacy Exports',
      description: 'Candidates can request self-service exports of their examination records, sanitized to protect proctor internal notes and proprietary question secrets.',
    },
    {
      icon: Shield,
      title: 'Comprehensive Auditability',
      description: 'Administrative interventions, proctor actions, and candidate timeline events are recorded to maintain a clear record of examination conduct.',
    },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16 space-y-16">
      {/* Header */}
      <div className="space-y-4 text-center max-w-3xl mx-auto">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
          <Shield className="w-3.5 h-3.5 text-emerald-600" />
          <span>Security Architecture</span>
        </div>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight font-sans">
          Security Built on Transparency & Defense-in-Depth
        </h1>
        <p className="text-base text-slate-600 leading-relaxed">
          CODEGUARD provides a secure examination environment through layered technical controls, server-authoritative state, and respectful human supervision.
        </p>
      </div>

      {/* Security Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {securityPillars.map((pillar) => {
          const Icon = pillar.icon;
          return (
            <Card key={pillar.title} className="p-6 space-y-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
                <Icon className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900">{pillar.title}</h3>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">{pillar.description}</p>
            </Card>
          );
        })}
      </div>

      {/* Realistic Security Stance Card */}
      <div className="rounded-2xl bg-white border border-slate-200 p-8 space-y-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700">
            <Lock className="w-4 h-4" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">Our Security Stance</h3>
        </div>
        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
          We believe in honest, grounded security. No assessment platform can legitimately guarantee 100% cheat prevention. CODEGUARD focuses on reducing cheating opportunities through controlled environments, assisting proctors with actionable signals, and ensuring transparent audit trails for institutional accountability.
        </p>
      </div>
    </div>
  );
};

export default SecurityPage;
