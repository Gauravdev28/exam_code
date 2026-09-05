import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { 
  Shield, 
  LogOut, 
  LogIn, 
  LayoutDashboard, 
  Users, 
  BookOpen, 
  Database, 
  Eye, 
  FileCode,
  ShieldCheck,
  BarChart3,
  ChevronDown
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../common/Button';
import { getDashboardPath } from '../common/ProtectedRoute';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const dashboardPath = getDashboardPath(user?.role);

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link to={isAuthenticated ? dashboardPath : '/'} className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white shadow-sm group-hover:bg-emerald-700 transition-colors">
              <Shield className="w-5 h-5 stroke-[2.2]" />
            </div>
            <div>
              <span className="font-extrabold text-base tracking-tight font-sans text-slate-900 leading-none">
                CODE<span className="text-emerald-600">GUARD</span>
              </span>
              <p className="text-[10px] text-slate-500 font-normal leading-none mt-1">
                Assessment & Invigilation
              </p>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 sm:gap-2">
            {/* Public Links */}
            {!isAuthenticated && (
              <>
                <Link
                  to="/"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/' ? 'text-emerald-700 bg-emerald-50 font-semibold' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Home
                </Link>
                <Link
                  to="/about"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/about' ? 'text-emerald-700 bg-emerald-50 font-semibold' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  About
                </Link>
                <Link
                  to="/features"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/features' ? 'text-emerald-700 bg-emerald-50 font-semibold' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Features
                </Link>
                <Link
                  to="/security"
                  className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/security' ? 'text-emerald-700 bg-emerald-50 font-semibold' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Security
                </Link>
              </>
            )}

            {/* Clean Admin Navigation */}
            {isAuthenticated && user?.role === 'ADMIN' && (
              <>
                <Link
                  to="/admin"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/admin' || location.pathname === '/admin/dashboard'
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <LayoutDashboard className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="hidden md:inline">Dashboard</span>
                </Link>

                <Link
                  to="/admin/assessments"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/assessments')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <FileCode className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="hidden md:inline">Assessments</span>
                </Link>

                <Link
                  to="/admin/questions"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/questions')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5 text-amber-600" />
                  <span className="hidden md:inline">Questions</span>
                </Link>

                <Link
                  to="/admin/students"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/students')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <Users className="w-3.5 h-3.5 text-blue-600" />
                  <span className="hidden md:inline">Students</span>
                </Link>

                <Link
                  to="/admin/administrators"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/administrators')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
                  <span className="hidden md:inline">Administrators</span>
                </Link>

                <Link
                  to="/admin/results"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/results')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <BarChart3 className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="hidden md:inline">Results</span>
                </Link>

                <Link
                  to="/admin/retention"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/admin/retention')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <Database className="w-3.5 h-3.5 text-slate-500" />
                  <span className="hidden lg:inline">Retention</span>
                </Link>
              </>
            )}

            {/* Proctor Links */}
            {isAuthenticated && user?.role === 'PROCTOR' && (
              <Link
                to="/proctor"
                className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                  location.pathname === '/proctor' || location.pathname === '/proctor/dashboard'
                    ? 'text-emerald-700 bg-emerald-50 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Eye className="w-4 h-4 text-amber-600" />
                <span className="hidden md:inline">Live Assessments</span>
              </Link>
            )}

            {/* Student Links */}
            {isAuthenticated && user?.role === 'STUDENT' && (
              <>
                <Link
                  to="/student"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname === '/student' || location.pathname === '/student/dashboard'
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <LayoutDashboard className="w-4 h-4 text-emerald-600" />
                  <span className="hidden md:inline">Dashboard</span>
                </Link>
                <Link
                  to="/student/assessments"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/student/assessments')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <FileCode className="w-4 h-4 text-emerald-600" />
                  <span className="hidden md:inline">My Exams</span>
                </Link>
                <Link
                  to="/student/privacy"
                  className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${
                    location.pathname.startsWith('/student/privacy')
                      ? 'text-emerald-700 bg-emerald-50 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <Shield className="w-4 h-4 text-sky-600" />
                  <span className="hidden md:inline">Privacy</span>
                </Link>
              </>
            )}

            {/* Auth / Account Controls */}
            {isAuthenticated && user ? (
              <div className="relative ml-2 pl-2 border-l border-slate-200">
                <button
                  onClick={() => setAccountMenuOpen(!accountMenuOpen)}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 transition-colors text-left"
                >
                  <div className="flex flex-col text-right">
                    <span className="text-xs font-bold text-slate-900 leading-tight">
                      {user.display_name || user.first_name || (user.role === 'ADMIN' ? 'Admin' : user.email.split('@')[0])}
                    </span>
                    <span className="text-[10px] font-medium text-slate-500 leading-none mt-0.5">
                      {user.role === 'ADMIN' ? 'Admin' : user.role}
                    </span>
                  </div>
                  {user.admin_id && (
                    <span className="hidden sm:inline-block text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                      {user.admin_id}
                    </span>
                  )}
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                </button>

                {/* Account Dropdown Menu */}
                {accountMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-slate-200 py-1.5 z-50 divide-y divide-slate-100">
                    <div className="px-3.5 py-2.5">
                      <div className="text-xs font-bold text-slate-900">
                        {user.display_name || user.first_name || 'Admin'}
                      </div>
                      <div className="text-[11px] text-slate-500 font-medium mt-0.5">
                        {user.role === 'ADMIN' ? 'Admin' : user.role}
                      </div>
                      {user.admin_id && (
                        <div className="text-[11px] text-emerald-700 font-mono font-semibold mt-1">
                          Admin ID: {user.admin_id}
                        </div>
                      )}
                    </div>

                    {user.role === 'ADMIN' && (
                      <div className="py-1">
                        <Link
                          to="/admin/administrators"
                          onClick={() => setAccountMenuOpen(false)}
                          className="flex items-center gap-2 px-3.5 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-emerald-700 font-medium"
                        >
                          <ShieldCheck className="w-4 h-4 text-purple-600" />
                          <span>Administrators</span>
                        </Link>
                      </div>
                    )}

                    <div className="py-1">
                      <button
                        onClick={() => {
                          setAccountMenuOpen(false);
                          handleLogout();
                        }}
                        className="w-full flex items-center gap-2 px-3.5 py-2 text-xs text-rose-600 hover:bg-rose-50 font-medium"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Link to="/login">
                <Button variant="primary" size="sm" className="flex items-center gap-1.5">
                  <LogIn className="w-3.5 h-3.5" />
                  <span>Sign In</span>
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
