// One route per screen (docs/DESIGN.md section 5). `phase` marks screens not built yet;
// remove it when the screen ships in that phase (docs/BUILD_PLAN.md).
export interface Screen {
  path: string
  title: string
  phase?: number
}

export const SCREENS: Screen[] = [
  { path: '/', title: 'Mission control' },
  { path: '/start', title: 'Start a project' },
  { path: '/lesson', title: 'Concept lesson', phase: 6 },
  { path: '/squad', title: 'Squad loadout', phase: 8 },
  { path: '/audit', title: 'Audit bay', phase: 7 },
  { path: '/deck', title: 'Deck viewer', phase: 4 },
  { path: '/readme', title: 'README coach', phase: 5 },
  { path: '/archive', title: 'Archive', phase: 5 },
]
