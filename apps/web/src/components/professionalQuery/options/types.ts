/** Minimal read-only catalog view consumed by pure option derivation. */
export type CatalogSnapshot<T> = { data: T | undefined; isPending: boolean; isError: boolean };
