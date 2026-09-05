import React from 'react';
import { Shield, Lock, Users, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';

export const AboutPage: React.FC = () => {
  const values = [
    {
      title: 'Fair & Objective Evaluation',
      desc: 'Grading is automated, deterministic, and identical across all candidate submissions. Coding test cases run in consistent environments with predictable criteria.',
      icon: CheckCircle2,
    },
    {
      title: 'Human-Centered Supervision',
      desc: 'Technology assists rather than dictates. Automated signals help human invigilators prioritize attention, leaving all critical disciplinary decisions to authorized proctors.',
      icon: Users,
    },
    {
      title: 'Candidate Privacy & Data Rights',
      desc: 'Institutions retain full control of their data lifecycle. Candidates have clear visibility into how their examination records are handled and retained.',
      icon: Lock,
    },
    {
      title: 'Reliability Under Pressure',
      desc: 'Assessments are built to withstand transient network drops with local state synchronization and server-authoritative timer enforcement.',
      icon: Shield,
    },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16 space-y-16">
      {/* Page Header */}
      <div className="space-y-4 text-center max-w-3xl mx-auto">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
          <Shield className="w-3.5 h-3.5 text-emerald-600" />
          <span>About CODEGUARD</span>
        </div>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight font-sans">
          Purpose-Built for Integrity in Technical Education
        </h1>
        <p className="text-base text-slate-600 leading-relaxed">
          CODEGUARD was conceived to bridge the gap between rigorous coding evaluations and humane, transparent examination supervision.
        </p>
      </div>

      {/* Mission Card */}
      <Card className="p-8 sm:p-10 space-y-6">
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900">Our Mission</h2>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          Modern software engineering education requires authentic practical testing, not just multiple-choice quizzes. However, administering hands-on coding examinations at scale presents serious challenges: grading hundreds of unique implementations, ensuring fairness, preventing unauthorized collaboration, and protecting student privacy.
        </p>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          CODEGUARD solves this by combining automated multi-language code execution with real-time proctoring tools. We empower academic institutions and hiring teams to conduct high-stakes assessments with confidence, objectivity, and mutual respect between candidates and proctors.
        </p>
      </Card>

      {/* Core Principles */}
      <div className="space-y-6">
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 text-center">Core Platform Principles</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {values.map((v) => {
            const Icon = v.icon;
            return (
              <Card key={v.title} className="p-6 space-y-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center">
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="text-base font-bold text-slate-900">{v.title}</h3>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">{v.desc}</p>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Commitment Section */}
      <div className="rounded-2xl bg-white border border-slate-200 p-8 text-center space-y-4 shadow-sm">
        <h3 className="text-xl font-bold text-slate-900">Explore the Platform</h3>
        <p className="text-xs sm:text-sm text-slate-600 max-w-xl mx-auto">
          Learn more about our comprehensive assessment features or sign in to your institutional account.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link to="/features">
            <Button variant="primary" size="md" className="flex items-center gap-1.5">
              <span>View Features</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Link to="/login">
            <Button variant="secondary" size="md">
              Sign In
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default AboutPage;
