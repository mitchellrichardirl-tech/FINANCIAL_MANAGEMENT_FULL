import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import UploadStatement from '@/features/statements';
import CategorizeTransactions from '@/features/transactions/CategorizeTransactions';
import ProcessReceipts from '@/features/receipts/ProcessReceipts';
import { StatementFormatsPage, FormatEditorPage } from '@/features/statementFormats';
import CategoryHierarchyPage from './features/hierarchy';
import { ToastProvider } from '@/components/ToastContext';
import './App.css';

function App() {
  return (
    <ToastProvider>
      <Router>
        <div className="app">
          {/* Navigation header */}
          <nav className="nav-menu">
              <Link to="/">Home</Link>
            <Link to="/upload">Upload Statement</Link>
            <Link to="/categorize">Categorize Transactions</Link>
            <Link to="/hierarchy">Manage Category Hierarchy</Link>
            <Link to="/process-receipts">Process Receipts</Link>
            <Link to="/statement-formats">Statement Formats</Link>
          </nav>

          {/* Main content area */}
          <main className="main-content">
            <Routes>
              <Route path="/" element={
                <div className="home-page">
                  <h1>Transaction Manager</h1>
                  <p>Welcome! Use the navigation above to get started.</p>
                </div>
              } />
              <Route path="/upload" element={<UploadStatement />} />
              <Route path="/categorize" element={<CategorizeTransactions />} />
              <Route path="/hierarchy" element={<CategoryHierarchyPage />} />
              <Route path="/process-receipts" element={<ProcessReceipts />} />
              <Route path="/statement-formats" element={<StatementFormatsPage />} />
              <Route path="/statement-formats/new" element={<FormatEditorPage mode="create" />} />
              <Route path="/statement-formats/:identifier" element={<FormatEditorPage mode="edit" />} />
            </Routes>
          </main>
        </div>
      </Router>
    </ToastProvider>
  );
}

export default App;