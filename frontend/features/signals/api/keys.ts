export const signalKeys = {
  all: ['signals'] as const,
  list: (limit: number, offset: number) => [...signalKeys.all, 'list', limit, offset] as const,
};
