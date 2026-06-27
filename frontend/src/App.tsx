import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/common/Layout';
import { Dashboard } from './pages/Dashboard';
import { ManualHoldings } from './pages/ManualHoldings';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  const [page, setPage] = useState<'dashboard' | 'manual-holdings'>('dashboard');

  return (
    <QueryClientProvider client={queryClient}>
      <Layout page={page} onNavigate={setPage}>
        {page === 'dashboard' ? <Dashboard /> : <ManualHoldings />}
      </Layout>
    </QueryClientProvider>
  );
}

export default App;
