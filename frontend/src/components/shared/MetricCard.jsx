import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function MetricCard({ label, value, trend, unit, icon: Icon, color = 'blue' }) {
  const colorMap = {
    blue: 'text-blue-600 bg-blue-50',
    green: 'text-green-600 bg-green-50',
    red: 'text-red-600 bg-red-50',
    amber: 'text-amber-600 bg-amber-50',
    purple: 'text-purple-600 bg-purple-50',
    gray: 'text-gray-600 bg-gray-100',
  };

  const iconClass = colorMap[color] || colorMap.blue;

  const trendValue = typeof trend === 'number' ? trend : null;
  const isPositive = trendValue > 0;
  const isNegative = trendValue < 0;
  const isNeutral = trendValue === 0 || trendValue === null;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-600 truncate">{label}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 tabular-nums">
            {value}
            {unit && <span className="text-sm font-normal text-gray-500 ml-1">{unit}</span>}
          </p>
          {trendValue !== null && (
            <div className={`mt-1 flex items-center gap-1 text-xs font-medium ${isPositive ? 'text-green-600' : isNegative ? 'text-red-600' : 'text-gray-500'}`}>
              {isPositive && <TrendingUp size={12} />}
              {isNegative && <TrendingDown size={12} />}
              {isNeutral && <Minus size={12} />}
              <span>
                {trendValue > 0 ? '+' : ''}{trendValue}% vs 30d
              </span>
            </div>
          )}
        </div>
        {Icon && (
          <div className={`ml-3 p-2 rounded-lg flex-shrink-0 ${iconClass}`}>
            <Icon size={18} />
          </div>
        )}
      </div>
    </div>
  );
}
