// localStorage can throw (private mode, blocked data); every access is guarded.
export function readStore(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeStore(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // no storage: the user will simply be asked again
  }
}

function newId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID()
  return "s-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

export function getSessionId(): string {
  const id = readStore("kontia_session") || newId()
  writeStore("kontia_session", id)
  return id
}
