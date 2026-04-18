import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAccounts,
  fetchStatementFormats,
  previewFile,
  importFile,
  createAccount,
} from './api';

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: getAccounts,
  });
}

export function useStatementFormats() {
  return useQuery({
    queryKey: ['statementFormats'],
    queryFn: fetchStatementFormats,
  });
}

export function usePreviewFile() {
  return useMutation({
    mutationFn: ({ file, numRows }) => previewFile(file, numRows),
  });
}

export function useImportFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, startRow, accountId }) => importFile(file, startRow, accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountName, accountType, statementFormat }) =>
      createAccount(accountName, accountType, statementFormat),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
    },
  });
}
