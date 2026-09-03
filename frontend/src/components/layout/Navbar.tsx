import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Shield, Activity, LogOut, LogIn, LayoutDashboard, Users, User } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-emerald-400 flex items-center justify-center shadow-lg shadow-brand-500/25">
              <Shield className="w-6 h-6 text-slate-950 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight font-sans text-white">
                  CODE<span className="text-brand-400">GUARD</span>
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-400 font-mono font-medium border border-brand-500/20">
                  PHASE 9
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-normal leading-none mt-0.5">
                AI Assessment & Proctoring Platform
              </p>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center gap-3 sm:gap-6">
            <Link
              to="/"
              className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
            >
              <LayoutDashboard className="w-4 h-4 text-brand-400" />
              <span>Dashboard</span>
            </Link>

            {isAuthenticated && user?.role === 'ADMIN' && (
              <>
                <Link
                  to="/admin/assessments"
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
                >
                  <Shield className="w-4 h-4 text-brand-400" />
                  <span>Assessments</span>
                </Link>
                <Link
                  to="/admin/questions"
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
                >
                  <Shield className="w-4 h-4 text-amber-400" />
                  <span>Questions</span>
                </Link>
                <Link
                  to="/admin/students"
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
                >
                  <Users className="w-4 h-4 text-purple-400" />
                  <span>Students</span>
                </Link>
                <Link
                  to="/admin/retention"
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
                >
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span>Retention</span>
                </Link>
              </>
            )}

            {isAuthenticated && user?.role === 'STUDENT' && (
              <>
                <Link
                  to="/student/assessments"
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
                >
                  <Shield className="w-4 h-4 text-brand-400" />
                  <span>Exams</span>
                </Link>
                <Link
                  to="/student/privacy"
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
                >
                  <Shield className="w-4 h-4 text-sky-400" />
                  <span>Privacy & DSAR</span>
                </Link>
                <Link
                  to="/student/profile"
                  className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
                >
                  <User className="w-4 h-4 text-emerald-400" />
                  <span>My Profile</span>
                </Link>
              </>
            )}

            <Link
              to="/health"
              className="flex items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-brand-400 transition-colors"
            >
              <Activity className="w-4 h-4 text-blue-400" />
              <span>Health</span>
            </Link>

            {/* Auth Actions */}
            {isAuthenticated && user ? (
              <div className="flex items-center gap-2 sm:gap-3 pl-2 sm:pl-3 border-l border-slate-800">
                <div className="hidden md:flex flex-col text-right">
                  <span className="text-xs font-medium text-slate-200">{user.email}</span>
                  <span className="text-[10px] font-mono text-brand-400">{user.role}</span>
                </div>
                <Badge variant={user.role === 'ADMIN' ? 'info' : 'success'} size="sm">
                  {user.role}
                </Badge>
                <Button variant="ghost" size="sm" onClick={handleLogout} className="p-1.5 text-slate-400 hover:text-red-400">
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <Link to="/login">
                <Button variant="primary" size="sm">
                  <LogIn className="w-3.5 h-3.5" />
                  Sign In
                </Button>
              </Link>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
