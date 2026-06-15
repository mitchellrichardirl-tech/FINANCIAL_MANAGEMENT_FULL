/**
 * @file BreadcrumbNav.jsx
 * Clickable ancestor path: Category › Sub-category › Type › [current].
 * Each ancestor is a button that navigates up; the current node is
 * rendered as plain text.
 */

import './BreadcrumbNav.css';

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
    <nav className="breadcrumb-nav" aria-label="Hierarchy path">
      {breadcrumb.map((crumb) => (
        <span key={`${crumb.level}:${crumb.id}`} className="breadcrumb-nav__segment">
          <button
            type="button"
            className="breadcrumb-nav__link"
            onClick={() => onNavigate(crumb)}
          >
            {crumb.name}
          </button>
          <span className="breadcrumb-nav__sep" aria-hidden="true">›</span>
        </span>
      ))}
      <span className="breadcrumb-nav__current">{currentName}</span>
    </nav>
  );
}