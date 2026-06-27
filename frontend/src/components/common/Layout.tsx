import React from 'react';

interface LayoutProps {
  children: React.ReactNode;
  page: 'dashboard' | 'manual-holdings';
  onNavigate: (page: 'dashboard' | 'manual-holdings') => void;
}

export const Layout: React.FC<LayoutProps> = ({ children, page, onNavigate }) => {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">
            📈 Portfolio Dashboard
          </h1>
          <button
            onClick={() => onNavigate(page === 'dashboard' ? 'manual-holdings' : 'dashboard')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
          >
            {page === 'dashboard' ? 'Manage Manual Holdings' : 'Back to Dashboard'}
          </button>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
};
