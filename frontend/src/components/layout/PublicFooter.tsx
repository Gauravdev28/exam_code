import React from 'react';
import { Link } from 'react-router-dom';
import { Shield } from 'lucide-react';

export const PublicFooter: React.FC = () => {
  return (
    <footer className="border-t border-slate-200 bg-white text-slate-600">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          {/* Brand Info */}
          <div className="space-y-3 md:col-span-2">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-emerald-600 flex items-center justify-center text-white">
                <Shield className="w-4 h-4 stroke-[2.2]" />
              </div>
              <span className="font-extrabold text-lg tracking-tight text-slate-900 font-sans">
                CODE<span className="text-emerald-600">GUARD</span>
              </span>
            </div>
            <p className="text-xs text-slate-500 max-w-sm leading-relaxed">
              CODEGUARD helps institutions conduct secure technical assessments with reliable coding evaluation, intelligent monitoring, and human supervision.
            </p>
          </div>

          {/* Navigation */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-900">Platform</h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link to="/features" className="text-slate-600 hover:text-emerald-600 transition-colors">
                  Features & Capabilities
                </Link>
              </li>
              <li>
                <Link to="/security" className="text-slate-600 hover:text-emerald-600 transition-colors">
                  Security Architecture
                </Link>
              </li>
              <li>
                <Link to="/how-it-works" className="text-slate-600 hover:text-emerald-600 transition-colors">
                  How It Works
                </Link>
              </li>
              <li>
                <Link to="/about" className="text-slate-600 hover:text-emerald-600 transition-colors">
                  About CODEGUARD
                </Link>
              </li>
            </ul>
          </div>

          {/* Access */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-900">Workspace</h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link to="/login" className="text-slate-600 hover:text-emerald-600 transition-colors">
                  Sign In
                </Link>
              </li>
              <li>
                <Link to="/health" className="text-slate-600 hover:text-emerald-600 transition-colors">
                  System Diagnostics
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <div>
            &copy; {new Date().getFullYear()} CODEGUARD Platform. All rights reserved.
          </div>
          <div className="flex items-center gap-6">
            <span>Enterprise Technical Assessment & Invigilation</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default PublicFooter;
