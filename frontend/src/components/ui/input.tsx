import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-11 w-full rounded-xl border border-input bg-card px-3.5 py-2 text-base text-foreground file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground/80 transition-colors hover:border-foreground/30 focus-visible:outline-none focus-visible:border-secondary focus-visible:ring-[3px] focus-visible:ring-secondary/20 disabled:cursor-not-allowed disabled:opacity-50 md:text-[15px]",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };
