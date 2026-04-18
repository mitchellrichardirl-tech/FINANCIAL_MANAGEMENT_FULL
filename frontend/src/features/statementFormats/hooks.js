import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryClient';
import {
  fetchFormats,
  fetchFormat,
  fetchFormatSchema,
  previewFormat,
  createFormat,
  updateFormat,
  deleteFormat,
} from './api';

export function useFormats() {
  return useQuery({
    queryKey: queryKeys.statementFormats,
    queryFn: fetchFormats,
  });
}

export function useFormat(identifier) {
  return useQuery({
    queryKey: queryKeys.statementFormat(identifier),
    queryFn: () => fetchFormat(identifier),
    enabled: !!identifier,
  });
}

export function useFormatSchema() {
  return useQuery({
    queryKey: queryKeys.statementFormatSchema,
    queryFn: fetchFormatSchema,
  });
}

export function usePreviewFormat() {
  return useMutation({
    mutationFn: ({ config, rows }) => previewFormat(config, rows),
  });
}

export function useCreateFormat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config) => createFormat(config),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.statementFormats }),
  });
}

export function useUpdateFormat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ formatId, config }) => updateFormat(formatId, config),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.statementFormats });
      qc.invalidateQueries({ queryKey: ['statement-format'] });
    },
  });
}

export function useDeleteFormat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (formatId) => deleteFormat(formatId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.statementFormats }),
  });
}
