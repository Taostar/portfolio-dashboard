import React from 'react';
import { MetricCard } from '../common/MetricCard';
import { formatCurrency } from '../../utils/formatters';
import type { OptionsSummary as OptionsSummaryData } from '../../types/portfolio';

interface OptionsSummaryProps {
  summary: OptionsSummaryData;
}

export const OptionsSummary: React.FC<OptionsSummaryProps> = ({ summary }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
    <MetricCard
      label="Notional Exposure"
      value={formatCurrency(summary.notional_exposure_cad)}
    />
    <MetricCard
      label="Cash-like Reserves"
      value={formatCurrency(summary.cash_like_reserves_cad)}
      change={`SGOV ${formatCurrency(summary.sgov_value_cad)} · PSA.TO ${formatCurrency(
        summary.psa_to_value_cad
      )}`}
    />
  </div>
);
