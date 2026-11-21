import { useEffect, useMemo, useState, type SyntheticEvent } from "react";
import "./QuestionnairePage.css";

export type QuestionType =
  | "text"
  | "textarea"
  | "number"
  | "single_choice"
  | "multiple_choice"
  | "scale"
  | "boolean";

export interface Question {
  id: string | number;
  text: string;
  type: QuestionType;
  sectionId: string;
  sectionTitle: string;
  sectionDescription?: string;
  options?: { value: string; label: string }[];
  required?: boolean;
  min?: number;
  max?: number;
  placeholder?: string;
  order?: number;
  sectionOrder?: number;
}

export type Answer = string | number | boolean | string[];

export interface QuestionnairePageProps {
  loadQuestions: () => Promise<Question[]>;
  /** Previously saved answers, so the user can pick up where they left off. */
  loadAnswers?: () => Promise<Record<string, Answer>>;
  /** Persist answers. Called on every "Continue" and on "Finish". */
  saveAnswers: (answers: Record<string, Answer>) => Promise<void>;
  onComplete: () => void;
  onBack?: () => void;
}

const BOOLEAN_OPTIONS = [
  { value: "true", label: "Yes" },
  { value: "false", label: "No" },
];

/** Drop blank answers so we never send "" or whitespace to the backend. */
function cleanAnswers(answers: Record<string, Answer>): Record<string, Answer> {
  return Object.fromEntries(
    Object.entries(answers).filter(([, v]) => !(typeof v === "string" && v.trim() === ""))
  );
}

