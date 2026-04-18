import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryClient';
import {
  getTransactions,
  updateTransaction,
  bulkUpdateTransactions,
  generateCashTransactions,
  createCashTransaction,
  getCategories,
  getSubCategories,
  getTypes,
  getParties,
  createCategory,
  createSubCategory,
  createType,
  createParty,
  remapParty,
  getUploads,
  createAccount,
} from './api';
import { getAccounts } from '@/features/statements/api';

export function useTransactions(filters) {
  return useQuery({
    queryKey: queryKeys.transactions(filters),
    queryFn: () => getTransactions(filters),
  });
}

export function useAccounts() {
  return useQuery({ queryKey: queryKeys.accounts, queryFn: getAccounts });
}

export function useUploads() {
  return useQuery({ queryKey: queryKeys.uploads, queryFn: getUploads });
}

export function useCategories() {
  return useQuery({ queryKey: queryKeys.categories, queryFn: getCategories });
}

export function useSubCategories(categoryId = null) {
  return useQuery({
    queryKey: queryKeys.subCategories(categoryId),
    queryFn: () => getSubCategories(categoryId),
  });
}

export function useTypes(subCategoryId = null) {
  return useQuery({
    queryKey: queryKeys.types(subCategoryId),
    queryFn: () => getTypes(subCategoryId),
  });
}

export function useParties(typeId = null) {
  return useQuery({
    queryKey: queryKeys.parties(typeId),
    queryFn: () => getParties(typeId),
  });
}

function invalidateAll(qc) {
  qc.invalidateQueries({ queryKey: ['transactions'] });
  qc.invalidateQueries({ queryKey: queryKeys.uploads });
}

export function useUpdateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, updates }) => updateTransaction(id, updates),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useBulkUpdateTransactions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ids, updates }) => bulkUpdateTransactions(ids, updates),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useGenerateCashTransactions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids) => generateCashTransactions(ids),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useCreateCashTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => createCashTransaction(data),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, description }) => createCategory(name, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.categories }),
  });
}

export function useCreateSubCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, categoryId, description }) =>
      createSubCategory(name, categoryId, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sub-categories'] }),
  });
}

export function useCreateType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, subCategoryId, description }) =>
      createType(name, subCategoryId, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['types'] }),
  });
}

export function useCreateParty() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, typeId, description }) =>
      createParty(name, typeId, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['parties'] }),
  });
}

export function useRemapParty() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ partyId, newTypeId }) => remapParty(partyId, newTypeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['parties'] });
      invalidateAll(qc);
    },
  });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ accountName, accountType, statementFormat }) =>
      createAccount(accountName, accountType, statementFormat),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.accounts }),
  });
}
