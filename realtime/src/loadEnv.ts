/** Load backend_v2/.env into process.env (does not override existing vars). */
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = typeof __dirname !== 'undefined' ? __dirname : dirname(fileURLToPath(import.meta.url))

export function loadBackendEnv(): string | null {
  const candidates = [
    resolve(here, '../../.env'),
    resolve(process.cwd(), '../.env'),
    resolve(process.cwd(), '.env'),
  ]
  const path = candidates.find((p) => existsSync(p))
  if (!path) return null
  for (const raw of readFileSync(path, 'utf8').split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const i = line.indexOf('=')
    if (i <= 0) continue
    const key = line.slice(0, i).trim()
    let val = line.slice(i + 1).trim()
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1)
    }
    if (process.env[key] === undefined) process.env[key] = val
  }
  return path
}

loadBackendEnv()
