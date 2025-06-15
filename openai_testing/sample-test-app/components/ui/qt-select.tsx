import { ChevronDown } from "lucide-react";

type Props = {
  value: number;
  onChange: (n: number) => void;
};

export function QtSelect({ value, onChange }: Props) {
  return (
    <div className="relative w-16">
      <select
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value, 10))}
        className="peer h-9 w-full cursor-pointer rounded-md border border-input bg-background px-2
                   pr-4 text-sm outline-none ring-offset-background
                   hover:bg-accent/30 focus-visible:ring-1 focus-visible:ring-ring/50
                   disabled:cursor-not-allowed disabled:opacity-50
                   appearance-none"
      >
        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>

      <ChevronDown
        className="pointer-events-none absolute right-1.5 top-1/2 size-4 -translate-y-1/2
                   text-muted-foreground transition-opacity peer-disabled:opacity-40"
      />
    </div>
  );
}
