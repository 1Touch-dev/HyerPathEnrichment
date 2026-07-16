import { SignalListItem, SignalListResponse } from '@/src/lib/types';

const mockSignals: SignalListItem[] = [
  {
    id: 'sig_mock001',
    source: 'changedetection',
    watchId: 'watch-careers',
    title: 'Acme Careers',
    url: 'https://acme.example/careers',
    timestamp: '2026-07-16T10:00:00Z',
    createdAt: '2026-07-16T10:00:01Z',
  },
  {
    id: 'sig_mock002',
    source: 'changedetection',
    watchId: 'watch-news',
    title: 'Acme News',
    url: 'https://acme.example/news',
    timestamp: '2026-07-15T08:30:00Z',
    createdAt: '2026-07-15T08:30:05Z',
  },
];

export function listMockSignals(limit: number, offset: number): SignalListResponse {
  const slice = mockSignals.slice(offset, offset + limit);
  return {
    signals: slice,
    total: mockSignals.length,
    limit,
    offset,
  };
}
