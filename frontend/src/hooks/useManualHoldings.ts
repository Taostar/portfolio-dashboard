import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { manualHoldingsApi } from '../api/manualHoldings';

export const useManualHoldings = () => {
  return useQuery({
    queryKey: ['manual-holdings'],
    queryFn: manualHoldingsApi.get,
  });
};

export const useUpdateManualHoldings = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: manualHoldingsApi.update,
    onSuccess: (config) => {
      queryClient.setQueryData(['manual-holdings'], config);
      queryClient.invalidateQueries({ queryKey: ['holdings'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
};
