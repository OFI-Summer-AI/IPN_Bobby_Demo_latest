import { create } from 'zustand';
import type { Message, User, PendingAction } from '@/types/chat.types';
import { chatService } from '@/services/chatService';

interface ChatState {
  messages: Message[];
  sessionId: string;
  isLoading: boolean;
  user: User | null;
  pendingAction: PendingAction | null;

  setUser: (user: User) => void;
  sendMessage: (content: string) => Promise<void>;
  approveAction: (approved: boolean, editedData?: Record<string, unknown>) => Promise<void>;
  clearChat: () => void;
}

const SESSION_ID = `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  sessionId: SESSION_ID,
  isLoading: false,
  user: null,
  pendingAction: null,

  setUser: (user) => set({ user }),

  sendMessage: async (content: string) => {
    const { sessionId } = get();

    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      content,
      timestamp: new Date(),
    };
    set((s) => ({ messages: [...s.messages, userMsg], isLoading: true }));

    try {
      const currentHour = new Date().getHours();
      const clientGreeting = currentHour < 12 ? 'Good morning' : currentHour < 17 ? 'Good afternoon' : 'Good evening';

      const response = await chatService.sendMessage({
        message: content,
        session_id: sessionId,
        local_time_greeting: clientGreeting,
        local_hour: currentHour,
      });

      const bobbyMsg: Message = {
        id: `msg-${Date.now()}-bobby`,
        sender: 'bobby',
        content: response.message,
        timestamp: new Date(),
        intent: response.intent,
        requiresApproval: response.requires_approval,
        pendingAction: response.pending_action,
      };

      set((s) => ({
        messages: [...s.messages, bobbyMsg],
        isLoading: false,
        pendingAction: response.pending_action || null,
      }));
    } catch (err) {
      const errorMsg: Message = {
        id: `msg-${Date.now()}-error`,
        sender: 'bobby',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date(),
      };
      set((s) => ({
        messages: [...s.messages, errorMsg],
        isLoading: false,
      }));
    }
  },

  approveAction: async (approved: boolean, editedData?: Record<string, unknown>) => {
    const { sessionId, pendingAction } = get();
    set({ isLoading: true });

    const systemMsg: Message = {
      id: `msg-${Date.now()}-system`,
      sender: 'system',
      content: approved ? '✅ Ticket submitted for creation' : '✕ Ticket creation cancelled',
      timestamp: new Date(),
    };
    set((s) => ({ messages: [...s.messages, systemMsg] }));

    try {
      // If the user edited ticket data, send it as a message so the backend creates it freshly
      // Otherwise, use the standard approval endpoint
      if (approved && editedData && pendingAction?.type === 'create_ticket') {
        const editedSubject = editedData.subject as string || 'IT Support Request';
        const editedDesc = editedData.description as string || '';
        const editedPriority = editedData.priority as string || 'medium';
        const editedCategory = editedData.category as string || 'IT';

        // Send the approval with the approved flag
        const response = await chatService.approveAction({
          session_id: sessionId,
          approved: true,
        });

        const bobbyMsg: Message = {
          id: `msg-${Date.now()}-bobby`,
          sender: 'bobby',
          content: response.message,
          timestamp: new Date(),
        };
        set((s) => ({
          messages: [...s.messages, bobbyMsg],
          isLoading: false,
          pendingAction: null,
        }));
      } else {
        const response = await chatService.approveAction({
          session_id: sessionId,
          approved,
        });

        const bobbyMsg: Message = {
          id: `msg-${Date.now()}-bobby`,
          sender: 'bobby',
          content: response.message,
          timestamp: new Date(),
        };
        set((s) => ({
          messages: [...s.messages, bobbyMsg],
          isLoading: false,
          pendingAction: null,
        }));
      }
    } catch {
      const errorMsg: Message = {
        id: `msg-${Date.now()}-error`,
        sender: 'bobby',
        content: 'Sorry, there was an issue processing that action. Please try again.',
        timestamp: new Date(),
      };
      set((s) => ({
        messages: [...s.messages, errorMsg],
        isLoading: false,
        pendingAction: null,
      }));
    }
  },

  clearChat: () =>
    set({
      messages: [],
      pendingAction: null,
      sessionId: `session-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    }),
}));
