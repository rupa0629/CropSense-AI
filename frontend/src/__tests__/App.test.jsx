import { render, screen } from '@testing-library/react'
import React, { createElement } from 'react'
import { expect, test } from 'vitest'

globalThis.React = React
const { default: App, Results } = await import('../App')

test('renders loading or auth screen without crashing', () => {
  render(createElement(App))
  expect(document.body).toBeTruthy()
})

test('renders the nested prediction response returned by the API', () => {
  render(createElement(Results, {
    result: {
      ok: true,
      disease: {
        disease: 'Leaf Blast',
        confidence: 0.87,
        method: 'custom model',
      },
      severity: {
        level: 'Severe',
        advice: 'Treat immediately.',
      },
      fertilizer: {
        fertiliser: ['Apply balanced potassium.'],
        immediate_action: 'Remove infected leaves.',
      },
    },
  }))

  expect(screen.getAllByText('Leaf Blast').length).toBeGreaterThan(0)
  expect(screen.getAllByText('87%').length).toBeGreaterThan(0)
  expect(screen.getByText('Apply balanced potassium.')).toBeTruthy()
})
