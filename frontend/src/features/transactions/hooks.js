import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
  getUploads,
  createCategory,
  createSubCategory,
  createType,
  createParty,
  remapParty,
} from './api';

export function useTransactions(filters) {
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => getTransactions(filters),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
  });
}

export function useSubCategories() {
  return useQuery({
    queryKey: ['subCategories'],
    queryFn: () => getSubCategories(),
  });
}

export function useTypes() {
  return useQuery({
    queryKey: ['types'],
    queryFn: () => getTypes(),
  });
}

export function useParties() {
  return useQuery({
    queryKey: ['parties'],
    queryFn: () => getParties(),
  });
}

export function useUploads() {
  return useQuery({
    queryKey: ['uploads'],
    queryFn: getUploads,
    select: (response) => response.data,
  });
}

export function useUpdateTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ transactionId, updates }) => updateTransaction(transactionId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}

export function useBulkUpdateTransactions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ transactionIds, updates }) => bulkUpdateTransactions(transactionIds, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}

export function useGenerateCashTransactions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (transactionIds) => generateCashTransactions(transactionIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
  });
}

export function useCreateCashTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => createCashTransaction(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
  });
}

export function useRemapParty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ partyId, newTypeId }) => remapParty(partyId, newTypeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parties'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ category, description }) => createCategory(category, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
    },
  });
}

export function useCreateSubCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ subCategory, categoryId, description }) =>
      createSubCategory(subCategory, categoryId, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subCategories'] });
    },
  });
}

export function useCreateType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ type, subCategoryId, description }) =>
      createType(type, subCategoryId, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['types'] });
    },
  });
}

export function useCreateParty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, typeId, description }) => createParty(name, typeId, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parties'] });
    },
  });
}
