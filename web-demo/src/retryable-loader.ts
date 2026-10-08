/** Share one startup attempt, retain success, and permit an explicit retry after failure. */
export function retryableLoader<T>(load: () => Promise<T>): () => Promise<T> {
  let loading: Promise<T> | undefined;
  return () => {
    if (!loading) {
      loading = Promise.resolve().then(load).catch(error => {
        loading = undefined;
        throw error;
      });
    }
    return loading;
  };
}
