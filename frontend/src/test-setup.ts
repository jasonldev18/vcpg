import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom has no EventSource; screens only need it to exist.
class SilentEventSource {
  addEventListener() {}
  close() {}
}
vi.stubGlobal('EventSource', SilentEventSource)

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.stubGlobal('EventSource', SilentEventSource)
})
