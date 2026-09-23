/**
 * Client for the FastAPI backend.
 *
 * `GET /api/courses` returns the raw rows from yale_som_classes.json, so the keys
 * have spaces and title case. We keep a faithful `RawCourse` type and normalise into
 * the friendlier `Course` the components actually render.
 */

export const API_BASE =
  import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export interface RawCourse {
  'Course ID': string
  'Course Number': string
  'Course Title': string
  'Course Category': string
  'Course Description': string
  'Course Type': string
  'Course Session': string
  Section: string
  Units: string
  Daytimes: string
  Room: string
  'Faculty 1': string
  'Faculty 1 Email': string
  faculty_bio: string
  'Bid Or Permission': string
  Syllabus: string
  [key: string]: string
}

export interface Course {
  key: string
  id: string
  number: string
  title: string
  category: string
  description: string
  section: string
  units: string
  when: string
  room: string
  faculty: string
  facultyEmail: string
  facultyBio: string
  session: string
  bid: string
  syllabus: string
}

export interface ChatReply {
  reply: string
  tools_used: string[]
}

/**
 * 79 rows carry `Room: " "` and a few have padded titles/numbers. A lone space is
 * truthy in JS, so every `{course.room && …}` guard would pass and render a label
 * with nothing after it. Trim on the way in.
 */
const s = (value: string | undefined): string => (value ?? '').trim()

export function normalise(row: RawCourse, index: number): Course {
  return {
    // Course ID repeats across sections, so pair it with the index for a stable key.
    key: `${s(row['Course ID']) || 'x'}-${s(row.Section)}-${index}`,
    id: s(row['Course ID']),
    number: s(row['Course Number']),
    title: s(row['Course Title']),
    category: s(row['Course Category']),
    description: s(row['Course Description']),
    section: s(row.Section),
    units: s(row.Units),
    when: s(row.Daytimes),
    room: s(row.Room),
    faculty: s(row['Faculty 1']),
    facultyEmail: s(row['Faculty 1 Email']),
    facultyBio: s(row.faculty_bio),
    session: s(row['Course Session']),
    bid: s(row['Bid Or Permission']),
    syllabus: s(row.Syllabus),
  }
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return (await res.json()) as T
}

export async function fetchCourses(
  query?: string,
  signal?: AbortSignal,
): Promise<Course[]> {
  const url = new URL('/api/courses', API_BASE)
  if (query) url.searchParams.set('q', query)
  const data = await asJson<{ count: number; courses: RawCourse[] }>(
    await fetch(url, { signal }),
  )
  return data.courses.map(normalise)
}

export async function sendChat(
  message: string,
  signal?: AbortSignal,
): Promise<ChatReply> {
  const res = await fetch(new URL('/api/chat', API_BASE), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  })
  return asJson<ChatReply>(res)
}

export async function fetchHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(new URL('/api/health', API_BASE), { signal })
    return res.ok
  } catch {
    return false
  }
}
