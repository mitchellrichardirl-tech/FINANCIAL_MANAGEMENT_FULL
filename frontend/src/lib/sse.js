/**
 * @file sse.js
 */

import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('sse');

/** Parse one SSE block. Returns null for comments and heartbeats. */
const parseSSEBlock = (block) => {
  const dataLines = block
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''));
  if (dataLines.length === 0) return null;
  return JSON.parse(dataLines.join('\n'));
};
/**
 * Read an SSE response body and call onEvent for each parsed event.
 *
 * Resolves when the server closes the stream. Rejects on network errors,
 * on abort, or if no bytes arrive for `idleTimeoutMs`. Heartbeat comments
 * count as bytes, so the timeout only fires on a real stall.
 *
 * @param {Response} response
 * @param {(event: Object) => void} onEvent
 * @param {{ idleTimeoutMs?: number }} [options]  0 disables the timeout.
 */
export const readEventStream = async (response, onEvent, { idleTimeoutMs = 0 } = {}) => {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let idleTimer = null;
  let timedOut = false;

  const resetIdleTimer = () => {
    if (!idleTimeoutMs) return;
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      timedOut = true;
      reader.cancel().catch(() => {}); // ends the pending read() with done: true
    }, idleTimeoutMs);
  };

  const dispatch = (block) => {
    let event;
    try {
      event = parseSSEBlock(block);
    } catch (parseError) {
      logger.error('Failed to parse SSE event:', parseError, block);
      return;
    }
    if (!event) return;
    try {
      onEvent(event);
    } catch (handlerError) {
      logger.error('Error handling SSE event:', handlerError, event);
    }
  };

  try {
    resetIdleTimer();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      resetIdleTimer();
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';
      blocks.forEach(dispatch);
    }
    if (timedOut) {
      throw new Error(`Stream idle: no data for ${idleTimeoutMs / 1000}s`);
    }
    buffer += decoder.decode();
    if (buffer.trim()) dispatch(buffer);
  } finally {
    clearTimeout(idleTimer);
    reader.releaseLock();
  }
};