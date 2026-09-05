import React from 'react';
import { 
  Shield, 
  Code2, 
  Eye, 
  Users, 
  BarChart3, 
  Lock, 
  CheckCircle2, 
  ArrowRight
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';

export const FeaturesPage: React.FC = () => {
  const featureSections = [
    {
      title: 'Secure Assessments',
      icon: Shield,
      description: 'Structured examination authoring, candidate scheduling, and strict lifecycle controls.',
      items: [
        'Multi-section and multi-type technical assessments',
        'Centralized question bank with immutable versioning',
        'Strict timed examinations with server-side countdown authority',
        'Candidate roster assignment with roll number and EUID support',
      ],
    },
    {
      title: 'Coding Evaluation',
      icon: Code2,
      description: 'Real-world coding problems evaluated consistently using automated execution test suites.',
      items: [
        'Full-featured browser code editor with syntax highlighting',
        'Multi-language support for major enterprise programming stacks',
        'Automated test runner with public sample cases and hidden verification suites',
        'Deterministic execution with memory, process, and CPU runtime ceilings',
      ],
    },
    {
      title: 'Intelligent Monitoring',
      icon: Eye,
      description: 'Behavioral and environmental signals that assist proctors without making automated accusations.',
      items: [
        'Browser tab focus and visibility change tracking',
        'Candidate camera and microphone connectivity verification',
        'Anomaly detection highlighting unusual examination patterns',
        'Proctor triage risk bands to prioritize live invigilator attention',
      ],
    },
    {
      title: 'Human Invigilation',
      icon: Users,
      description: 'Authoritative supervisory tools putting human proctors in complete operational control.',
      items: [
        'Live candidate roster view sorted by monitoring risk priority',
        '360° environmental room scan requests',
        'Non-accusatory candidate warnings requiring acknowledgement',
        'Server-coordinated exam pause and resume with time bank controls',
        'Private bilateral messaging between proctor and candidate',
      ],
    },
    {
      title: 'Results & Reporting',
      icon: BarChart3,
      description: 'Detailed analytics and performance scorecards generated immediately upon finalization.',
      items: [
        'Comprehensive candidate scorecards with per-question breakdowns',
        'Cohort grade distributions and passing rate analytics',
        'Test case execution logs and memory/runtime statistics',
        'Formal evaluation release workflow controlled by administrators',
      ],
    },
    {
      title: 'Privacy & Data Controls',
      icon: Lock,
      description: 'Transparent candidate data protection, retention schedules, and governance.',
      items: [
        'Configurable institutional retention schedules for exam artifacts',
        'Legal hold protection preventing accidental data deletion',
        'Self-service candidate data subject access requests (DSAR)',
        'Encrypted export generation with zero proctor private note leakage',
      ],
    },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16 space-y-16">
      {/* Header */}
      <div className="space-y-4 text-center max-w-3xl mx-auto">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
          <Shield className="w-3.5 h-3.5 text-emerald-600" />
          <span>Product Capabilities</span>
        </div>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight font-sans">
          Engineered for Modern Examination Workflows
        </h1>
        <p className="text-base text-slate-600 leading-relaxed">
          Explore the core capabilities that make CODEGUARD a dependable choice for academic departments and technical certification bodies.
        </p>
      </div>

      {/* Feature Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {featureSections.map((sec) => {
          const Icon = sec.icon;
          return (
            <Card key={sec.title} className="p-6 space-y-5 flex flex-col justify-between">
              <div className="space-y-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
                  <Icon className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-lg font-bold text-slate-900">{sec.title}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">{sec.description}</p>
                </div>
                <ul className="space-y-2 pt-2 border-t border-slate-100">
                  {sec.items.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-slate-700 leading-normal">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Callout */}
      <div className="rounded-2xl bg-white border border-slate-200 p-8 sm:p-10 text-center space-y-4 shadow-sm max-w-4xl mx-auto">
        <h3 className="text-xl font-bold text-slate-900">Experience CODEGUARD in Action</h3>
        <p className="text-xs sm:text-sm text-slate-600 max-w-xl mx-auto">
          Log in to your workspace to schedule assessments, configure evaluation test suites, or supervise active sessions.
        </p>
        <div className="pt-2">
          <Link to="/login">
            <Button variant="primary" size="md" className="flex items-center gap-1.5 mx-auto">
              <span>Sign In to Workspace</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default FeaturesPage;