function isAnswered(value: Answer | undefined): boolean {
  if (value === undefined) return false;
  if (typeof value === "string") return value.trim() !== "";
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

export default function QuestionnairePage({
  loadQuestions,
  loadAnswers,
  saveAnswers,
  onComplete,
  onBack,
}: QuestionnairePageProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState("");
  const [reload, setReload] = useState(0);
  const [page, setPage] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [loaded, saved] = await Promise.all([
          loadQuestions(),
          loadAnswers ? loadAnswers() : Promise.resolve({}),
        ]);
        if (!active) return;
        setQuestions(loaded);
        setAnswers(saved);
        if (Object.keys(saved).length > 0) setNotice("Welcome back. Your saved answers are filled in.");
        setStatus("ready");
      } catch (err) {
        if (!active) return;
        setLoadError(err instanceof Error ? err.message : "Could not load questions.");
        setStatus("error");
      }
    })();
    return () => {
      active = false;
    };
  }, [loadQuestions, loadAnswers, reload]);

  const sections = useMemo(() => {
    const grouped = new Map<
      string,
      { id: string; title: string; description?: string; sectionOrder: number; questions: Question[] }
    >();
    for (const q of questions) {
      if (!grouped.has(q.sectionId)) {
        grouped.set(q.sectionId, {
          id: q.sectionId,
          title: q.sectionTitle,
          description: q.sectionDescription,
          sectionOrder: q.sectionOrder ?? grouped.size,
          questions: [],
        });
      }
      grouped.get(q.sectionId)!.questions.push(q);
    }
    return [...grouped.values()]
      .sort((a, b) => a.sectionOrder - b.sectionOrder)
      .map((s) => ({ ...s, questions: [...s.questions].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)) }));
  }, [questions]);

  // Question numbers follow the on-screen order across all sections.
  const numbers = useMemo(() => {
    const map = new Map<string, number>();
    sections.flatMap((s) => s.questions).forEach((q, i) => map.set(String(q.id), i + 1));
    return map;
  }, [sections]);

  const total = sections.length;
  const safePage = Math.min(page, Math.max(total - 1, 0));
  const current = sections[safePage];
  const isLast = safePage === total - 1;
  const answeredCount = questions.filter((q) => isAnswered(answers[String(q.id)])).length;
  const percent = questions.length ? Math.round((answeredCount / questions.length) * 100) : 0;

  const setAnswer = (id: string | number, value: Answer) => {
    setAnswers((prev) => ({ ...prev, [String(id)]: value }));
    setNotice("");
  };

  const goTo = (index: number) => {
    setPage(index);
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const validateSection = (): boolean => {
    const missing = current?.questions.find((q) => q.required && !isAnswered(answers[String(q.id)]));
    if (missing) {
      document.getElementById(`me2-q-${missing.id}`)?.focus();
      setError("Please answer the required questions before continuing.");
      return false;
    }
    return true;
  };

  const next = async () => {
    if (!validateSection()) return;
    const toSave = cleanAnswers(answers);
    if (isLast && Object.keys(toSave).length === 0) {
      setError("Please answer at least one question before finishing.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (Object.keys(toSave).length > 0) await saveAnswers(toSave);
      if (isLast) onComplete();
      else {
        setNotice("Progress saved.");
        goTo(safePage + 1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your answers.");
    } finally {
      setSaving(false);
    }
  };

  const renderQuestion = (q: Question) => {
    const key = String(q.id);
    const value = answers[key];
    const qId = `me2-q-${key}`;
    const number = numbers.get(key) ?? 0;
    const isChoice = q.type === "single_choice" || q.type === "multiple_choice" || q.type === "boolean";
    const options = q.type === "boolean" ? BOOLEAN_OPTIONS : q.options ?? [];

    let input;
    if (isChoice) {
      input = (
        <div className="me2-options" id={qId} role="group" aria-label={q.text} tabIndex={-1}>
          {options.map((o) => {
            const selected =
              q.type === "multiple_choice"
                ? Array.isArray(value) && value.includes(o.value)
                : q.type === "boolean"
                  ? value === (o.value === "true")
                  : value === o.value;
            const choose = () => {
              if (q.type === "boolean") setAnswer(key, o.value === "true");
              else if (q.type === "single_choice") setAnswer(key, o.value);
              else {
                const list = Array.isArray(value) ? value : [];
                setAnswer(key, selected ? list.filter((x) => x !== o.value) : [...list, o.value]);
              }
            };
            return (
              <button
                key={o.value}
                type="button"
                className={`me2-option${selected ? " is-selected" : ""}`}
                aria-pressed={selected}
                onClick={choose}
              >
                <span className={`me2-selector ${q.type === "multiple_choice" ? "multi" : ""}`} aria-hidden="true" />
                <span>{o.label}</span>
              </button>
            );
          })}
        </div>
      );
    } else if (q.type === "scale") {
      const min = q.min ?? 1;
      const max = q.max ?? 10;
      const pick = (e: SyntheticEvent<HTMLInputElement>) => setAnswer(key, Number(e.currentTarget.value));
      input = (
        <div className="me2-slider-row">
          <input
            id={qId}
            type="range"
            min={min}
            max={max}
            step={1}
            value={typeof value === "number" ? value : min}
            onChange={pick}
            onClick={pick}
          />
          <strong>{typeof value === "number" ? value : "–"}/{max}</strong>
        </div>
      );
    } else if (q.type === "textarea") {
      input = (
        <textarea
          id={qId}
          value={typeof value === "string" ? value : ""}
          placeholder={q.placeholder ?? "Your answer…"}
          maxLength={2000}
          onChange={(e) => setAnswer(key, e.target.value)}
        />
      );
    } else {
      const isNumber = q.type === "number";
      input = (
        <input
          className="me2-textbox"
          id={qId}
          type={isNumber ? "number" : "text"}
          inputMode={isNumber ? "numeric" : undefined}
          min={isNumber ? q.min : undefined}
          max={isNumber ? q.max : undefined}
          maxLength={isNumber ? undefined : 2000}
          value={value === undefined ? "" : String(value)}
          placeholder={q.placeholder ?? "Your answer…"}
          onChange={(e) => {
            const raw = e.target.value;
            if (!isNumber) setAnswer(key, raw);
            else if (raw === "") {
              setAnswers((prev) => {
                const next = { ...prev };
                delete next[key];
                return next;
              });
            }
            else if (Number.isFinite(Number(raw))) setAnswer(key, Number(raw));
          }}
        />
      );
    }

    return (
      <div className="me2-question" key={key}>
        <div className="me2-qtop">
          <span className="me2-qnum">Q{String(number).padStart(2, "0")}</span>
          <label className="me2-qtitle" htmlFor={isChoice ? undefined : qId}>
            {q.text} {q.required && <span className="me2-required">*</span>}
          </label>
        </div>
        {input}
      </div>
    );
  };

  return (
    <div className="me2-survey">
      <div className="me2-shell">
        <header className="me2-header">
          <div className="me2-logo">Me²</div>
          <div className="me2-top-right">
            <span className="me2-led" />
            BEFORE THE CALL
          </div>
        </header>

        <div className="me2-layout">
          <aside className="me2-aside">
            <div className="me2-eyebrow">YOUR CONNECTION</div>
            <h2>A little about you, before we connect.</h2>
            <p>Every future begins with who you are today.</p>
            <nav className="me2-step-list" aria-label="Questionnaire sections">
              {sections.map((s, i) => {
                const done = s.questions.every((q) => isAnswered(answers[String(q.id)]));
                return (
                  <button
                    key={s.id}
                    type="button"
                    className={`me2-step ${safePage === i ? "active" : ""} ${done && safePage !== i ? "done" : ""}`}
                    aria-current={safePage === i ? "step" : undefined}
                    onClick={() => goTo(i)}
                  >
                    <span className="me2-number">{done && safePage !== i ? "✓" : String(i + 1).padStart(2, "0")}</span>
                    <span>{s.title}</span>
                  </button>
                );
              })}
            </nav>
            <div className="me2-tip">
              <div>A NOTE FROM TOMORROW</div>
              <p>Your answers help create an imagined future version of you, not a prediction.</p>
            </div>
          </aside>

          <main className="me2-main">
            <div className="me2-mobile-step">BEFORE THE CALL</div>

            {status === "loading" ? (
              <div role="status" className="me2-state">Loading questions…</div>
            ) : status === "error" ? (
              <div className="me2-state" role="alert">
                <h1>Questions couldn't load</h1>
                <p>{loadError}</p>
                <button className="me2-button" type="button" onClick={() => {
                    setStatus("loading");
                    setReload((n) => n + 1);
                  }}>
                  Try again
                </button>
              </div>
            ) : total === 0 ? (
              <div className="me2-state">No questions available yet.</div>
            ) : (
              <>
                <div className="me2-progress-row">
                  <span>
                    SECTION {String(safePage + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
                  </span>
                  <span>
                    {answeredCount} of {questions.length} answered
                  </span>
                </div>
                <div
                  className="me2-bar"
                  role="progressbar"
                  aria-label="Questions answered"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percent}
                >
                  <div className="me2-fill" style={{ width: `${percent}%` }} />
                </div>

                <div className="me2-intro">
                  <div className="me2-kicker">LET'S GET TO KNOW YOU</div>
                  <h1>{current.title}</h1>
                  {current.description && <p>{current.description}</p>}
                </div>

                <div className="me2-form">{current.questions.map(renderQuestion)}</div>

                {error && (
                  <p className="me2-error" role="alert" style={{ whiteSpace: "pre-line" }}>
                    {error}
                  </p>
                )}

                <div className="me2-footer">
                  <button
                    className="me2-button secondary"
                    type="button"
                    onClick={() => (safePage === 0 ? onBack?.() : goTo(safePage - 1))}
                    disabled={(safePage === 0 && !onBack) || saving}
                  >
                    {safePage === 0 ? "← Back" : "← Previous"}
                  </button>
                  <button className="me2-button" type="button" onClick={next} disabled={saving}>
                    {saving ? "Saving…" : isLast ? "Finish →" : "Continue →"}
                  </button>
                </div>

                <p className="me2-note" role="status">
                  {notice || "Questions are optional — answer what you're comfortable sharing. Your answers are saved each time you continue."}
                </p>
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
