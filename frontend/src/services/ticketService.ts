import { apiClient } from './api';
import type { Ticket, TicketsResponse } from '@/types/chat.types';

export const ticketService = {
  getMyTickets: async (status?: string): Promise<TicketsResponse> => {
    const params = status ? { status } : {};
    const { data } = await apiClient.get<TicketsResponse>('/queries/tickets', { params });
    return data;
  },

  getTicketDetail: async (ticketId: string): Promise<Ticket> => {
    const { data } = await apiClient.get<Ticket>(`/queries/tickets/${ticketId}`);
    return data;
  },

  searchTickets: async (query: string): Promise<TicketsResponse> => {
    const { data } = await apiClient.get<TicketsResponse>('/queries/tickets/search', {
      params: { q: query },
    });
    return data;
  },
};
