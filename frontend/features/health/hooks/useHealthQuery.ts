import { useQuery } from '@tanstack/react-query';
import { getHealth } from '@/src/lib/api-client';

export const healthKeys = {
  all: ['health'] as const,
  status: () => [...healthKeys.all, 'status'] as const,
};

export function useHealthQuery() {
  return useQuery({
    queryKey: healthKeys.status(),
    queryFn: getHealth,
    refetchInterval: 30_000,
  });
}
