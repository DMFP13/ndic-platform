import React from 'react';

export default function Card({ title, children, className = '', action }) {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          {title && (
            <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          )}
          {action && <div className="ml-auto">{action}</div>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
