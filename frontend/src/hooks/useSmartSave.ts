import { useState, useCallback } from 'react';
import { useToast } from '../components/common/ToastProvider';
import { saveQuery, addDashboardWidget, listDashboards } from '../services/api';
import { inferViz, autoTitle, layoutDims } from '../utils/dashboardUtils';
import type { ChatMessageView } from '../types/chat';
import type { WidgetSize } from '../types/dashboard';

export function useSmartSave() {
  const { addToast } = useToast();
  const [isSaving, setIsSaving] = useState(false);

  /**
   * Smart Add to Dashboard
   */
  const smartAddToDashboard = useCallback(async (
    message: ChatMessageView,
    connectionId: string,
    onOpenModal: () => void
  ) => {
    const lastDashId = localStorage.getItem('lastUsedDashboardId');
    setIsSaving(true);

    try {
      // 1. Fetch dashboards to see if lastUsed exists
      const dashboards = await listDashboards();
      const targetDash = dashboards.find(d => d.id === lastDashId) || dashboards[0];

      if (!targetDash) {
        // No dashboards exist, open modal
        onOpenModal();
        return;
      }

      // 2. Add widget immediately
      const vizType = inferViz(message);
      const rows = message.rows || [];
      const columns = message.columns || [];
      const size: WidgetSize = vizType === 'kpi' ? 'quarter' : (vizType === 'table' || (vizType === 'bar' && rows.length > 6) ? 'full' : 'half');
      const dims = layoutDims(size);

      await addDashboardWidget({
        dashboard_id: targetDash.id,
        title: autoTitle(message),
        viz_type: vizType,
        size,
        connection_id: connectionId,
        sql: message.sql || '',
        columns,
        rows: rows as Array<Record<string, unknown>>,
        chart_config: message.chart_recommendation ? {
          x_column: message.chart_recommendation.x_column,
          y_columns: message.chart_recommendation.y_columns,
          color_column: message.chart_recommendation.color_column,
          is_grouped: message.chart_recommendation.is_grouped,
          title: message.chart_recommendation.title,
          x_label: message.chart_recommendation.x_label,
          y_label: message.chart_recommendation.y_label,
        } : undefined,
        cadence: 'Manual only',
        w: dims.w, h: dims.h, minW: dims.minW, minH: dims.minH,
        bar_orientation: 'horizontal',
      });

      // 3. Persist and notify
      localStorage.setItem('lastUsedDashboardId', targetDash.id);
      addToast(`Added to ${targetDash.name}`, 'success', {
        label: 'Settings',
        onClick: onOpenModal
      });
    } catch (err) {
      console.error('Smart add failed:', err);
      // Fallback to modal on error
      onOpenModal();
    } finally {
      setIsSaving(false);
    }
  }, [addToast]);

  /**
   * Smart Save to Library
   */
  const smartSaveToLibrary = useCallback(async (
    sql: string,
    connectionId: string,
    defaultTitle: string,
    onOpenModal: () => void,
    onSuccess: () => void
  ) => {
    const lastFolder = localStorage.getItem('lastUsedFolder') || 'Uncategorized';
    setIsSaving(true);

    try {
      // 1. Use last folder if set; folders are created implicitly when a query is saved there.
      const targetFolder = lastFolder || 'Uncategorized';

      // 2. Save query immediately
      await saveQuery({
        title: defaultTitle,
        sql,
        connection_id: connectionId,
        folder_name: targetFolder,
      });

      // 3. Notify
      localStorage.setItem('lastUsedFolder', targetFolder);
      addToast(`Saved to ${targetFolder}`, 'success', {
        label: 'Settings',
        onClick: onOpenModal
      });
      onSuccess();
    } catch (err) {
      console.error('Smart save failed:', err);
      onOpenModal();
    } finally {
      setIsSaving(false);
    }
  }, [addToast]);

  return {
    smartAddToDashboard,
    smartSaveToLibrary,
    isSaving
  };
}
