export function Metric({
  icon,
  label,
  value,
  danger = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className={danger ? "danger" : ""}>
      {icon}
      <span>
        <strong>{value}</strong>
        <small>{label}</small>
      </span>
    </div>
  );
}
