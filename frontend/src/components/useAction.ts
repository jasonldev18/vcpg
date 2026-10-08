import { useState } from 'react'

// Runs one API action at a time and keeps its error message for display.
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    setBusy(true)
    setError(null)
    try {
      return await action()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      return undefined
    } finally {
      setBusy(false)
    }
  }

  return { busy, error, run }
}
