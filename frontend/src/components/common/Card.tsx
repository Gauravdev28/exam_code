import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glass?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, glass = true, className, ...props }) => {
  return (
    <div
      className={twMerge(
        clsx(
          'rounded-xl p-6 transition-all duration-200',
          glass ? 'glass-panel shadow-xl' : 'bg-slate-900 border border-slate-800',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};
