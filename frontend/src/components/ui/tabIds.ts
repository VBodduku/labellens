/** Matching ids so each tab and its panel reference each other (aria-controls / aria-labelledby). */
export const tabId = (prefix: string, id: string) => `${prefix}-tab-${id}`;
export const panelId = (prefix: string, id: string) => `${prefix}-panel-${id}`;
