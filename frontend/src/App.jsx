import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import UploadStatement from '@/features/statements';
import CategorizeTransactions from '@/features/transactions/CategorizeTransactions';
import ProcessReceipts from '@/features/receipts/ProcessReceipts';
import { StatementFormatsPage, FormatEditorPage } from '@/features/statementFormats';

function App() {
  return (
    <Router>
      <div className="h-full flex flex-col overflow-hidden">
        <nav className="shrink-0 py-4 px-5 bg-[#f0f0f0] border-b border-[#ddd] flex gap-5 justify-center">
          {[
            ['/', 'Home'],
            ['/upload', 'Upload Statement'],
            ['/categorize', 'Categorize Transactions'],
            ['/process-receipts', 'Process Receipts'],
            ['/statement-formats', 'Statement Formats'],
          ].map(([to, label]) => (
            <Link
              key={to}
              to={to}
              className="text-[#333] no-underline font-medium py-2 px-3 rounded transition-colors duration-200 hover:bg-[#e0e0e0]"
            >
              {label}
            </Link>
          ))}
        </nav>
        <main className="flex-1 min-h-0 overflow-hidden flex justify-center bg-[#f5f6fa]">
          <Routes>
            <Route path="/" element={
              <div className="w-full max-w-[1200px] p-5 overflow-auto h-full box-border">
                <h1 className="text-[3.2em] leading-[1.1] font-bold">Transaction Manager</h1>
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
  );
}

export default App;
