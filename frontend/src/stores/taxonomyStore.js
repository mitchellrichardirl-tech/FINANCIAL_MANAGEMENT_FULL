import { create } from 'zustand';

export const useTaxonomyStore = create((set) => ({
  categories: [],
  subCategories: [],
  types: [],
  parties: [],

  setCategories: (categories) => set({ categories }),
  setSubCategories: (subCategories) => set({ subCategories }),
  setTypes: (types) => set({ types }),
  setParties: (parties) => set({ parties }),
}));
