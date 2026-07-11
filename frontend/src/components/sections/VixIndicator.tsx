import React from 'react';
import Plot from 'react-plotly.js';
import { useVix } from '../../hooks/usePortfolio';
import { MetricCard } from '../common/MetricCard';

export const VixIndicator: React.FC = () => {
  const { data, isLoading, error } = useVix();

  return (
    <section className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Market Mood (VIX)</h2>

      {isLoading && <div className="text-center py-8">Loading VIX data...</div>}

      {error && (
        <div className="text-center py-8 text-red-500">
          VIX data unavailable — check the backend connection.
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-6 gap-4">
          <div className="lg:col-span-1">
            <MetricCard
              label="VIX"
              value={data.current.toFixed(2)}
              change={data.zone}
              changeColor={
                data.current < 20
                  ? '#006400'
                  : data.current < 30
                    ? '#b45309'
                    : '#8B0000'
              }
            />
          </div>
          <div className="lg:col-span-5">
            <Plot
              data={[
                {
                  type: 'scatter',
                  mode: 'lines',
                  name: 'VIX',
                  x: data.dates,
                  y: data.close_prices,
                  line: { color: '#1f77b4', width: 1.5 },
                },
              ]}
              layout={{
                autosize: true,
                title: {
                  text: 'CBOE Volatility Index (VIX) — Past Year',
                  font: { size: 16 },
                },
                xaxis: { type: 'date' },
                yaxis: { title: { text: 'VIX' } },
                showlegend: false,
                margin: { t: 50, b: 40, l: 50, r: 110 },
                shapes: [
                  // Zone shading: calm / elevated / high+extreme fear
                  { type: 'rect', xref: 'paper', x0: 0, x1: 1, y0: 0, y1: 20, fillcolor: 'green', opacity: 0.05, line: { width: 0 } },
                  { type: 'rect', xref: 'paper', x0: 0, x1: 1, y0: 20, y1: 30, fillcolor: 'yellow', opacity: 0.08, line: { width: 0 } },
                  { type: 'rect', xref: 'paper', x0: 0, x1: 1, y0: 30, y1: 100, fillcolor: 'red', opacity: 0.05, line: { width: 0 } },
                  // Reference lines
                  { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 20, y1: 20, line: { color: 'orange', width: 1, dash: 'dot' } },
                  { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 30, y1: 30, line: { color: 'darkorange', width: 1, dash: 'dash' } },
                  { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 40, y1: 40, line: { color: 'red', width: 1 } },
                ],
                annotations: [
                  { xref: 'paper', x: 1, y: 20, xanchor: 'left', text: 'Elevated (20)', showarrow: false, font: { size: 11, color: 'orange' } },
                  { xref: 'paper', x: 1, y: 30, xanchor: 'left', text: 'High Fear (30)', showarrow: false, font: { size: 11, color: 'darkorange' } },
                  { xref: 'paper', x: 1, y: 40, xanchor: 'left', text: 'Extreme (40)', showarrow: false, font: { size: 11, color: 'red' } },
                ],
              }}
              useResizeHandler
              style={{ width: '100%', height: '300px' }}
              config={{ responsive: true }}
            />
          </div>
        </div>
      )}
    </section>
  );
};
