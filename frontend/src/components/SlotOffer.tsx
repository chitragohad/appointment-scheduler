type SlotOption = {
  id: string
  label: string
  startText: string
}

type SlotOfferProps = {
  slots: SlotOption[]
  caption: string
  onSelect: (index: 1 | 2) => void
  onEnd: () => void
}

export function SlotOffer({ slots, caption, onSelect, onEnd }: SlotOfferProps) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-gutter">
      <p className="mb-md w-full text-center text-label-sm uppercase tracking-widest text-primary">
        Agent speaking…
      </p>
      <p
        className="w-full max-w-2xl text-center text-headline-md leading-relaxed text-on-surface"
        style={{ animation: 'caption-in 0.45s ease both' }}
      >
        {caption}
      </p>
      <div className="mt-lg flex w-full flex-col gap-md">
        {slots.map((slot, i) => (
          <button
            key={slot.id}
            type="button"
            onClick={() => onSelect((i + 1) as 1 | 2)}
            className="group w-full rounded-lg border border-outline-variant bg-surface-container-lowest p-lg text-left transition-all hover:border-primary hover:bg-surface-container-low focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary active:scale-[0.99]"
          >
            <div className="flex items-center gap-md">
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-DEFAULT text-lg font-semibold ${
                  i === 0
                    ? 'bg-primary-fixed text-primary'
                    : 'bg-secondary-fixed text-secondary'
                }`}
              >
                {i + 1}
              </div>
              <div>
                <div className="text-headline-md text-primary">Option {i + 1}</div>
                <div className="text-body-lg text-on-surface-variant">{slot.startText}</div>
              </div>
            </div>
          </button>
        ))}
      </div>
      <div className="mt-xl flex flex-wrap justify-center gap-md">
        {slots.map((_, i) => (
          <button
            key={`cta-${i}`}
            type="button"
            onClick={() => onSelect((i + 1) as 1 | 2)}
            className="flex items-center gap-sm rounded-lg bg-primary px-lg py-sm text-label-md text-on-primary transition hover:bg-primary-container active:scale-[0.98]"
          >
            <span className="material-symbols-outlined fill text-[20px]" aria-hidden>
              check_circle
            </span>
            Option {i + 1}
          </button>
        ))}
        <button
          type="button"
          onClick={onEnd}
          className="rounded-lg border border-outline px-lg py-sm text-label-md text-on-surface-variant transition hover:border-error-container hover:bg-error-container hover:text-on-error-container"
        >
          End session
        </button>
      </div>
    </div>
  )
}
