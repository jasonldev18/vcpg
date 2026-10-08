import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Deck, DeckSlide, Finish, SlideData, Visual } from '../api/types'
import { FinishPanel } from '../components/FinishPanel'
import { VisualView } from '../components/SlideView'
import { fakeApi, makeProject } from '../testing'
import { DeckViewer } from './DeckViewer'

const slide = (title: string, visual: Visual): SlideData => ({
  title,
  kicker: 'CORE',
  what: 'does a thing',
  visual,
  decisions: [{ choice: 'Cosine', tradeoff: 'ignores scale' }],
  failure_and_scale: ['cold start'],
  struggled: [{ question: 'Why centre?', hints: 2 }],
  notes: `Notes for ${title}`,
})

const SLIDES: DeckSlide[] = [
  {
    id: 1,
    kind: 'title',
    slide: slide('Title', { kind: 'flow', spec: { steps: ['Load', 'Rank'] } }),
    code: null,
  },
  {
    id: 2,
    kind: 'step',
    slide: slide('Core', { kind: 'code', spec: { path: 'app.py', lines: [3, 4], highlight: [4] } }),
    code: ['a = 1', 'b = 2'],
  },
]

describe('slide visuals', () => {
  it('draws architecture nodes, flow steps, tables and committed code', () => {
    const { rerender } = render(
      <VisualView
        code={null}
        visual={{
          kind: 'architecture',
          spec: {
            nodes: [
              { id: 'a', label: 'Ratings CSV', group: 'data' },
              { id: 'b', label: 'KNN core', group: 'backend' },
            ],
            edges: [{ from: 'a', to: 'b', label: 'load' }],
          },
        }}
      />,
    )
    expect(screen.getByText('Ratings CSV')).toBeInTheDocument()
    expect(screen.getByText('load')).toBeInTheDocument()
    rerender(
      <VisualView
        code={null}
        visual={{ kind: 'table', spec: { columns: ['Tool'], rows: [['pandas']] } }}
      />,
    )
    expect(screen.getByRole('cell', { name: 'pandas' })).toBeInTheDocument()
    rerender(<VisualView code={['a = 1', 'b = 2']} visual={SLIDES[1].slide.visual} />)
    expect(screen.getByText('b = 2').closest('div')).toHaveClass('hl')
    expect(screen.getByText('a = 1').closest('div')).not.toHaveClass('hl')
  })
})

describe('DeckViewer', () => {
  it('reorders, exports and lists versions', async () => {
    const deck: Deck = { slides: SLIDES, exports: [] }
    const exported: Deck = {
      slides: SLIDES,
      exports: [{ id: 7, version: 1, format: 'pptx', created_at: 'now' }],
    }
    const calls = fakeApi({
      'GET /api/projects/current': makeProject(),
      'GET /api/projects/1/deck': deck,
      'POST /api/projects/1/deck/order': { slides: [SLIDES[1], SLIDES[0]], exports: [] },
      'POST /api/projects/1/deck/export': exported,
    })
    render(
      <MemoryRouter>
        <DeckViewer />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Notes for Title')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Move down' }))
    expect(calls.find((c) => c.path.endsWith('/order'))?.body).toEqual({ slide_ids: [2, 1] })
    await userEvent.click(screen.getByRole('button', { name: 'PowerPoint' }))
    expect(calls.at(-1)?.body).toEqual({ format: 'pptx' })
    expect(await screen.findByRole('link', { name: 'deck_v1.pptx' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/api/exports/7/download',
    )
  })
})

describe('FinishPanel', () => {
  const finish = (over: Partial<Finish>): Finish => ({
    stage: 'final_review',
    final_review: null,
    final_review_status: { running: false, error: null },
    retest: null,
    ...over,
  })

  it('starts the final review', async () => {
    const calls = fakeApi({ 'POST /api/projects/1/final-review': makeProject() })
    const onProject = vi.fn()
    render(
      <FinishPanel project={makeProject()} finish={finish({})} live={{}} onProject={onProject} />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Start the final review' }))
    expect(calls[0].path).toBe('/api/projects/1/final-review')
    expect(onProject).toHaveBeenCalled()
  })

  it('runs the re-test as a conversation with a count', async () => {
    const retest = {
      passed: 1,
      total: 3,
      current_step: 'KNN core',
      messages: [{ id: 1, agent: 'retest', role: 'assistant' as const, content: 'Why cosine?' }],
    }
    const calls = fakeApi({ 'POST /api/projects/1/retest/answer': makeProject() })
    render(
      <FinishPanel
        project={makeProject()}
        finish={finish({ stage: 'retest', retest })}
        live={{}}
        onProject={vi.fn()}
      />,
    )
    expect(screen.getByText('1 of 3 steps re-tested')).toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox', { name: 'Your answer' }), 'direction only')
    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(calls[0].body).toEqual({ answer: 'direction only' })
  })

  it('links to the deck viewer once the deck is ready', () => {
    render(
      <MemoryRouter>
        <FinishPanel
          project={makeProject()}
          finish={finish({ stage: 'deck' })}
          live={{}}
          onProject={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Open the deck viewer' })).toHaveAttribute(
      'href',
      '/deck',
    )
  })
})
