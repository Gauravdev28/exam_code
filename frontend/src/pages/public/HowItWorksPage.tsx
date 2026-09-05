import React from 'react';
import { Shield, ArrowRight, UserCheck, GraduationCap, Eye } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';

export const HowItWorksPage: React.FC = () => {
  const candidateSteps = [
    {
      num: '1',
      title: 'Sign In',
      desc: 'Log in with your institutional email address or Exam Unique ID (EUID). Temporary credentials require immediate password update.',
    },
    {
      num: '2',
      title: 'Environment Verification',
      desc: 'Confirm your camera, microphone, and browser compatibility prior to entering the secure assessment room.',
    },
    {
      num: '3',
      title: 'Enter Assessment',
      desc: 'Access your assigned test room once the examination window opens and review the provided instructions.',
    },
    {
      num: '4',
      title: 'Solve & Test Code',
      desc: 'Write code in the browser editor, run sample test cases, and verify your logic against sample criteria.',
    },
    {
      num: '5',
      title: 'Submit Assessment',
      desc: 'Finalize your submission when complete or let the server automatically submit your work when time expires.',
    },
    {
      num: '6',
      title: 'Receive Results',
      desc: 'View your scorecard, evaluation breakdown, and score summary as soon as results are released by the institution.',
    },
  ];

  const institutionSteps = [
    {
      num: '1',
      title: 'Create Assessment',
      desc: 'Define examination parameters, duration, attempt ceilings, and scoring policies.',
    },
    {
      num: '2',
      title: 'Add Questions',
      desc: 'Select coding problems and questions from your version-controlled question bank.',
    },
    {
      num: '3',
      title: 'Assign Candidates',
      desc: 'Enroll candidates via single-entry registration or batch CSV import with automatic credentialing.',
    },
    {
      num: '4',
      title: 'Assign Proctors',
      desc: 'Designate authorized faculty or invigilators with scope-restricted proctoring access.',
    },
    {
      num: '5',
      title: 'Conduct Examination',
      desc: 'Supervise real-time participation while candidate code is executed in isolated containers.',
    },
    {
      num: '6',
      title: 'Review Results',
      desc: 'Analyze cohort score distributions, pass rates, and release scorecards to students.',
    },
  ];

  const proctorSteps = [
    {
      num: '1',
      title: 'Sign In',
      desc: 'Access your invigilation workspace using your institutional proctor credentials.',
    },
    {
      num: '2',
      title: 'Open Assigned Exam',
      desc: 'Select an active scheduled examination from your authorized assessment roster.',
    },
    {
      num: '3',
      title: 'Monitor Candidates',
      desc: 'Review the live candidate queue organized by behavioral and environmental risk bands.',
    },
    {
      num: '4',
      title: 'Review Alerts',
      desc: 'Inspect signals such as focus loss, disconnected hardware, or unusual activity.',
    },
    {
      num: '5',
      title: 'Intervene When Necessary',
      desc: 'Send formal warnings, request environmental room scans, or temporarily pause attempts.',
    },
    {
      num: '6',
      title: 'Record Examination Events',
      desc: 'Every intervention is automatically logged to the immutable examination timeline for institutional review.',
    },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16 space-y-20">
      {/* Header */}
      <div className="space-y-4 text-center max-w-3xl mx-auto">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
          <Shield className="w-3.5 h-3.5 text-emerald-600" />
          <span>Platform Workflows</span>
        </div>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight font-sans">
          How Assessments Work on CODEGUARD
        </h1>
        <p className="text-base text-slate-600 leading-relaxed">
          A clear, transparent examination process designed for candidates, instructors, and invigilators.
        </p>
      </div>

      {/* Candidate Workflow */}
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
            <GraduationCap className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">Candidate Examination Journey</h2>
            <p className="text-xs text-slate-500">From identity sign-in to final score release</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {candidateSteps.map((step) => (
            <Card key={step.num} className="p-5 space-y-2 relative">
              <div className="w-7 h-7 rounded-lg bg-emerald-100/70 text-emerald-800 text-xs font-bold flex items-center justify-center">
                {step.num}
              </div>
              <h3 className="text-sm font-bold text-slate-900">{step.title}</h3>
              <p className="text-xs text-slate-600 leading-relaxed">{step.desc}</p>
            </Card>
          ))}
        </div>
      </div>

      {/* Institution Workflow */}
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 flex items-center justify-center">
            <UserCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">Institutional Administration</h2>
            <p className="text-xs text-slate-500">Assessment lifecycle from creation to evaluation release</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {institutionSteps.map((step) => (
            <Card key={step.num} className="p-5 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-blue-100/70 text-blue-800 text-xs font-bold flex items-center justify-center">
                {step.num}
              </div>
              <h3 className="text-sm font-bold text-slate-900">{step.title}</h3>
              <p className="text-xs text-slate-600 leading-relaxed">{step.desc}</p>
            </Card>
          ))}
        </div>
      </div>

      {/* Proctor Workflow */}
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center">
            <Eye className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900">Invigilator Supervision</h2>
            <p className="text-xs text-slate-500">Live supervision, candidate triage, and structured interventions</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {proctorSteps.map((step) => (
            <Card key={step.num} className="p-5 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-amber-100/70 text-amber-800 text-xs font-bold flex items-center justify-center">
                {step.num}
              </div>
              <h3 className="text-sm font-bold text-slate-900">{step.title}</h3>
              <p className="text-xs text-slate-600 leading-relaxed">{step.desc}</p>
            </Card>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="rounded-2xl bg-white border border-slate-200 p-8 text-center space-y-4 shadow-sm">
        <h3 className="text-xl font-bold text-slate-900">Get Started with CODEGUARD</h3>
        <p className="text-xs sm:text-sm text-slate-600 max-w-md mx-auto">
          Sign in to your account with your institutional email or candidate EUID.
        </p>
        <div className="pt-2">
          <Link to="/login">
            <Button variant="primary" size="md" className="flex items-center gap-1.5 mx-auto">
              <span>Go to Sign In</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default HowItWorksPage;
