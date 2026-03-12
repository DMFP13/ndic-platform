import React from 'react';
import { Loader2 } from 'lucide-react';

const SIZE_MAP = {
  sm: 16,
  md: 24,
  lg: 40,
};

export default function Spinner({ size = 'md', label = 'Loading...' }) {
  const px = SIZE_MAP[size] || SIZE_MAP.md;
  return (
    <div className="flex flex-col items-center justify-center gap-2 p-4" role="status" aria-label={label}>
      <Loader2 size={px} className="animate-spin text-blue-600" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
