import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryClient';
import {
  processReceiptImage,
  getReceiptImage,
  confirmReceipt,
  deleteReceipt,
  getCandidateTransactions,
  uploadReceiptsStream,
  getUploads,
  matchParty,
  createCashTransactionFromReceipt,
} from './api';

export function useReceiptImage(receiptId) {
  return useQuery({
    queryKey: ['receipt-image', receiptId],
    queryFn: () => getReceiptImage(receiptId),
    enabled: !!receiptId,
  });
}

export function useUploads() {
  return useQuery({ queryKey: queryKeys.uploads, queryFn: getUploads });
}

export function useProcessReceipt() {
  return useMutation({
    mutationFn: (file) => processReceiptImage(file),
  });
}

export function useConfirmReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => confirmReceipt(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['transactions'] }),
  });
}

export function useDeleteReceipt() {
  return useMutation({ mutationFn: (id) => deleteReceipt(id) });
}

export function useCandidateTransactions(receiptData, enabled = true) {
  const hasInputs = !!(receiptData?.date || receiptData?.amount || receiptData?.vendor);
  return useQuery({
    queryKey: ['candidate-transactions', receiptData?.date, receiptData?.amount, receiptData?.vendor],
    queryFn: () => getCandidateTransactions(receiptData),
    enabled: enabled && hasInputs,
  });
}

export function useBulkUploadReceipts() {
  return useMutation({ mutationFn: (formData) => uploadReceiptsStream(formData) });
}

export function useMatchParty() {
  return useMutation({ mutationFn: (name) => matchParty(name) });
}

export function useCreateCashFromReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => createCashTransactionFromReceipt(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['transactions'] }),
  });
}
