import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { Idea, IdeaBatch, LessonPathView } from '../api/types'
import { routes } from '../routes'
import { fakeApi, makeProject } from '../testing'

const idea = (name: string): Idea => ({
  name,
  line: `${name} line`,
  pitch: 'A longer pitch.',
  difficulty: 'medium',
  step_count: 5,
  thumbnail: {
    template: 'ranked',
    data_json: JSON.stringify({ query: 'q', items: [{ label: 'a', score: 0.9 }] }),
  },
  concepts: [
    { name: 'cosine similarity', familiarity: 'used' },
    { name: 'chunking', familiarity: 'new' },
  ],
  architecture: ['Loader', 'Index', 'API'],
  questions: ['Why chunk?'],
})
const BATCH: IdeaBatch = { id: 3, topic: 'RAG', cards: ['A', 'B', 'C', 'D'].map(idea) }

const PATH: LessonPathView = {
  id: 5,
  concept: 'chunking',
  status: 'active',
  return_idea_id: 3,
  return_card: 1,
  dropped_note: 'This section was left out: the topic needs a source that supports it.',
  lessons: [
    {
      title: 'What a chunk is',
      goal: 'Split text.',
      key_terms: ['chunk'],
      dropped: ['recap'],
      passages: { '1:0': { title: 'sbert docs', text: 'A chunk is a piece of a document.' } },
      content: {
        title: 'What a chunk is',
        by_the_end: ['split a document'],
        community: [{ text: 'People use 500-token chunks.', source_id: '2:0' }],
        sections: [
          {
            kind: 'start_here',
            paragraphs: [{ text: 'A chunk is a piece of a document.', citations: ['1:0'] }],
            visual_json: '',
            code: '',
            questions: [],
          },
          {
            kind: 'check_yourself',
            paragraphs: [],
            visual_json: '',
            code: '',
            questions: [
              {
                type: 'tf',
                prompt: 'Bigger chunks are always better.',
                options: [
                  { text: 'True', correct: false, why: 'Big chunks dilute the match.' },
                  { text: 'False', correct: true, why: 'It is a trade-off.' },
                ],
                answer: '',
                rubric: [],
                tests: '',
              },
            ],
          },
          {
            kind: 'your_turn',
            paragraphs: [],
            visual_json: '',
            code: '',
            questions: [
              {
                type: 'short',
                prompt: 'Why overlap chunks?',
                options: [],
                answer: 'x',
                rubric: ['a', 'b'],
                tests: '',
              },
            ],
          },
        ],
      },
    },
    { title: 'Retrieval', goal: 'Find chunks.', key_terms: [], dropped: [], content: null },
    { title: 'Ranking', goal: 'g', key_terms: [], dropped: [], content: null },
    { title: 'Answering', goal: 'g', key_terms: [], dropped: [], content: null },
  ],
}

const renderAt = (path: string) =>
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />)

describe('Start: give me ideas', () => {
  it('shows four cards, expands one, and builds it', async () => {
    const calls = fakeApi({
      'POST /api/ideas': BATCH,
      'POST /api/ideas/3/build': makeProject(),
      'GET /api/projects/current': null,
    })
    renderAt('/start')
    await userEvent.click(screen.getByRole('button', { name: /Give me ideas Pick a topic/ }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Topic' }), 'RAG')
    await userEvent.click(screen.getByRole('button', { name: 'Files I upload' }))
    await userEvent.click(screen.getByRole('button', { name: 'Give me ideas' }))
    expect(calls[0].body).toEqual({ topic: 'RAG', use: '', data: 'Files I upload' })
    expect(await screen.findAllByRole('article')).toHaveLength(4)
    expect(screen.getAllByText('used it before')).toHaveLength(4)
    await userEvent.click(screen.getByRole('button', { name: /^B / }))
    expect(screen.getByText('Why chunk?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Build this' }))
    expect(calls.find((c) => c.path === '/api/ideas/3/build')?.body).toEqual({ card: 1 })
    expect(await screen.findByRole('heading', { name: 'Mission control' })).toBeInTheDocument()
  })
})

describe('Lesson screen', () => {
  it('shows cited sections, checks answers, notes dropped sections, and returns to the idea', async () => {
    const calls = fakeApi({
      'GET /api/lessons/5': PATH,
      'POST /api/lessons/5/answer': { covered: 1, total: 2, feedback: 'mention overlap' },
      'GET /api/ideas/3': BATCH,
    })
    renderAt('/lesson/5')
    expect(await screen.findByText('A chunk is a piece of a document.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Source 1' }))
    expect(screen.getByText('1. sbert docs')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'True' }))
    expect(screen.getByText(/Not quite\. Big chunks dilute the match\./)).toBeInTheDocument()

    await userEvent.type(
      screen.getByRole('textbox', { name: 'Your answer' }),
      'So sentences are not cut.',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Check my answer' }))
    expect(await screen.findByText(/1 of 2 points covered\. mention overlap/)).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/api/lessons/5/answer')?.body).toEqual({
      lesson: 0,
      section: 'your_turn',
      question: 0,
      answer: 'So sentences are not cut.',
    })

    expect(screen.getByText(/Recap: This section was left out/)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Community' })).toHaveTextContent('500-token chunks')

    await userEvent.click(screen.getByRole('button', { name: 'Back to the idea' }))
    expect(await screen.findByText('Why chunk?')).toBeInTheDocument() // card 1 reopened
  })
})
