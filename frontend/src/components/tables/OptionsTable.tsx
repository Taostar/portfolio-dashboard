import React from 'react';
import { getItmOtmColor } from '../../utils/colorUtils';
import { formatNumber, formatPercent } from '../../utils/formatters';
import type { OptionHoldingItem } from '../../types/portfolio';

interface OptionsTableProps {
  options: OptionHoldingItem[];
}

const COLUMNS = [
  'Symbol',
  'Underlying',
  'Type',
  'Strike',
  'Expiry',
  'DTE',
  'Quantity',
  'Premium',
  'Market Value',
  'Underlying Price',
  'ITM/OTM',
  'Prob. Assigned',
];

export const OptionsTable: React.FC<OptionsTableProps> = ({ options }) => {
  // Backend already sorts by DTE ascending; sort again here so the table's
  // contract doesn't silently depend on API ordering.
  const sorted = [...options].sort((a, b) => a.dte - b.dte);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full bg-white border border-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {COLUMNS.map((header, i) => (
              <th
                key={header}
                className={`px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider ${
                  i === 0 ? 'text-left' : 'text-right'
                }`}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {sorted.map((option) => (
            <tr key={option.symbol} className="hover:bg-gray-50">
              <td className="px-4 py-2 font-medium text-gray-900">{option.symbol}</td>
              <td className="px-4 py-2 text-right text-gray-900">{option.underlying}</td>
              <td className="px-4 py-2 text-right text-gray-900">{option.option_type}</td>
              <td className="px-4 py-2 text-right text-gray-900">{formatNumber(option.strike)}</td>
              <td className="px-4 py-2 text-right text-gray-900">{option.expiry_date}</td>
              <td className="px-4 py-2 text-right font-semibold text-gray-900">{option.dte}</td>
              <td className="px-4 py-2 text-right text-gray-900">
                {formatNumber(option.quantity, 0)}
              </td>
              <td className="px-4 py-2 text-right text-gray-900">
                {formatNumber(option.current_price)}
              </td>
              <td className="px-4 py-2 text-right text-gray-900">
                {formatNumber(option.market_value)}
              </td>
              <td className="px-4 py-2 text-right text-gray-900">
                {option.underlying_price === null ? 'N/A' : formatNumber(option.underlying_price)}
              </td>
              <td
                className="px-4 py-2 text-right font-medium"
                style={{ color: getItmOtmColor(option.itm_otm) }}
              >
                {option.itm_otm ?? 'N/A'}
              </td>
              <td className="px-4 py-2 text-right text-gray-900">
                {formatPercent(option.probability_materialized)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
