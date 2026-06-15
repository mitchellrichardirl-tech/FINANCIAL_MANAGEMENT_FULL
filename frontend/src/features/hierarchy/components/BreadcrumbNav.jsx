/**
 * @file BreadcrumbNav.jsx
 * Clickable ancestor path: Category › Sub-category › Type › [current].
 * Each ancestor is a button that navigates up; the current node is
 * rendered as plain text.
 */

/**
 * @component
 * @param {Object} props
 * @param {Array<{id: number, name: string, level: string}>} props.breadcrumb
 *        Ancestors ordered root-first. Empty for root-level categories.
 * @param {string} props.currentName - Name of the currently selected node.
 * @param {(crumb: {level: string, id: number}) => void} props.onNavigate
 * @returns {JSX.Element}
 */
export default function BreadcrumbNav({ breadcrumb, currentName, onNavigate }) {
  return (
    <nav
      className="flex flex-wrap items-center gap-1 text-[0.85rem] text-[#888]"
      aria-label="Hierarchy path"
    >
      {breadcrumb.map((crumb) => (
        <span
          key={`${crumb.level}:${crumb.id}`}
          className="inline-flex items-center gap-1"
        >
          <button
            type="button"
            className="px-[0.2rem] py-[0.1rem] text-[#2b7de9] cursor-pointer rounded-[3px] hover:underline hover:bg-[#eef3f8]"
            onClick={() => onNavigate(crumb)}
          >
            {crumb.name}
          </button>
          <span className="text-[#aaa]" aria-hidden="true">›</span>
        </span>
      ))}
      <span className="text-[#333] font-medium">{currentName}</span>
    </nav>
  );
}