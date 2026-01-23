import { create } from 'zustand';

export const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isLoading: false,
  error: null,

  login: (data) => {
    set({ isLoading: true, error: null });
    // API call happens in component
    set({ isLoading: false });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, token: null });
  },

  setUser: (user) => set({ user }),
  setToken: (token) => {
    localStorage.setItem('access_token', token);
    set({ token });
  },
}));

export const useBrokerStore = create((set) => ({
  brokers: [],
  isLoading: false,
  error: null,

  setBrokers: (brokers) => set({ brokers }),
  addBroker: (broker) =>
    set((state) => ({ brokers: [...state.brokers, broker] })),
  removeBroker: (id) =>
    set((state) => ({
      brokers: state.brokers.filter((b) => b.id !== id),
    })),
}));

export const useOrderStore = create((set) => ({
  orders: [],
  isLoading: false,
  error: null,

  setOrders: (orders) => set({ orders }),
  addOrder: (order) =>
    set((state) => ({ orders: [...state.orders, order] })),
  updateOrder: (id, updates) =>
    set((state) => ({
      orders: state.orders.map((o) => (o.id === id ? { ...o, ...updates } : o)),
    })),
}));

export const useStrategyStore = create((set) => ({
  strategies: [],
  isLoading: false,
  error: null,

  setStrategies: (strategies) => set({ strategies }),
  addStrategy: (strategy) =>
    set((state) => ({ strategies: [...state.strategies, strategy] })),
  updateStrategy: (id, updates) =>
    set((state) => ({
      strategies: state.strategies.map((s) =>
        s.id === id ? { ...s, ...updates } : s
      ),
    })),
  removeStrategy: (id) =>
    set((state) => ({
      strategies: state.strategies.filter((s) => s.id !== id),
    })),
}));
