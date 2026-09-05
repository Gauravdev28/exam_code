import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Shield, 
  Code2, 
  Eye, 
  Users, 
  ArrowRight, 
  Lock, 
  GraduationCap,
  Building2,
  Award
} from 'lucide-react';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';

export const HomePage: React.FC = () => {
  const capabilities = [
    {
      icon: Shield,
      title: 'Secure Assessments',
      description: 'Conduct structured technical examinations in a controlled assessment environment with question versioning and strict session boundaries.',
    },
    {
      icon: Code2,
      title: 'Reliable Evaluation',
      description: 'Evaluate coding submissions consistently using automated test cases, hidden evaluation suites, and deterministic scoring.',
    },
    {
      icon: Eye,
      title: 'Intelligent Monitoring',
      description: 'Identify unusual examination activity and provide useful signals for review, including tab focus shifts and environmental status.',
    },
    {
      icon: Users,
      title: 'Human Supervision',
      description: 'Allow authorized proctors to monitor candidates in real time and intervene when necessary through formal warnings, room scans, or timed pauses.',
    },
  ];

  const personas = [
    {
      icon: GraduationCap,
      title: 'Higher Education & Universities',
      description: 'Administer midterms, finals, and lab practicals with confidence in grading consistency and student integrity.',
    },
    {
      icon: Award,
      title: 'Certification Bodies',
      description: 'Deliver standardized practical programming exams with verifiable results and institutional governance.',
    },
    {
      icon: Building2,
      title: 'Engineering Organizations',
      description: 'Screen technical talent with realistic coding problems evaluated automatically and reviewed objectively.',
    },
  ];

  return (
    <div className="space-y-20 pb-20">
      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-16 md:pt-20 md:pb-24 bg-gradient-to-b from-white via-slate-50 to-slate-50 border-b border-slate-200/80">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
            <Shield className="w-3.5 h-3.5 text-emerald-600" />
            <span>Modern Technical Assessment Platform</span>
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight font-sans">
            Secure Assessments. <br className="hidden sm:inline" />
            <span className="text-emerald-600">Smarter Evaluation.</span>
          </h1>

          <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
            CODEGUARD helps institutions conduct secure technical assessments with reliable coding evaluation, intelligent monitoring, and human supervision.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Link to="/login">
              <Button variant="primary" size="lg" className="flex items-center gap-2 px-6">
                <span>Sign In to Platform</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
            <Link to="/features">
              <Button variant="secondary" size="lg" className="px-6">
                Explore Features
              </Button>
            </Link>
          </div>

          {/* Value highlights */}
          <div className="pt-10 grid grid-cols-2 md:grid-cols-4 gap-4 text-center max-w-3xl mx-auto">
            <div className="p-3 bg-white rounded-xl border border-slate-200/90 shadow-sm">
              <div className="text-xl font-bold text-slate-900">Deterministic</div>
              <div className="text-xs text-slate-500 mt-0.5">Automated Code Grading</div>
            </div>
            <div className="p-3 bg-white rounded-xl border border-slate-200/90 shadow-sm">
              <div className="text-xl font-bold text-slate-900">Human-Led</div>
              <div className="text-xs text-slate-500 mt-0.5">Proctor Interventions</div>
            </div>
            <div className="p-3 bg-white rounded-xl border border-slate-200/90 shadow-sm">
              <div className="text-xl font-bold text-slate-900">Multi-Role</div>
              <div className="text-xs text-slate-500 mt-0.5">Admin, Proctor & Student</div>
            </div>
            <div className="p-3 bg-white rounded-xl border border-slate-200/90 shadow-sm">
              <div className="text-xl font-bold text-slate-900">Private</div>
              <div className="text-xs text-slate-500 mt-0.5">Controlled Data Retention</div>
            </div>
          </div>
        </div>
      </section>

      {/* Core Capabilities Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="text-center space-y-3 max-w-2xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
            Built for Academic and Professional Rigor
          </h2>
          <p className="text-sm text-slate-600">
            Everything your institution needs to author, administer, and supervise technical examinations.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {capabilities.map((cap) => {
            const Icon = cap.icon;
            return (
              <Card key={cap.title} className="p-6 space-y-4 hover:border-emerald-300 transition-colors">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200/70 text-emerald-700 flex items-center justify-center">
                  <Icon className="w-5 h-5" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-base font-bold text-slate-900">{cap.title}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">{cap.description}</p>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Who Is It For Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="text-center space-y-3 max-w-2xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
            Who Uses CODEGUARD?
          </h2>
          <p className="text-sm text-slate-600">
            Designed to meet the diverse requirements of educators, certifying agencies, and hiring departments.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {personas.map((persona) => {
            const Icon = persona.icon;
            return (
              <Card key={persona.title} className="p-6 space-y-3">
                <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 text-slate-700 flex items-center justify-center">
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="text-base font-bold text-slate-900">{persona.title}</h3>
                <p className="text-xs text-slate-600 leading-relaxed">{persona.description}</p>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Simple CTA Banner */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-2xl bg-white border border-slate-200 p-8 sm:p-12 shadow-sm text-center space-y-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 mb-2">
            <Lock className="w-6 h-6" />
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
            Ready to conduct secure technical exams?
          </h2>
          <p className="text-sm text-slate-600 max-w-xl mx-auto">
            Sign in with your institutional credentials or contact your administrator to get started with CODEGUARD.
          </p>
          <div className="pt-2">
            <Link to="/login">
              <Button variant="primary" size="lg" className="px-8">
                Sign In to Platform
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
