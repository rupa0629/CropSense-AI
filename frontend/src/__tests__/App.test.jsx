import { render } from '@testing-library/react'
import React, { createElement } from 'react'
import { expect, test } from 'vitest'

globalThis.React = React
const { default: App } = await import('../App')

test('renders loading or auth screen without crashing', () => {
  render(createElement(App))
  expect(document.body).toBeTruthy()
})
