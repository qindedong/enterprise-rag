/**
 * 自定义 Hooks
 */

import { useState, useCallback, useRef, useEffect } from 'react'

/**
 * 防抖 Hook
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}

/**
 * 组件的加载/空/错误状态
 */
export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useAsyncState<T>(initialData: T | null = null) {
  const [state, setState] = useState<AsyncState<T>>({
    data: initialData,
    loading: false,
    error: null,
  })

  const setLoading = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }))
  }, [])

  const setData = useCallback((data: T) => {
    setState({ data, loading: false, error: null })
  }, [])

  const setError = useCallback((error: string) => {
    setState((s) => ({ ...s, loading: false, error }))
  }, [])

  const reset = useCallback(() => {
    setState({ data: initialData, loading: false, error: null })
  }, [initialData])

  return { ...state, setLoading, setData, setError, reset, setState }
}

/**
 * 自动保存的 ref Hook
 */
export function useAutoSaveRef<T>(value: T, delay = 3000) {
  const savedValue = useRef(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      savedValue.current = value
    }, delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return savedValue
}
