import { createContext } from 'react'

/** Opens the Core access overlay; mission control's core calls it (SPEC 12). */
export const OpenCore = createContext<() => void>(() => {})
