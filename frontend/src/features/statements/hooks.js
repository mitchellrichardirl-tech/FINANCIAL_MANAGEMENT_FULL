import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryClient';
import {
  getAccounts,
  createAccount,
  previewFile,
  importFile,
  getUploads,
  fetchStatementFormats,
} from './api';

export function useAccounts() {
  return useQuery({ queryKey: queryKeys.accounts, queryFn: getAccounts });
}

export function useStatementFormats() {
  return useQuery({
    queryKey: queryKeys.statementFormats,
    queryFn: fetchStatementFormats,
  });
}

export function useUploads() {
  return useQuery({ queryKey: queryKeys.uploads, queryFn: getUploads });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ accountName, accountType, statementFormat }) =>
      createAccount(accountName, accountType, statementFormat),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.accounts }),
  });
}

export function usePreviewFile() {
  return useMutation({
    mutationFn: ({ file, numRows = 20 }) => previewFile(file, numRows),
  });
}

export function useImportFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, startRow, accountId }) =>
      importFile(file, startRow, accountId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.uploads });
      qc.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}
