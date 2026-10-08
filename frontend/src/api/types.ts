// Mirrors the API responses in backend/routes. Rubric text never reaches the client.

export type StepState =
  | 'planned'
  | 'taught'
  | 'built'
  | 'reviewed'
  | 'toured'
  | 'interviewing'
  | 'passed'
  | 'slide_done'
  | 'blocked'

export interface Message {
  id: number
  agent: string
  role: 'user' | 'assistant' | 'reteach'
  content: string
}

export interface Step {
  id: number
  project_id: number
  position: number
  title: string
  component: string
  goal: string
  concepts: string[]
  state: StepState
  current: boolean
  lesson: string | null
  build_note: BuildNote | null
  review_note: string | null
  build?: BuildStatus
  chat: Message[]
  gate: Message[]
  progress: { covered: number; total: number }
  can_hint: boolean
}

export interface BuildNote {
  files: { path: string; summary: string }[]
  decisions: string[]
  not_done: string[]
}

export interface BuildStatus {
  running: boolean
  paused: boolean
  error: string | null
  isolation: 'docker' | 'venv'
}

export interface PlanView {
  questions: string[]
  project_name: string
  one_liner: string
  stack: string[]
  changes_from_spine: { step: string; change: string; reason: string }[]
  steps: { title: string; goal: string; concepts: string[]; component: string }[]
}

export interface Project {
  id: number
  name: string
  brief: string
  status: 'planning' | 'active' | 'finishing' | 'done'
  plan: PlanView | null
  steps: Step[]
  current_step_id: number | null
}

export interface KeyStatus {
  saved: boolean
  last4: string | null
}
