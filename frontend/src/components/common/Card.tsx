import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glass?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, glass = false, className, ...props }) => {
  return (
    <div
      className={twMerge(
        clsx(
          'rounded-xl p-6 transition-all duration-200 bg-white border border-slate-200/90 shadow-sm text-slate-800',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};
