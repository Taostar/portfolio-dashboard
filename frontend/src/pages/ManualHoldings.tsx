import React, { useState } from 'react';
import { useManualHoldings, useUpdateManualHoldings } from '../hooks/useManualHoldings';
import type { ManualHolding } from '../types/portfolio';

const emptyRow: ManualHolding = {
  symbol: '',
  currency: 'USD',
  quantity: 0,
  open_quantity: 0,
  average_entry_price: 0,
};

export const ManualHoldings: React.FC = () => {
  const { data, isLoading, error } = useManualHoldings();

  if (isLoading) {
    return <div className="text-center py-8">Loading manual holdings...</div>;
  }

  if (error || !data) {
    return (
      <div className="text-center py-8 text-red-500">Failed to load manual holdings</div>
    );
  }

  return <ManualHoldingsForm initialHoldings={data.holdings} />;
};

const ManualHoldingsForm: React.FC<{ initialHoldings: ManualHolding[] }> = ({
  initialHoldings,
}) => {
  const updateMutation = useUpdateManualHoldings();
  const [rows, setRows] = useState<ManualHolding[]>(initialHoldings);

  const updateRow = (index: number, field: keyof ManualHolding, value: string) => {
    setRows((prev) =>
      prev.map((row, i) => {
        if (i !== index) return row;
        if (field === 'symbol' || field === 'currency') {
          return { ...row, [field]: value };
        }
        return { ...row, [field]: Number(value) };
      })
    );
  };

  const addRow = () => setRows((prev) => [...prev, { ...emptyRow }]);
  const removeRow = (index: number) =>
    setRows((prev) => prev.filter((_, i) => i !== index));

  const handleSave = () => {
    updateMutation.mutate({ holdings: rows });
  };

  return (
    <section className="mb-8 bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-2">Manual Holdings</h2>
      <p className="text-gray-600 mb-4">
        Stocks/ETFs held in accounts not reachable via the broker API. Saving here refreshes
        the main dashboard.
      </p>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500">
              <th className="px-2 py-2">Symbol</th>
              <th className="px-2 py-2">Currency</th>
              <th className="px-2 py-2">Quantity</th>
              <th className="px-2 py-2">Open Quantity</th>
              <th className="px-2 py-2">Avg Entry Price</th>
              <th className="px-2 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-t border-gray-100">
                <td className="px-2 py-2">
                  <input
                    type="text"
                    value={row.symbol}
                    onChange={(e) => updateRow(index, 'symbol', e.target.value)}
                    className="w-28 px-2 py-1 border border-gray-300 rounded"
                  />
                </td>
                <td className="px-2 py-2">
                  <select
                    value={row.currency}
                    onChange={(e) => updateRow(index, 'currency', e.target.value)}
                    className="px-2 py-1 border border-gray-300 rounded"
                  >
                    <option value="USD">USD</option>
                    <option value="CAD">CAD</option>
                  </select>
                </td>
                <td className="px-2 py-2">
                  <input
                    type="number"
                    value={row.quantity}
                    onChange={(e) => updateRow(index, 'quantity', e.target.value)}
                    className="w-24 px-2 py-1 border border-gray-300 rounded"
                  />
                </td>
                <td className="px-2 py-2">
                  <input
                    type="number"
                    value={row.open_quantity}
                    onChange={(e) => updateRow(index, 'open_quantity', e.target.value)}
                    className="w-24 px-2 py-1 border border-gray-300 rounded"
                  />
                </td>
                <td className="px-2 py-2">
                  <input
                    type="number"
                    step="0.01"
                    value={row.average_entry_price}
                    onChange={(e) => updateRow(index, 'average_entry_price', e.target.value)}
                    className="w-28 px-2 py-1 border border-gray-300 rounded"
                  />
                </td>
                <td className="px-2 py-2">
                  <button
                    onClick={() => removeRow(index)}
                    className="text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={addRow}
          className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          Add row
        </button>
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {updateMutation.isPending ? 'Saving...' : 'Save'}
        </button>
        {updateMutation.isSuccess && (
          <span className="text-green-600 text-sm">Saved</span>
        )}
        {updateMutation.isError && (
          <span className="text-red-500 text-sm">Failed to save</span>
        )}
      </div>
    </section>
  );
};
