import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ThemeToggleButton } from './ThemeToggleButton'

describe('ThemeToggleButton', () => {
  it('toggles the document theme and persisted preference', () => {
    render(<ThemeToggleButton />)

    const button = screen.getByRole('button', { name: 'Switch to light mode' })
    fireEvent.click(button)

    expect(screen.getByRole('button', { name: 'Switch to dark mode' })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(window.localStorage.getItem('jurisai-theme')).toBe('light')
  })

  it('uses the saved theme on first render', () => {
    window.localStorage.setItem('jurisai-theme', 'light')

    render(<ThemeToggleButton />)

    expect(screen.getByRole('button', { name: 'Switch to dark mode' })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe('light')
  })
})
