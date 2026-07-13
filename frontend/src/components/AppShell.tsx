import type { ReactNode } from 'react'

const INTENTS = [
  { label: 'Reschedule', prompt: 'I want to reschedule' },
  { label: 'Cancel', prompt: 'I want to cancel my booking' },
  { label: 'What to prepare', prompt: 'What should I prepare' },
  { label: 'Check availability', prompt: 'What times are available' },
] as const

type ShellProps = {
  children: ReactNode
  onIntent?: (prompt: string) => void
  showIntents?: boolean
}

export function AppShell({ children, onIntent, showIntents = true }: ShellProps) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden bg-background text-on-background">
      <div className="acoustic-grain pointer-events-none fixed inset-0 z-50" aria-hidden />

      <header className="relative z-40 bg-background">
        <nav className="mx-auto flex w-full max-w-[1140px] items-center justify-between px-gutter py-md">
          <div className="font-display text-headline-md tracking-tight text-primary">
            ADVISOR APPOINTMENT SCHEDULER
          </div>
          <div className="flex items-center gap-md text-primary">
            <span className="material-symbols-outlined" aria-hidden>
              account_circle
            </span>
            <span className="material-symbols-outlined" aria-hidden>
              settings
            </span>
          </div>
        </nav>
      </header>

      <main className="relative z-10 flex flex-1 flex-col">{children}</main>

      <footer className="relative z-40 border-t border-surface-variant bg-background">
        <div className="mx-auto flex w-full max-w-[1140px] flex-col items-center gap-base px-gutter py-lg text-center">
          {showIntents && (
            <div className="mb-sm flex flex-wrap justify-center gap-lg">
              {INTENTS.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  className="text-label-sm text-secondary underline decoration-outline-variant underline-offset-4 transition-colors hover:text-primary"
                  onClick={() => onIntent?.(item.prompt)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
          <p className="w-full max-w-2xl text-label-sm text-secondary opacity-70">
            © 2026 Advisor Appointment Scheduler. No PII on call. Secure encrypted links. All times
            in IST.
          </p>
        </div>
      </footer>
    </div>
  )
}
