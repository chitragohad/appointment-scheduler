const FLOW_STEPS = ['Disclaimer', 'Topic', 'Time', 'Slots', 'Confirm'] as const

type StepIndicatorProps = {
  active: (typeof FLOW_STEPS)[number] | 'Welcome'
}

export function StepIndicator({ active }: StepIndicatorProps) {
  const steps = ['Welcome', ...FLOW_STEPS] as const
  const activeIndex = Math.max(
    0,
    steps.findIndex((s) => s === active),
  )

  return (
    <nav
      className="mb-lg flex flex-wrap items-center justify-center gap-sm text-label-sm uppercase tracking-widest"
      aria-label="Booking progress"
    >
      {steps.map((step, index) => {
        const isActive = index === activeIndex
        const isDone = index < activeIndex
        return (
          <div key={step} className="flex items-center gap-sm">
            {index > 0 && <span className="h-px w-3 bg-outline-variant" aria-hidden />}
            <span
              className={
                isActive
                  ? 'border-b-2 border-primary py-xs font-semibold text-primary'
                  : isDone
                    ? 'text-primary/70'
                    : 'text-secondary opacity-60'
              }
            >
              {String(index + 1).padStart(2, '0')} {step}
            </span>
          </div>
        )
      })}
    </nav>
  )
}
