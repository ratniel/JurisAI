import { UiIcon } from './UiArt'
import { useTheme } from '../hooks/useTheme'

type ThemeToggleButtonProps = {
  className?: string
}

export function ThemeToggleButton({ className }: ThemeToggleButtonProps) {
  const { isDark, toggleTheme } = useTheme()

  return (
    <button
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={className ?? 'quiet-icon-button'}
      onClick={toggleTheme}
      type="button"
    >
      <UiIcon name={isDark ? 'sun' : 'moon'} />
    </button>
  )
}
