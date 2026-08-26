import { useState, useEffect, useCallback } from 'react';
import { ticketService } from '@/services/ticketService';
import type { Ticket } from '@/types/chat.types';

/**
 * useTickets hook
 * Fetches and manages ticket list state for the dashboard.
 * Uses the CQRS query path — no LangGraph involved.
 */
export function useTickets(status?: string) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTickets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await ticketService.getMyTickets(status);
      setTickets(result.tickets);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load tickets');
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  return { tickets, loading, error, refetch: fetchTickets };
}
