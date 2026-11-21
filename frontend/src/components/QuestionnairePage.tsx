import { useEffect, useMemo, useState } from "react";
import "./QuestionnairePage.css";

/** Replace the example shape with the actual backend response using adaptQuestions. */
export type QuestionType = "text" | "number" | "textarea" | "single_choice" | "multiple_choice" | "scale";
export interface Question {
  id: string | number;
  text: string;
  type: QuestionType;
  sectionId: string;
  sectionTitle: string;
  sectionDescription?: string;
  options?: { value: string; label: string }[];
  required?: boolean; // Omitted = not marked required until confirmed by the team
  min?: number;
  max?: number;
  placeholder?: string;
  order?: number;
  sectionOrder?: number;
}
export type Answer = string | number | string[];
export type QuestionnaireResult = { answers: Record<string, Answer>; restrictedTopics: string[] };
export interface QuestionnairePageProps {
  /** The backend endpoint; default is an illustrative path, not a confirmed endpoint. */
  endpoint?: string;
  /** Use this if the backend has different field names or a nested API response. */
  loadQuestions?: () => Promise<Question[]>;
  /** App handles saving the results and navigating to the next screen. */
  onSubmit?: (result: QuestionnaireResult) => void | Promise<void>;
  onBackToLogin?: () => void;
}
const TOPICS = ["Health", "Finances", "Religion", "Political Views"];

function adaptQuestions(payload: unknown): Question[] {
  // This is a SAMPLE adapter. Confirm real field names with your backend team.
  const data = Array.isArray(payload) ? payload : (payload && typeof payload === "object" && "questions" in payload ? (payload as { questions: unknown }).questions : null);
  if (!Array.isArray(data)) throw new Error("Unexpected questions response. Check API field mapping.");
  return data.map((item: unknown, index: number) => {
    const q = item as Record<string, unknown>;
    const id = q.id;
    const text = q.text ?? q.question_text;
    const rawType = String(q.type ?? q.question_type ?? "text").toLowerCase();
    const types: Record<string, QuestionType> = { text:"text", string:"text", number:"number", numeric:"number", textarea:"textarea", long_text:"textarea", options:"single_choice", radio:"single_choice", single_choice:"single_choice", select:"single_choice", checkbox:"multiple_choice", multiple_choice:"multiple_choice", slider:"scale", scale:"scale" };
    const type = types[rawType];
    if ((typeof id !== "number" && typeof id !== "string") || typeof text !== "string" || !type) throw new Error(`Invalid question at index ${index}. Check API field mapping.`);
    const rawOptions = q.options;
    const options = Array.isArray(rawOptions) ? rawOptions.map((option: unknown) => typeof option === "string" ? {value:option,label:option} : ({ value: String((option as Record<string, unknown>).value ?? (option as Record<string, unknown>).id ?? ""), label: String((option as Record<string, unknown>).label ?? (option as Record<string, unknown>).text ?? "") })) : undefined;
    return {
      id, text, type,
      sectionId: String(q.sectionId ?? q.section_id ?? q.section ?? "general"),
      sectionTitle: String(q.sectionTitle ?? q.section_title ?? q.section ?? "Questionnaire"),
      sectionDescription: typeof q.sectionDescription === "string" ? q.sectionDescription : undefined,
      options, required: q.required === true,
      min: typeof q.min === "number" ? q.min : undefined,
      max: typeof q.max === "number" ? q.max : undefined,
      placeholder: typeof q.placeholder === "string" ? q.placeholder : undefined,
      order: typeof q.order === "number" ? q.order : index,
      sectionOrder: typeof q.sectionOrder === "number" ? q.sectionOrder : undefined,
    };
  });
}

