type HttpLikeError = {
  response?: {
    status?: number
  }
}

export const shouldRetryQuery = (
  failureCount: number,
  error: unknown,
): boolean => {
  const status = (error as HttpLikeError)?.response?.status
  if (status && [401, 403, 404, 422].includes(status)) {
    return false
  }
  return failureCount < 2
}

export const queryRetryDelay = (attemptIndex: number): number =>
  Math.min(1000 * 2 ** attemptIndex, 10_000)
