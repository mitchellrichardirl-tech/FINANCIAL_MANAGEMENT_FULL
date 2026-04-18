// Shared Tailwind modal shell + button helpers used by the bulk-edit /
// remap / generate / create-cash modals so they look identical without
// duplicating utility-class strings.

export const overlayCls =
  'fixed inset-0 bg-black/50 flex items-center justify-center z-[1000] p-4';

export const dialogCls =
  'bg-white rounded-lg shadow-[0_4px_24px_rgba(0,0,0,0.18)] flex flex-col max-h-[90vh] w-full max-w-[560px] overflow-hidden';

export const headerCls =
  'flex items-center justify-between py-5 px-6 border-b border-[#e5e7eb] shrink-0';

export const headerTitleCls = 'm-0 text-[1.2rem] font-semibold text-[#111827]';

export const closeBtnCls =
  'bg-none border-0 text-[1.5rem] leading-none cursor-pointer text-[#6b7280] py-0 px-1 rounded transition-[color,background] duration-150 hover:enabled:text-[#111827] hover:enabled:bg-[#f3f4f6] disabled:opacity-40 disabled:cursor-not-allowed';

export const errorBannerCls =
  'flex items-center justify-between gap-2 mx-6 mt-3 py-2 px-3 bg-[#fef2f2] border border-[#fecaca] rounded-md text-[#dc2626] text-sm shrink-0';

export const errorCloseCls =
  'bg-none border-0 text-[#dc2626] text-base leading-none cursor-pointer p-0 shrink-0';

export const bodyCls =
  'flex-1 overflow-y-auto py-4 px-6 flex flex-col gap-5';

export const sectionCls = 'flex flex-col gap-3';
export const sectionTitleCls =
  'm-0 text-[0.95rem] font-semibold text-[#374151] uppercase tracking-wider';
export const formHintCls = 'm-0 text-[0.8rem] text-[#6b7280] leading-snug';
export const formFieldCls = 'flex flex-col gap-[0.3rem]';
export const formLabelCls = 'text-[0.85rem] font-medium text-[#374151]';

export const footerCls =
  'flex justify-end gap-3 py-4 px-6 border-t border-[#e5e7eb] shrink-0';

export const cancelBtnCls =
  'py-2 px-[1.1rem] border border-[#d1d5db] rounded-md bg-white text-[#374151] text-[0.9rem] cursor-pointer transition-[background,border-color] duration-150 hover:enabled:bg-[#f9fafb] hover:enabled:border-[#9ca3af] disabled:opacity-50 disabled:cursor-not-allowed';

export const saveBtnCls =
  'py-2 px-5 border-0 rounded-md bg-[#2563eb] text-white text-[0.9rem] font-medium cursor-pointer transition-colors duration-150 hover:enabled:bg-[#1d4ed8] disabled:bg-[#93c5fd] disabled:cursor-not-allowed';

export const checkboxFieldCls = 'flex items-center gap-3';

export const clearBtnCls =
  'py-1 px-2 text-xs bg-[#e0e0e0] border-0 rounded cursor-pointer hover:enabled:bg-[#d0d0d0] disabled:opacity-50 disabled:cursor-not-allowed';
