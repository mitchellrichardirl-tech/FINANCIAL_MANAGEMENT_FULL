import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import UploadStatement from '@/features/statements';
import CategorizeTransactions from './features/transactions/CategorizeTransactions';
import ProcessReceipts from './features/receipts/ProcessReceipts';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        {/* Navigation header */}
        <nav className="nav-menu">
          <Link to="/">Home</Link>
          <Link to="/upload">Upload Statement</Link>
          <Link to="/categorize">Categorize Transactions</Link>
          <Link to="/process-receipts">Process Receipts</Link>
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
            <Route path="/process-receipts" element={<ProcessReceipts />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;