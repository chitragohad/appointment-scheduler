type BookingConfirmedProps = {
  code: string
  whenText: string
  secureUrl: string
  onOpenSecureLink: () => void
}

export function BookingConfirmed({
  code,
  whenText,
  secureUrl,
  onOpenSecureLink,
}: BookingConfirmedProps) {
  return (
    <div className="mx-auto flex w-full max-w-[1140px] flex-col items-center gap-xl px-gutter lg:flex-row lg:items-center lg:justify-between">
      <div className="flex-1 space-y-md text-center lg:text-left">
        <div className="mb-base inline-flex items-center gap-sm rounded-lg bg-tertiary-fixed px-md py-xs">
          <span className="material-symbols-outlined fill text-tertiary" aria-hidden>
            check_circle
          </span>
          <span className="text-label-md font-semibold text-tertiary">Appointment confirmed</span>
        </div>
        <h2 className="text-display-brand leading-tight text-primary max-md:text-headline-lg">
          Appointment confirmed for {whenText}
        </h2>
        <p className="w-full max-w-2xl text-body-lg text-on-surface-variant">
          Your tentative advisor slot is held. Complete contact details later via the secure link —
          nothing personal was collected on this call.
        </p>

        <div className="mt-lg inline-block rounded-xl border border-outline-variant bg-surface-container-lowest p-lg">
          <span className="mb-xs block text-label-sm uppercase tracking-widest text-secondary">
            Your booking code
          </span>
          <div className="font-display text-display-brand tracking-widest text-primary max-md:text-headline-lg">
            {[...code].map((ch, i) => (
              <span
                key={`${ch}-${i}`}
                className="inline-block"
                style={{ animation: `code-in 0.5s ease ${i * 0.08}s both` }}
              >
                {ch}
              </span>
            ))}
          </div>
        </div>

        <div className="pt-lg">
          <button
            type="button"
            onClick={onOpenSecureLink}
            className="mx-auto flex items-center gap-sm rounded-lg bg-primary px-lg py-md text-label-md text-on-primary transition hover:bg-primary-container active:scale-[0.98] lg:mx-0"
          >
            Open secure link to complete details
            <span className="material-symbols-outlined text-[20px] leading-none" aria-hidden>
              arrow_forward
            </span>
          </button>
          {secureUrl && (
            <p className="mt-sm break-all text-label-sm text-secondary">{secureUrl}</p>
          )}
        </div>
      </div>

      <div className="relative flex min-h-[280px] flex-1 items-center justify-center">
        <div
          className="absolute h-64 w-64 rounded-full"
          style={{
            background:
              'radial-gradient(circle, rgba(149,209,209,0.4) 0%, rgba(12,82,82,0.1) 70%, transparent 100%)',
            animation: 'orb-breathe 4s ease-in-out infinite',
          }}
          aria-hidden
        />
        <div className="relative z-10 grid h-48 w-48 place-items-center rounded-xl bg-primary shadow-sm">
          <span
            className="material-symbols-outlined fill text-on-primary leading-none"
            style={{ fontSize: 48, lineHeight: 1, display: 'block' }}
            aria-hidden
          >
            mic
          </span>
        </div>
      </div>
    </div>
  )
}
