type VoiceOrbProps = {
  mode: 'idle' | 'listening' | 'speaking' | 'processing' | 'success'
  statusLabel: string
  onClick?: () => void
}

export function VoiceOrb({ mode, statusLabel, onClick }: VoiceOrbProps) {
  const interactive = Boolean(onClick)
  const pulsing = mode === 'listening' || mode === 'speaking'
  const breathing = mode === 'processing' || mode === 'success'

  return (
    <div className="relative flex flex-col items-center">
      <button
        type="button"
        onClick={onClick}
        disabled={!interactive}
        aria-label={statusLabel}
        className={`relative flex h-48 w-48 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-container transition-transform duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary ${
          interactive ? 'cursor-pointer hover:scale-[1.03] active:scale-[0.98]' : 'cursor-default'
        }`}
        style={{
          boxShadow:
            mode === 'idle'
              ? '0 0 60px rgba(12, 82, 82, 0.18)'
              : '0 0 80px 20px rgba(12, 82, 82, 0.22)',
          animation: breathing ? 'orb-breathe 3s ease-in-out infinite' : undefined,
        }}
      >
        {pulsing && (
          <>
            <span
              className="absolute inset-0 rounded-full bg-primary-fixed-dim"
              style={{ animation: 'orb-pulse 2.8s ease-in-out infinite' }}
              aria-hidden
            />
            <span
              className="absolute inset-0 rounded-full bg-primary-fixed-dim"
              style={{ animation: 'orb-pulse 2.8s ease-in-out infinite 1.2s' }}
              aria-hidden
            />
          </>
        )}
        <span
          className="material-symbols-outlined fill relative z-10 text-on-primary"
          style={{ fontSize: 56 }}
          aria-hidden
        >
          mic
        </span>
      </button>
      <div className="mt-md">
        <span
          className={`inline-block rounded-DEFAULT border px-md py-xs text-label-md ${
            mode === 'listening'
              ? 'border-primary/20 bg-primary-container/15 text-primary-container'
              : 'border-primary/10 bg-primary-fixed/30 text-primary'
          }`}
        >
          {statusLabel}
        </span>
      </div>
    </div>
  )
}
