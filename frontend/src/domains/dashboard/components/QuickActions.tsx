type QuickActionsProps = {
  actions: string[];
  onAction: (action: string) => void;
};

export function QuickActions({ actions, onAction }: QuickActionsProps) {
  return (
    <section className="panel quick-actions" aria-labelledby="quick-actions-title">
      <div className="panel-header">
        <h2 id="quick-actions-title">Quick Actions</h2>
      </div>
      <div className="action-row">
        {actions.map((action) => (
          <button className="primary-action" key={action} type="button" onClick={() => onAction(action)}>
            {action}
          </button>
        ))}
      </div>
    </section>
  );
}
