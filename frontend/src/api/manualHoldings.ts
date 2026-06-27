import { apiClient } from './client';
import type { ManualHoldingsConfig } from '../types/portfolio';

export const manualHoldingsApi = {
  get: async (): Promise<ManualHoldingsConfig> => {
    const response = await apiClient.get<ManualHoldingsConfig>('/manual-holdings');
    return response.data;
  },

  update: async (config: ManualHoldingsConfig): Promise<ManualHoldingsConfig> => {
    const response = await apiClient.put<ManualHoldingsConfig>('/manual-holdings', config);
    return response.data;
  },
};
