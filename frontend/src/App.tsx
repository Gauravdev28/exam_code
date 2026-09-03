import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/layout/Navbar';
import { LoginPage } from './pages/auth/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { HealthCheckPage } from './pages/HealthCheckPage';
import { AdminStudentsPage } from './pages/admin/AdminStudentsPage';
import { StudentProfilePage } from './pages/student/StudentProfilePage';
import { AdminQuestionsPage } from './pages/admin/AdminQuestionsPage';
import { QuestionEditorPage } from './pages/admin/QuestionEditorPage';
import { AdminAssessmentsPage } from './pages/admin/AdminAssessmentsPage';
import { AssessmentEditorPage } from './pages/admin/AssessmentEditorPage';
import { AdminProctoringDashboardPage } from './pages/admin/AdminProctoringDashboardPage';
import { StudentAssessmentsPage } from './pages/student/StudentAssessmentsPage';
import { StudentTestRoomPage } from './pages/student/StudentTestRoomPage';
import { StudentResultPage } from './pages/student/StudentResultPage';
import { AdminAssessmentResultsPage } from './pages/admin/AdminAssessmentResultsPage';
import { AdminRetentionDashboardPage } from './pages/admin/AdminRetentionDashboardPage';
import { StudentPrivacyPage } from './pages/student/StudentPrivacyPage';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { ForcePasswordChangeModal } from './components/auth/ForcePasswordChangeModal';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-brand-500/30 selection:text-brand-300">
          <Navbar />
          <ForcePasswordChangeModal />
          <main className="flex-1">
            <Routes>
              {/* Public Auth Route */}
              <Route path="/login" element={<LoginPage />} />

              {/* Public Diagnostics Route */}
              <Route path="/health" element={<HealthCheckPage />} />

              {/* Authenticated Dashboard Route */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <DashboardPage />
                  </ProtectedRoute>
                }
              />

              {/* Admin Assessments & Editor */}
              <Route
                path="/admin/assessments"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AdminAssessmentsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/assessments/create"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AssessmentEditorPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/assessments/:id"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AssessmentEditorPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/assessments/:assessmentId/proctoring"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AdminProctoringDashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/assessments/:assessmentId/results"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AdminAssessmentResultsPage />
                  </ProtectedRoute>
                }
              />

              {/* Admin Question Bank & Editor */}
              <Route
                path="/admin/questions"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AdminQuestionsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/questions/create"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <QuestionEditorPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/questions/:id/versions/:version"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <QuestionEditorPage />
                  </ProtectedRoute>
                }
              />

              {/* Admin Student Management */}
              <Route
                path="/admin/students"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AdminStudentsPage />
                  </ProtectedRoute>
                }
              />

              {/* Student Assessments & Test Room */}
              <Route
                path="/student/assessments"
                element={
                  <ProtectedRoute requiredRole="STUDENT">
                    <StudentAssessmentsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/student/room/:attemptId"
                element={
                  <ProtectedRoute requiredRole="STUDENT">
                    <StudentTestRoomPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/student/attempts/:attemptId/result"
                element={
                  <ProtectedRoute requiredRole="STUDENT">
                    <StudentResultPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/student/results/:resultId"
                element={
                  <ProtectedRoute requiredRole="STUDENT">
                    <StudentResultPage />
                  </ProtectedRoute>
                }
              />

              {/* Admin Retention & Privacy Operations */}
              <Route
                path="/admin/retention"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AdminRetentionDashboardPage />
                  </ProtectedRoute>
                }
              />

              {/* Student Self Profile */}
              <Route
                path="/student/profile"
                element={
                  <ProtectedRoute requiredRole="STUDENT">
                    <StudentProfilePage />
                  </ProtectedRoute>
                }
              />

              {/* Student Privacy & DSAR */}
              <Route
                path="/student/privacy"
                element={
                  <ProtectedRoute requiredRole="STUDENT">
                    <StudentPrivacyPage />
                  </ProtectedRoute>
                }
              />

              {/* Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <footer className="border-t border-slate-900 bg-slate-950/90 py-6 text-center text-xs text-slate-500 font-mono">
            CODEGUARD Platform — AI Assessment, Evaluation & Proctoring &copy; 2026
          </footer>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