export default function QuestionnairePage({ endpoint = "/api/questions", loadQuestions, onSubmit, onBackToLogin }: QuestionnairePageProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [page, setPage] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [restrictedTopics, setRestrictedTopics] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState("");
  useEffect(() => {
    let active = true;
    setStatus("loading");
    (async () => {
      try {
        const loaded = loadQuestions ? await loadQuestions() : await (async () => {
          const response = await fetch(endpoint);
          if (!response.ok) throw new Error(`Could not load questions (${response.status}).`);
          return adaptQuestions(await response.json());
        })();
        if (active) { setQuestions(loaded); setStatus("ready"); }
      } catch (err) { if (active) { setError(err instanceof Error ? err.message : "Could not load questions."); setStatus("error"); } }
    })();
    return () => { active = false; };
  }, [endpoint, loadQuestions, reload]);
  const sections = useMemo(() => {
    const grouped = new Map<string, { id: string; title: string; description?: string; sectionOrder: number; questions: Question[] }>();
    questions.forEach(q => {
      if (!grouped.has(q.sectionId)) grouped.set(q.sectionId, {id:q.sectionId,title:q.sectionTitle,description:q.sectionDescription,sectionOrder:q.sectionOrder ?? grouped.size,questions:[]});
      grouped.get(q.sectionId)!.questions.push(q);
    });
    return [...grouped.values()].sort((a,b)=>a.sectionOrder-b.sectionOrder).map(s=>({...s,questions:s.questions.sort((a,b)=>(a.order??0)-(b.order??0))}));
  }, [questions]);
  const totalSteps = sections.length + 1; // + Conversation Boundaries
  const safePage = Math.min(page, Math.max(totalSteps - 1,0));
  const current = sections[safePage];
  const boundaries = safePage === sections.length;
  const percent = Math.round(((safePage + 1) / Math.max(totalSteps, 1)) * 100);
  const setAnswer = (id: string | number, value: Answer) => setAnswers(prev => ({...prev, [String(id)]: value}));
  const validate = (): boolean => {
    if (boundaries || !current) return true;
    const firstMissing = current.questions.find(q => q.required && (answers[String(q.id)] === undefined || answers[String(q.id)] === "" || (Array.isArray(answers[String(q.id)]) && (answers[String(q.id)] as string[]).length === 0)));
    if (firstMissing) { document.getElementById(`me2-q-${firstMissing.id}`)?.focus(); setSubmissionError("Please answer the required questions before continuing."); return false; }
    setSubmissionError(""); return true;
  };
  const next = async () => {
    if (!validate()) return;
    if (!boundaries) {setPage(p => p+1); window.scrollTo({top:0,behavior:"smooth"}); return;}
    if (!onSubmit) { setSubmissionError("Demo mode: your team needs to connect the submit action."); return; }
    setSubmitting(true); setSubmissionError("");
    try { await onSubmit({answers,restrictedTopics}); }
    catch(err) {setSubmissionError(err instanceof Error ? err.message : "Could not submit questionnaire.");}
    finally {setSubmitting(false);}
  };
  const renderQuestion = (q: Question, number: number) => {
    const key = String(q.id), value = answers[key];
    const qId = `me2-q-${key}`;
    return <div className="me2-question" key={key}>
      <div className="me2-qtop"><span className="me2-qnum">Q{String(number).padStart(2,"0")}</span><label className="me2-qtitle" htmlFor={qId}>{q.text} {q.required && <span className="me2-required">*</span>}</label></div>
      {q.type === "single_choice" || q.type === "multiple_choice" ? <div className="me2-options" id={qId} role="group" aria-label={q.text} tabIndex={-1}>
        {(q.options ?? []).map(o => {
          const selected = q.type === "multiple_choice" ? Array.isArray(value) && value.includes(o.value) : value === o.value;
          return <button key={o.value} type="button" className={`me2-option${selected?" is-selected":""}`} aria-pressed={selected} onClick={()=> {
            if (q.type === "single_choice") setAnswer(key,o.value);
            else setAnswer(key, selected ? ((value as string[]).filter(x=>x!==o.value)) : [...(Array.isArray(value)?value:[]),o.value]);
          }}><span className={`me2-selector ${q.type === "multiple_choice" ? "multi" : ""}`} aria-hidden="true"/><span>{o.label}</span></button>;
        })}
      </div> : q.type === "scale" ? <div className="me2-slider-row"><input id={qId} type="range" min={q.min??1} max={q.max??10} step={1} value={typeof value === "number" ? value : (q.min??1)} onChange={e=>setAnswer(key,Number(e.target.value))}/><strong>{typeof value === "number" ? value : (q.min??1)}/{q.max??10}</strong></div>
      : q.type === "textarea" ? <textarea id={qId} value={typeof value === "string" ? value : ""} placeholder={q.placeholder??"Your answer..."} onChange={e=>setAnswer(key,e.target.value)}/>
      : <input className="me2-textbox" id={qId} type={q.type === "number" ? "number" : "text"} min={q.type==="number"?q.min:undefined} max={q.type==="number"?q.max:undefined} value={value === undefined ? "" : String(value)} placeholder={q.placeholder??"Your answer..."} onChange={e=>setAnswer(key,q.type === "number" && e.target.value!=="" ? Number(e.target.value) : e.target.value)}/>}
    </div>;
  };
  return <div className="me2-survey"><div className="me2-shell">
    <header className="me2-header"><div className="me2-logo">Me²</div><div className="me2-top-right"><span className="me2-led"/>BEFORE THE CALL</div></header>
    <div className="me2-layout"><aside className="me2-aside"><div className="me2-eyebrow">YOUR CONNECTION</div><h2>A little about you, before we connect.</h2><p>Every future begins with who you are today.</p><nav className="me2-step-list" aria-label="Questionnaire sections">
      {sections.map((s,i)=><button key={s.id} type="button" className={`me2-step ${safePage===i?"active":""} ${safePage>i?"done":""}`} onClick={()=>{setPage(i);setSubmissionError("");}}><span className="me2-number">{safePage>i?"✓":String(i+1).padStart(2,"0")}</span><span>{s.title}</span></button>)}
      {sections.length>0 && <button type="button" className={`me2-step ${boundaries?"active":""}`} onClick={()=>{setPage(sections.length);setSubmissionError("");}}><span className="me2-number">{String(totalSteps).padStart(2,"0")}</span><span>Conversation Boundaries</span></button>}
    </nav><div className="me2-tip"><div>A NOTE FROM TOMORROW</div><p>Your answers help create an imagined future version of you, not a prediction.</p></div></aside>
    <main className="me2-main"><div className="me2-mobile-step">BEFORE THE CALL</div>
      {status === "loading" ? <div role="status" className="me2-state">Loading questions…</div> : status === "error" ? <div className="me2-state" role="alert"><h1>Questions couldn't load</h1><p>{error}</p><button className="me2-button" onClick={()=>setReload(n=>n+1)}>Try again</button></div> : questions.length===0 ? <div className="me2-state">No questions available.</div> : <>
      <div className="me2-progress-row"><span>{boundaries ? "CONVERSATION BOUNDARIES" : `SECTION ${String(safePage+1).padStart(2,"0")} / ${String(sections.length).padStart(2,"0")}`}</span><span>Step {safePage+1} of {totalSteps}</span></div>
      <div className="me2-bar" role="progressbar" aria-label="Questionnaire progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><div className="me2-fill" style={{width:`${percent}%`}}/></div>
      <div className="me2-intro"><div className="me2-kicker">{boundaries ? "YOUR CHOICE, YOUR BOUNDARIES" : "LET'S GET TO KNOW YOU"}</div><h1>{boundaries ? "Choose your conversation boundaries." : current?.title}</h1><p>{boundaries ? "Select any topics you'd prefer your future self to avoid discussing." : current?.description}</p></div>
      <div className="me2-form">{boundaries ? <section className="me2-question"><div className="me2-qtop"><span className="me2-qnum">SETTINGS</span><span className="me2-qtitle">Chat Restricted Topics Settings</span></div><p className="me2-restriction-note">These are conversation preferences, not a guarantee of complete filtering.</p>{TOPICS.map(t=><label className="me2-boundary" key={t}><input type="checkbox" checked={restrictedTopics.includes(t)} onChange={e=>setRestrictedTopics(prev=>e.target.checked?[...prev,t]:prev.filter(x=>x!==t))}/>{t}</label>)}</section> : current?.questions.map((q)=>renderQuestion(q,questions.findIndex(item=>String(item.id)===String(q.id))+1))}</div>
      {submissionError && <p className="me2-error" role="alert">{submissionError}</p>}
      <div className="me2-footer"><button className="me2-button secondary" type="button" onClick={()=>safePage===0?onBackToLogin?.():setPage(p=>Math.max(0,p-1))} disabled={safePage===0&&!onBackToLogin}>{safePage===0?"← Back":"← Previous"}</button><button className="me2-button" type="button" onClick={next} disabled={submitting}>{submitting?"Connecting…":boundaries?"Finish →":"Continue →"}</button></div>
      <p className="me2-note">Your answers help create a fictional future self. Review privacy information before providing sensitive details.</p>
      </>}
    </main></div>
  </div></div>;
}
