import { useState, useEffect, useMemo, useCallback } from 'react';
export function useTaxonomyCascade({
  isOpen,
  categories,
  subCategories,
  types,
  parties,
  initialPartyId = null,
}) {
  const [categoryId, setCategoryId] = useState(null);
  const [subCategoryId, setSubCategoryId] = useState(null);
  const [typeId, setTypeId] = useState(null);
  const [partyId, setPartyId] = useState(null);
  /**
   * Reset on open. When `initialPartyId` is supplied, walk up the
   * hierarchy to pre-fill every level. Runs once per open so inline
   * creates don't clobber the user's selection.
   */
  useEffect(() => {
    if (!isOpen) return;
    const party = initialPartyId ? parties.find((p) => p.id === initialPartyId) : null;
    const type = party ? types.find((t) => t.id === party.type_id) : null;
    const sub = type ? subCategories.find((s) => s.id === type.sub_category_id) : null;
    setPartyId(party?.id ?? null);
    setTypeId(type?.id ?? null);
    setSubCategoryId(sub?.id ?? null);
    setCategoryId(sub?.category_id ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);
  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories],
  );
  const filteredSubCategories = useMemo(() => {
    if (!categoryId) return [];
    return [...subCategories]
      .filter((sc) => sc.category_id === categoryId)
      .sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, categoryId]);
  const filteredTypes = useMemo(() => {
    if (!subCategoryId) return [];
    return [...types]
      .filter((t) => t.sub_category_id === subCategoryId)
      .sort((a, b) => a.type.localeCompare(b.type));
  }, [types, subCategoryId]);
  const filteredParties = useMemo(() => {
    if (!typeId) return [];
    return [...parties]
      .filter((p) => p.type_id === typeId)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [parties, typeId]);
  const selectCategory = useCallback((id) => {
    setCategoryId(id ? parseInt(id) : null);
    setSubCategoryId(null); setTypeId(null); setPartyId(null);
  }, []);
  const selectSubCategory = useCallback((id) => {
    setSubCategoryId(id ? parseInt(id) : null);
    setTypeId(null); setPartyId(null);
  }, []);
  const selectType = useCallback((id) => {
    setTypeId(id ? parseInt(id) : null);
    setPartyId(null);
  }, []);
  const selectParty = useCallback((id) => {
    setPartyId(id ? parseInt(id) : null);
  }, []);
  return {
    categoryId, subCategoryId, typeId, partyId,
    sortedCategories, filteredSubCategories, filteredTypes, filteredParties,
    selectCategory, selectSubCategory, selectType, selectParty,
  };
}
