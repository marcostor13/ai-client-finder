import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import AppLayout from './components/AppLayout';
import Spinner from './components/Spinner';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import FreelanceSearch from './pages/FreelanceSearch';
import CompanyIntel from './pages/CompanyIntel';
import VideoEditor from './pages/VideoEditor';
import ICPConfigForm from './pages/ICPConfigForm';
import ApprovalQueue from './pages/ApprovalQueue';
import SentEmails from './pages/SentEmails';
import CareerOpsConfig from './pages/CareerOpsConfig';
import CareerOpsOffers from './pages/CareerOpsOffers';
import CareerOpsPipeline from './pages/CareerOpsPipeline';
import CareerOpsReports from './pages/CareerOpsReports';
import CareerOpsScan from './pages/CareerOpsScan';

const PrivateRoute = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <Spinner fullPage size={48} label="Iniciando sesión…" />;
  if (!user) return <Navigate to="/login" />;
  return <AppLayout>{children}</AppLayout>;
};

function App() {
  return (
    <NotificationProvider>
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/freelance" element={<PrivateRoute><FreelanceSearch /></PrivateRoute>} />
          <Route path="/company-intel" element={<PrivateRoute><CompanyIntel /></PrivateRoute>} />
          <Route path="/video" element={<PrivateRoute><VideoEditor /></PrivateRoute>} />
          <Route path="/outbound/icp-config" element={<PrivateRoute><ICPConfigForm /></PrivateRoute>} />
          <Route path="/outbound/approvals" element={<PrivateRoute><ApprovalQueue /></PrivateRoute>} />
          <Route path="/outbound/sent" element={<PrivateRoute><SentEmails /></PrivateRoute>} />
          <Route path="/career-ops/config" element={<PrivateRoute><CareerOpsConfig /></PrivateRoute>} />
          <Route path="/career-ops/offers" element={<PrivateRoute><CareerOpsOffers /></PrivateRoute>} />
          <Route path="/career-ops/pipeline" element={<PrivateRoute><CareerOpsPipeline /></PrivateRoute>} />
          <Route path="/career-ops/reports" element={<PrivateRoute><CareerOpsReports /></PrivateRoute>} />
          <Route path="/career-ops/scan" element={<PrivateRoute><CareerOpsScan /></PrivateRoute>} />
        </Routes>
      </Router>
    </AuthProvider>
    </NotificationProvider>
  );
}

export default App;
