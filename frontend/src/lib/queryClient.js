import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

export const queryKeys = {
  accounts:        ['accounts'],
  uploads:         ['uploads'],
  categories:      ['categories'],
  subCategories:   (categoryId) => ['sub-categories', categoryId ?? 'all'],
  types:           (subCategoryId) => ['types', subCategoryId ?? 'all'],
  parties:         (typeId) => ['parties', typeId ?? 'all'],
  transactions:    (filters) => ['transactions', filters ?? {}],
  statementFormats: ['statement-formats'],
  statementFormat: (identifier) => ['statement-format', identifier],
  statementFormatSchema: ['statement-format-schema'],
};
