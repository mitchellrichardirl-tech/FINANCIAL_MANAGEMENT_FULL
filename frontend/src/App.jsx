import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import UploadStatement from '@/features/statements';
import CategorizeTransactions from '@/features/transactions/CategorizeTransactions';
import ProcessReceipts from '@/features/receipts/ProcessReceipts';
import { StatementFormatsPage, FormatEditorPage } from '@/features/statementFormats';
import ToastContainer from '@/components/ToastContainer';

function App() {
  return (
    <>
      <Router>
        <div className="h-full flex flex-col overflow-hidden">
          <nav className="shrink-0 px-5 py-4 bg-nav-bg border-b border-border flex gap-5 justify-center">
            <Link to="/" className="text-text-dark no-underline font-medium px-3 py-2 rounded hover:bg-[#e0e0e0] transition-colors">Home</Link>
            <Link to="/upload" className="text-text-dark no-underline font-medium px-3 py-2 rounded hover:bg-[#e0e0e0] transition-colors">Upload Statement</Link>
            <Link to="/categorize" className="text-text-dark no-underline font-medium px-3 py-2 rounded hover:bg-[#e0e0e0] transition-colors">Categorize Transactions</Link>
            <Link to="/process-receipts" className="text-text-dark no-underline font-medium px-3 py-2 rounded hover:bg-[#e0e0e0] transition-colors">Process Receipts</Link>
            <Link to="/statement-formats" className="text-text-dark no-underline font-medium px-3 py-2 rounded hover:bg-[#e0e0e0] transition-colors">Statement Formats</Link>
          </nav>

          <main className="flex-1 min-h-0 overflow-hidden flex justify-center bg-bg">
            <Routes>
              <Route path="/" element={
                <div className="w-full max-w-[1200px] p-5 overflow-auto h-full box-border">
                  <h1>Transaction Manager</h1>
                  <p>Welcome! Use the navigation above to get started.</p>
                </div>
              } />
              <Route path="/upload" element={<UploadStatement />} />
              <Route path="/categorize" element={<CategorizeTransactions />} />
              <Route path="/process-receipts" element={<ProcessReceipts />} />
              <Route path="/statement-formats" element={<StatementFormatsPage />} />
              <Route path="/statement-formats/new" element={<FormatEditorPage mode="create" />} />
              <Route path="/statement-formats/:identifier" element={<FormatEditorPage mode="edit" />} />
            </Routes>
          </main>
        </div>
      </Router>
      <ToastContainer />
    </>
  );
}

export default App;
