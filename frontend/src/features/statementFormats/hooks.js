import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchFormats,
  fetchFormat,
  fetchFormatSchema,
  previewFormat,
  createFormat,
  updateFormat,
  deleteFormat,
} from './api';

export function useStatementFormats() {
  return useQuery({
    queryKey: ['statementFormats'],
    queryFn: fetchFormats,
  });
}

export function useStatementFormat(identifier) {
  return useQuery({
    queryKey: ['statementFormat', identifier],
    queryFn: () => fetchFormat(identifier),
    enabled: !!identifier,
  });
}

export function useFormatSchema() {
  return useQuery({
    queryKey: ['formatSchema'],
    queryFn: fetchFormatSchema,
  });
}

export function usePreviewFormat() {
  return useMutation({
    mutationFn: ({ config, rows }) => previewFormat(config, rows),
  });
}

export function useCreateFormat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (config) => createFormat(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['statementFormats'] });
    },
  });
}

export function useUpdateFormat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ formatId, config }) => updateFormat(formatId, config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['statementFormats'] });
    },
  });
}

export function useDeleteFormat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (formatId) => deleteFormat(formatId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['statementFormats'] });
    },
  });
}
