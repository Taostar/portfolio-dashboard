import React from 'react';
import { getReturnColor, getPriceVsEmaColor } from '../../utils/colorUtils';
import { formatPercent, formatNumber } from '../../utils/formatters';
import type { HoldingItem } from '../../types/portfolio';

interface HoldingsTableProps {
  holdings: HoldingItem[];
}

export const HoldingsTable: React.FC<HoldingsTableProps> = ({ holdings }) => {
  const renderReturnCell = (value: number | null) => {
    const color = getReturnColor(value);
    return (
      <td className="px-4 py-2 text-right" style={{ color }}>
        {formatPercent(value)}
      </td>
    );
  };

  const renderEmaCell = (price: number, ema: number | null) => (
    <td
      className="px-4 py-2 text-right"
      style={{ color: getPriceVsEmaColor(price, ema) }}
    >
      {ema === null ? 'N/A' : formatNumber(ema)}
    </td>
  );

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full bg-white border border-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Symbol
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Currency
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Quantity
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Current Price
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Market Value
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Portfolio %
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              21M EMA
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              21Q EMA
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              1 Day
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              1 Week
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              1 Month
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              6 Months
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              1 Year
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {holdings.map((holding) => (
            <tr key={holding.symbol} className="hover:bg-gray-50">
              <td className="px-4 py-2 font-medium text-gray-900">
                {holding.symbol}
              </td>
              <td className="px-4 py-2 text-gray-500">{holding.currency}</td>
              <td className="px-4 py-2 text-right text-gray-900">
                {formatNumber(holding.quantity, 0)}
              </td>
              <td className="px-4 py-2 text-right text-gray-900">
                {formatNumber(holding.current_price)}
              </td>
              <td className="px-4 py-2 text-right text-gray-900">
                {formatNumber(holding.market_value)}
              </td>
              <td className="px-4 py-2 text-right text-gray-900">
                {holding.portfolio_pct.toFixed(2)}%
              </td>
              {renderEmaCell(holding.current_price, holding.ema_21m)}
              {renderEmaCell(holding.current_price, holding.ema_21q)}
              {renderReturnCell(holding.change_1d)}
              {renderReturnCell(holding.change_1w)}
              {renderReturnCell(holding.change_1m)}
              {renderReturnCell(holding.change_6m)}
              {renderReturnCell(holding.change_1y)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
