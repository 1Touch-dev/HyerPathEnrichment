import { useInfiniteQuery } from '@tanstack/react-query';
import { listSignals } from '@/src/lib/api-client';
import { signalKeys } from '../api/keys';

const PAGE_SIZE = 50;

export function useSignalListQuery() {
  return useInfiniteQuery({
    queryKey: signalKeys.all,
    queryFn: ({ pageParam }) => listSignals({ limit: PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _pages, lastOffset) => {
      const nextOffset = lastOffset + lastPage.signals.length;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
  });
}
