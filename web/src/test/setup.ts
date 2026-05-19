import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'

type StorageRecord = Record<string, string>

function createStorageMock(seed: StorageRecord = {}) {
  const store: StorageRecord = { ...seed }

  return {
    getItem(key: string) {
      return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null
    },
    setItem(key: string, value: string) {
      store[key] = String(value)
    },
    removeItem(key: string) {
      delete store[key]
    },
    clear() {
      for (const key of Object.keys(store)) {
        delete store[key]
      }
    },
  }
}

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', {
    value: createStorageMock(),
    configurable: true,
  })
})

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  document.documentElement.dataset.theme = 'dark'
})
