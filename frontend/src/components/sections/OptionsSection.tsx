import React from 'react';
import { useOptions } from '../../hooks/usePortfolio';
import { OptionsTable } from '../tables/OptionsTable';
import { OptionsSummary } from './OptionsSummary';

export const OptionsSection: React.FC = () => {
  const { data, isLoading, error } = useOptions();

  return (
    <section className="mb-8 bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Options</h2>

      {isLoading && <div className="text-center py-8">Loading options...</div>}

      {error && (
        <div className="text-center py-8 text-red-500">
          Failed to load options data
        </div>
      )}

      {data && data.options.length === 0 && (
        <div className="text-center py-8 text-gray-500">No open option positions.</div>
      )}

      {data && data.options.length > 0 && (
        <>
          <OptionsSummary summary={data.summary} />
          <OptionsTable options={data.options} />
        </>
      )}
    </section>
  );
};
