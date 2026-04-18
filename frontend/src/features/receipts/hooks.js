import { useQuery, useMutation } from '@tanstack/react-query';
import {
  getCandidateTransactions,
  confirmReceipt,
  deleteReceipt,
  createCashTransactionFromReceipt,
  matchParty,
} from './api';

export function useCandidateTransactions(params, options = {}) {
  return useQuery({
    queryKey: ['candidateTransactions', params],
    queryFn: () => getCandidateTransactions(params),
    ...options,
  });
}

export function useConfirmReceipt() {
  return useMutation({
    mutationFn: (receiptData) => confirmReceipt(receiptData),
  });
}

export function useDeleteReceipt() {
  return useMutation({
    mutationFn: (receiptId) => deleteReceipt(receiptId),
  });
}

export function useCreateCashFromReceipt() {
  return useMutation({
    mutationFn: (payload) => createCashTransactionFromReceipt(payload),
  });
}

export function useMatchParty(vendor) {
  return useQuery({
    queryKey: ['matchParty', vendor],
    queryFn: () => matchParty(vendor),
    enabled: !!vendor,
  });
}
