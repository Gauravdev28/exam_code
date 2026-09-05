import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, Menu, X, ArrowRight, LogOut, LayoutDashboard } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { getDashboardPath } from '../common/ProtectedRoute';

export const PublicNavbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { label: 'Home', path: '/' },
    { label: 'About', path: '/about' },
    { label: 'Features', path: '/features' },
    { label: 'Security', path: '/security' },
    { label: 'How It Works', path: '/how-it-works' },
  ];

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const dashboardPath = getDashboardPath(user?.role);

  return (
    <nav className="sticky top-0 z-50 backdrop-blur-md bg-white/90 border-b border-slate-200 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center shadow-sm text-white group-hover:bg-emerald-700 transition-colors">
              <Shield className="w-5 h-5 stroke-[2.2]" />
            </div>
            <div className="flex flex-col">
              <span className="font-extrabold text-lg tracking-tight text-slate-900 font-sans leading-none">
                CODE<span className="text-emerald-600">GUARD</span>
              </span>
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mt-0.5">
                Assessment Platform
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <div className="hidden md:flex items-center gap-1 lg:gap-2">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`px-3 py-1.5 rounded-lg text-xs lg:text-sm font-medium transition-colors ${
                  isActive(link.path)
                    ? 'text-emerald-700 bg-emerald-50 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* Desktop Action Buttons */}
          <div className="hidden md:flex items-center gap-3">
            {isAuthenticated && user ? (
              <div className="flex items-center gap-2">
                <div className="text-right mr-1">
                  <div className="text-xs font-medium text-slate-800 truncate max-w-[150px]">{user.email}</div>
                  <Badge variant={user.role === 'ADMIN' ? 'info' : user.role === 'PROCTOR' ? 'warning' : 'success'} size="sm">
                    {user.role}
                  </Badge>
                </div>
                <Link to={dashboardPath}>
                  <Button variant="primary" size="sm" className="flex items-center gap-1.5">
                    <LayoutDashboard className="w-3.5 h-3.5" />
                    Dashboard
                  </Button>
                </Link>
                <Button variant="ghost" size="sm" onClick={logout} title="Sign Out">
                  <LogOut className="w-4 h-4 text-slate-500 hover:text-slate-800" />
                </Button>
              </div>
            ) : (
              <Link to="/login">
                <Button variant="primary" size="sm" className="flex items-center gap-1.5">
                  <span>Sign In</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              </Link>
            )}
          </div>

          {/* Mobile menu toggle */}
          <div className="flex md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-slate-200 bg-white px-4 pt-2 pb-5 space-y-2 shadow-lg">
          {navLinks.map((link) => (
            <Link
              key={link.path}
              to={link.path}
              onClick={() => setMobileMenuOpen(false)}
              className={`block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive(link.path)
                  ? 'text-emerald-700 bg-emerald-50 font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              {link.label}
            </Link>
          ))}
          <div className="pt-3 border-t border-slate-100 flex flex-col gap-2">
            {isAuthenticated && user ? (
              <>
                <div className="flex items-center justify-between px-3 py-1">
                  <span className="text-xs text-slate-600">{user.email}</span>
                  <Badge variant={user.role === 'ADMIN' ? 'info' : user.role === 'PROCTOR' ? 'warning' : 'success'} size="sm">
                    {user.role}
                  </Badge>
                </div>
                <Link to={dashboardPath} onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="primary" size="md" className="w-full flex items-center justify-center gap-1.5">
                    <LayoutDashboard className="w-4 h-4" />
                    Go to Dashboard
                  </Button>
                </Link>
                <Button variant="outline" size="sm" onClick={() => { logout(); setMobileMenuOpen(false); }} className="w-full">
                  Sign Out
                </Button>
              </>
            ) : (
              <Link to="/login" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="primary" size="md" className="w-full flex items-center justify-center gap-1.5">
                  <span>Sign In to CODEGUARD</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default PublicNavbar;
