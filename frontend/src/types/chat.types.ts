// Shared TypeScript types for Bobby frontend

// ── Auth ──────────────────────────────────────────────
export type UserRole = 'employee' | 'helpdesk' | 'admin';

export interface User {
  user_id: string;
  name: string;
  role: UserRole;
}

// ── Chat / Messages ───────────────────────────────────
export type MessageSender = 'user' | 'bobby' | 'system';

export interface Message {
  id: string;
  sender: MessageSender;
  content: string;
  timestamp: Date;
  intent?: string;
  requiresApproval?: boolean;
  pendingAction?: PendingAction;
  ticketCard?: TicketCardData;
}

export interface PendingAction {
  type: 'create_ticket' | 'account_unlock' | 'password_reset';
  data: Record<string, unknown>;
  message: string;
}

export interface TicketCardData {
  id: string;
  subject: string;
  status: string;
  priority: string;
  category?: string;
}

// ── Chat API ──────────────────────────────────────────
export interface ChatRequest {
  message: string;
  session_id: string;
  local_time_greeting?: string;
  local_hour?: number;
}

export interface ChatResponse {
  session_id: string;
  local_time_greeting?: string;
  local_hour?: number;
  message: string;
  intent?: string;
  escalated?: boolean;
  requires_approval?: boolean;
  pending_action?: PendingAction;
}

export interface ApprovalRequest {
  session_id: string;
  local_time_greeting?: string;
  local_hour?: number;
  approved: boolean;
}

// ── Ticket ────────────────────────────────────────────
export interface Ticket {
  id: string;
  subject: string;
  description: string;
  status: 'Open' | 'Pending' | 'Resolved' | 'Closed';
  priority: number;
  created_at: string;
  updated_at: string;
  tags: string[];
}

export interface TicketsResponse {
  tickets: Ticket[];
  count: number;
}
