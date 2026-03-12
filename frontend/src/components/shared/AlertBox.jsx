import React from 'react';
import { AlertTriangle, XCircle, Info, CheckCircle } from 'lucide-react';

const CONFIG = {
  critical: {
    container: 'bg-red-50 border border-red-200',
    title: 'text-red-800',
    message: 'text-red-700',
    Icon: XCircle,
    iconClass: 'text-red-500',
  },
  warning: {
    container: 'bg-amber-50 border border-amber-200',
    title: 'text-amber-800',
    message: 'text-amber-700',
    Icon: AlertTriangle,
    iconClass: 'text-amber-500',
  },
  info: {
    container: 'bg-blue-50 border border-blue-200',
    title: 'text-blue-800',
    message: 'text-blue-700',
    Icon: Info,
    iconClass: 'text-blue-500',
  },
  success: {
    container: 'bg-green-50 border border-green-200',
    title: 'text-green-800',
    message: 'text-green-700',
    Icon: CheckCircle,
    iconClass: 'text-green-500',
  },
};

export default function AlertBox({ level = 'info', title, message, actions }) {
  const cfg = CONFIG[level] || CONFIG.info;
  const { Icon } = cfg;

  return (
    <div className={`rounded-lg p-4 ${cfg.container}`}>
      <div className="flex items-start gap-3">
        <Icon size={16} className={`mt-0.5 flex-shrink-0 ${cfg.iconClass}`} />
        <div className="flex-1 min-w-0">
          {title && (
            <p className={`text-sm font-semibold ${cfg.title}`}>{title}</p>
          )}
          {message && (
            <p className={`mt-0.5 text-sm ${cfg.message}`}>{message}</p>
          )}
          {actions && <div className="mt-2">{actions}</div>}
        </div>
      </div>
    </div>
  );
}
