import { useEffect, useState } from 'react';
import './CallEndPage.css';

export type CallEndPageProps = {
  /** Connect this callback to your existing frontend router/home route. */
  onBackHome: () => void;
  /** Optional call duration in seconds, shown only if supplied. */
  durationSeconds?: number;
};

/** A quiet end state, with no conversation summary and no backend dependencies. */
export default function CallEndPage({ onBackHome, durationSeconds }: CallEndPageProps) {
  const [settled, setSettled] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setSettled(true), 120);
    return () => window.clearTimeout(id);
  }, []);
  const duration = typeof durationSeconds === 'number' && Number.isFinite(durationSeconds)
    ? `${Math.floor(Math.max(0, durationSeconds) / 60).toString().padStart(2,'0')}:${Math.floor(Math.max(0, durationSeconds) % 60).toString().padStart(2,'0')}`
    : null;

  return (
    <main className={`me2-end ${settled ? 'me2-end--settled' : ''}`} aria-labelledby="me2-end-title">
      <header className="me2-end__header">
        <span className="me2-end__brand" aria-label="Me squared">Me<sup>2</sup></span>
        <span className="me2-end__eyebrow">A CONVERSATION ACROSS TIME</span>
      </header>
      <section className="me2-end__content">
        <div className="me2-end__transition" aria-hidden="true">
          <div className="me2-end__particles">
            {Array.from({ length: 90 }, (_, i) => {
              const angle = i * 2.399963229728653;
              const r = Math.sqrt((i + .5) / 90);
              const x = 50 + r * 47 * Math.cos(angle);
              const y = 50 + r * 25 * Math.sin(angle);
              return <i key={i} style={{ left: `${x}%`, top: `${y}%`, opacity: .25 + .68 * r }} />;
            })}
          </div>
        </div>
        <div className="me2-end__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="m3 3 18 18"/><path d="M8.1 5.7c-.55.05-1.1.3-1.5.8l-1.3 1.6c-.45.56-.65 1.35-.42 2.05 1.35 4.2 4.75 7.6 8.95 8.95.7.23 1.49.03 2.05-.42l1.6-1.3c.5-.4.75-.95.8-1.5"/><path d="M11.2 4.8a14.5 14.5 0 0 1 8 8"/>
          </svg>
        </div>
        <div className="me2-end__copy">
          <span className="me2-end__status">CONNECTION CLOSED</span>
          <h1 id="me2-end-title">Call ended.</h1>
          <p>Your conversation with your future self has ended.</p>
          <p className="me2-end__tagline">The future is still yours to shape.</p>
          {duration && <p className="me2-end__duration">Call duration · {duration}</p>}
        </div>
        <button className="me2-end__button" type="button" onClick={onBackHome}>
          Back to Home <span aria-hidden="true">↗</span>
        </button>
      </section>
      <footer className="me2-end__footer">Me² · Your future, your story.</footer>
    </main>
  );
}
