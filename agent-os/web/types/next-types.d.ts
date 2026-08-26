/// <reference types="next" />
/// <reference types="next/image-types/global" />

// Next normally generates `next-env.d.ts` at the project root during
// `next dev` / `next build`, and that file is gitignored on the assumption it
// will always be regenerated. This project builds through `vinext`, which does
// not generate it, so a fresh clone had no reference to Next's types at all and
// `import type { Metadata } from 'next'` failed with TS7016 in both
// `app/layout.tsx` and `next.config.ts`.
//
// This committed shim supplies the same references. It sits outside the root so
// it does not collide with a generated `next-env.d.ts` if the toolchain ever
// changes; tsconfig picks it up via the `**/*.ts` include.
