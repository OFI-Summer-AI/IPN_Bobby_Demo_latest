import { useState, useCallback } from 'react';
import { useChatStore } from '@/store/chatStore';

/**
 * useChat hook
 * Wraps the Zustand store for components that want a clean hook interface.
 * Components should prefer this over accessing the store directly.
 */
export function useChat() {
  const { messages, isLoading, pendingAction, sendMessage, approveAction, clearChat } =
    useChatStore();

  const [inputValue, setInputValue] = useState('');

  const handleSend = useCallback(
    async (text?: string) => {
      const msg = (text ?? inputValue).trim();
      if (!msg) return;
      setInputValue('');
      await sendMessage(msg);
    },
    [inputValue, sendMessage]
  );

  return {
    messages,
    isLoading,
    pendingAction,
    inputValue,
    setInputValue,
    handleSend,
    approveAction,
    clearChat,
  };
}
