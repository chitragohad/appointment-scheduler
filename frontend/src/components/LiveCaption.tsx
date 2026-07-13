type LiveCaptionProps = {
  text: string
  emphasis?: boolean
}

export function LiveCaption({ text, emphasis = false }: LiveCaptionProps) {
  if (!text) return null
  return (
    <div
      className={`mt-lg w-full max-w-2xl border border-outline-variant/40 bg-surface-container-lowest px-md py-sm text-center ${
        emphasis ? 'rounded-xl' : 'rounded-lg'
      }`}
      style={{ animation: 'caption-in 0.45s ease both' }}
      role="status"
      aria-live="polite"
    >
      <p
        className={`text-body-md italic leading-relaxed text-primary ${
          emphasis ? 'text-body-lg not-italic font-display text-headline-md' : ''
        }`}
      >
        {text.startsWith('"') ? text : `"${text}"`}
      </p>
    </div>
  )
}
