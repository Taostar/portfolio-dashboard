import React from 'react';
import { useHoldings } from '../../hooks/usePortfolio';
import { HoldingsTable } from '../tables/HoldingsTable';

export const CurrentHoldings: React.FC = () => {
  const { data, isLoading, error } = useHoldings();

  if (isLoading) {
    return <div className="text-center py-8">Loading holdings...</div>;
  }

  if (error || !data) {
    return (
      <div className="text-center py-8 text-red-500">
        Failed to load holdings data
      </div>
    );
  }

  return (
    <section className="mb-8 bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Current Holdings</h2>
      <h3 className="text-lg font-medium mb-2">Stocks & ETFs</h3>
      <HoldingsTable holdings={data.holdings} />
      {data.options && data.options.length > 0 && (
        <>
          <h3 className="text-lg font-medium mt-6 mb-2">Options</h3>
          <HoldingsTable holdings={data.options} />
        </>
      )}
    </section>
  );
};
