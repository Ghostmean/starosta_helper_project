import { useEffect, useMemo, useState } from 'react'
import './App.css'

type Lesson = {
  day_of_week: number
  starts_at: string
  ends_at: string
  week_pattern: 'EVERY' | 'TOP' | 'BOTTOM'
  subject: string
  instructor_name: string | null
  room: string | null
}

type Schedule = {
  course_name: string
  group_name: string
  weekdays: Record<number, string>
  lessons: Lesson[]
}

const weekLabels: Record<Lesson['week_pattern'], string> = {
  EVERY: 'Каждую неделю',
  TOP: 'Верхняя неделя',
  BOTTOM: 'Нижняя неделя',
}

const dayLabels: Record<number, string> = {
  1: 'Пн',
  2: 'Вт',
  3: 'Ср',
  4: 'Чт',
  5: 'Пт',
  6: 'Сб',
  7: 'Вс',
}

function currentDayOfWeek() {
  const day = new Date().getDay()
  return day === 0 ? 7 : day
}

function lessonCountLabel(count: number) {
  const lastTwoDigits = count % 100
  if (lastTwoDigits >= 11 && lastTwoDigits <= 14) return 'пар'
  const lastDigit = count % 10
  if (lastDigit === 1) return 'пара'
  if (lastDigit >= 2 && lastDigit <= 4) return 'пары'
  return 'пар'
}

function App() {
  const [schedule, setSchedule] = useState<Schedule | null>(null)
  const [selectedDay, setSelectedDay] = useState(currentDayOfWeek)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const webApp = window.Telegram?.WebApp
    webApp?.ready()
    webApp?.expand()

    const controller = new AbortController()
    fetch('/api/schedule', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          const body = (await response.json()) as { detail?: string }
          throw new Error(body.detail ?? 'Не удалось загрузить расписание.')
        }
        return (await response.json()) as Schedule
      })
      .then(setSchedule)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setError(reason instanceof Error ? reason.message : 'Произошла неизвестная ошибка.')
      })

    return () => controller.abort()
  }, [])

  const lessons = useMemo(
    () =>
      schedule?.lessons
        .filter((lesson) => lesson.day_of_week === selectedDay)
        .sort((a, b) => a.starts_at.localeCompare(b.starts_at)) ?? [],
    [schedule, selectedDay],
  )

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <span className="brand-name">Староста</span>
        <span className="beta-badge">ТЕСТ</span>
      </header>

      <section className="welcome">
        <p className="eyebrow">ТВОЁ РАСПИСАНИЕ</p>
        <h1>Учёба —<br />по плану.</h1>
        <p className="welcome-copy">Все пары на день — в одном месте.</p>
      </section>

      <section className="schedule-panel" aria-label="Расписание группы">
        {schedule ? (
          <>
            <div className="group-heading">
              <div>
                <p className="eyebrow muted">{schedule.course_name}</p>
                <h2>{schedule.group_name}</h2>
              </div>
              <span className="calendar-icon" aria-hidden="true">▦</span>
            </div>

            <nav className="day-picker" aria-label="Выбрать день недели">
              {Object.entries(schedule.weekdays).map(([day, name]) => {
                const dayNumber = Number(day)
                const selected = selectedDay === dayNumber
                return (
                  <button
                    className={`day-button${selected ? ' selected' : ''}`}
                    key={day}
                    onClick={() => setSelectedDay(dayNumber)}
                    type="button"
                    aria-pressed={selected}
                    aria-label={name}
                  >
                    {dayLabels[dayNumber]}
                  </button>
                )
              })}
            </nav>

            <div className="lesson-list">
              <div className="day-title">
                <h3>{schedule.weekdays[selectedDay]}</h3>
                <span>{lessons.length} {lessonCountLabel(lessons.length)}</span>
              </div>

              {lessons.length ? (
                lessons.map((lesson, index) => (
                  <article className="lesson-card" key={`${lesson.starts_at}-${index}`}>
                    <div className="lesson-time">
                      <strong>{lesson.starts_at.slice(0, 5)}</strong>
                      <span>{lesson.ends_at.slice(0, 5)}</span>
                      <i aria-hidden="true" />
                    </div>
                    <div className="lesson-details">
                      <span className={`week-tag week-${lesson.week_pattern.toLowerCase()}`}>
                        {weekLabels[lesson.week_pattern]}
                      </span>
                      <h4>{lesson.subject}</h4>
                      {lesson.instructor_name && (
                        <p className="lesson-meta">{lesson.instructor_name}</p>
                      )}
                      {lesson.room && <p className="room-tag">⌖ {lesson.room}</p>}
                    </div>
                  </article>
                ))
              ) : (
                <div className="empty-state">
                  <span aria-hidden="true">✳</span>
                  <p>В этот день пар нет.<br />Можно выдохнуть.</p>
                </div>
              )}
            </div>
          </>
        ) : error ? (
          <div className="error-state" role="alert">
            <h2>Расписание пока недоступно</h2>
            <p>{error}</p>
            <button className="retry-button" onClick={() => window.location.reload()} type="button">
              Попробовать ещё раз
            </button>
          </div>
        ) : (
          <div className="loading-state" role="status">
            <span className="loader" />
            <p>Загружаем расписание…</p>
          </div>
        )}
      </section>

      <footer className="app-footer">
        <span className="footer-dot" />
        Тестовая версия · только расписание
      </footer>
    </main>
  )
}

export default App
