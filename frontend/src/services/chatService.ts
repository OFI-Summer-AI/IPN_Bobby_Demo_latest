import { apiClient } from './api';
import type { ChatRequest, ChatResponse, ApprovalRequest } from '@/types/chat.types';

export const chatService = {
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post<ChatResponse>('/commands/chat', request);
    return data;
  },

  approveAction: async (request: ApprovalRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post<ChatResponse>('/commands/chat/approve', request);
    return data;
  },
};
