import React from 'react';

const STATUS_MAP = {
  healthy:   { label: 'Healthy',   className: 'bg-green-100 text-green-800' },
  at_risk:   { label: 'At Risk',   className: 'bg-amber-100 text-amber-800' },
  critical:  { label: 'Critical',  className: 'bg-red-100 text-red-800' },
  confirmed: { label: 'Confirmed', className: 'bg-red-100 text-red-800' },
  suspected: { label: 'Suspected', className: 'bg-yellow-100 text-yellow-800' },
  resolved:  { label: 'Resolved',  className: 'bg-gray-100 text-gray-700' },
  low:       { label: 'Low',       className: 'bg-green-100 text-green-800' },
  medium:    { label: 'Medium',    className: 'bg-amber-100 text-amber-800' },
  high:      { label: 'High',      className: 'bg-red-100 text-red-800' },
  active:    { label: 'Active',    className: 'bg-blue-100 text-blue-800' },
  monitoring:{ label: 'Monitoring',className: 'bg-purple-100 text-purple-800' },
  info:      { label: 'Info',      className: 'bg-blue-100 text-blue-800' },
  warning:   { label: 'Warning',   className: 'bg-amber-100 text-amber-800' },
};

export default function StatusBadge({ status }) {
  const config = STATUS_MAP[status] || { label: status, className: 'bg-gray-100 text-gray-700' };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  );
}
