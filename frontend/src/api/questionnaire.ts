import { API_URL, ApiError, apiRequest } from "./auth";
import type { Answer, Question, QuestionType } from "../components/QuestionnairePage";

/** Shape returned by GET /questionnaire (backend/app/api/questionnaire.py). */
type ApiQuestion = {
  id: string;
  code: string;
  category: string;
  text: string;
  type: "text" | "number" | "single_choice" | "multiple_choice" | "scale" | "boolean";
  options: { value: string; label: string }[] | null;
  min: number | null;
  max: number | null;
  order: number;
};

/** Intro line shown under each section title. Unknown categories show none. */
const SECTION_DESCRIPTIONS: Record<string, string> = {
  "About You": "Let's start with who you are today.",
  "Personality": "How you think, decide and bounce back.",
  "Values & Ambitions": "What matters to you, and where you want to go.",
  "Lifestyle": "How you live, spend and connect right now.",
  "Your Future Self":
    "Imagine the person you could become. Answer these out loud: your words are turned into text, and the way you speak is used to make your future self sound like you. The recording itself isn't kept.",
  "Conversation Boundaries":
    "Choose any topics you'd prefer your future self to avoid. These are preferences, not a guarantee of complete filtering.",
};

/** Free-text questions in these sections are answered by voice. */
const VOICE_SECTIONS = new Set(["Your Future Self"]);

function toQuestion(q: ApiQuestion, sectionOrder: number): Question {
  // Free-text answers in this questionnaire are mostly sentences, so use a textarea.
  const type: QuestionType = q.type === "text" ? "textarea" : q.type;
  return {
    id: q.id,
    text: q.text,
    type,
    voice: q.type === "text" && VOICE_SECTIONS.has(q.category),
    sectionId: q.category,
    sectionTitle: q.category,
    sectionDescription: SECTION_DESCRIPTIONS[q.category],
    options: q.options ?? undefined,
    min: q.min ?? undefined,
    max: q.max ?? undefined,
    order: q.order,
    sectionOrder,
  };
}

export const questionnaireApi = {
  async questions(): Promise<Question[]> {
    const { questions } = await apiRequest<{ questions: ApiQuestion[] }>("/questionnaire");
    // Sections appear in the order of their first question.
    const sectionOrder = new Map<string, number>();
    for (const q of questions) {
      if (!sectionOrder.has(q.category)) sectionOrder.set(q.category, sectionOrder.size);
    }
    return questions.map((q) => toQuestion(q, sectionOrder.get(q.category)!));
  },

  /** The user's latest saved answers, keyed by question id. */
  async myAnswers(): Promise<Record<string, Answer>> {
    const { answers } = await apiRequest<{ answers: Record<string, Answer> }>("/questionnaire/answers");
    return answers;
  },

  save(answers: Record<string, Answer>) {
    return apiRequest<{ saved: number; unchanged: number }>("/questionnaire/answers", {
      method: "POST",
      body: JSON.stringify({ answers }),
    });
  },

  /** Turn a recorded answer into text (nothing is saved yet). */
  async transcribe(audio: Blob): Promise<string> {
    const form = new FormData();
    form.append("audio", audio, "answer.webm");
    let response: Response;
    try {
      // No Content-Type header: the browser sets the multipart boundary itself.
      response = await fetch(`${API_URL}/questionnaire/transcribe`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
    } catch {
      throw new ApiError("Can't reach the server. Is the backend running?", 0);
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new ApiError(typeof data?.detail === "string" ? data.detail : "Couldn't transcribe that.", response.status);
    }
    return data.text as string;
  },

  /** After saving: tell the server which saved answers were spoken, for speaking-style learning. */
  saveVoiceSamples(questionIds: string[]) {
    return apiRequest<{ queued: number }>("/questionnaire/voice-samples", {
      method: "POST",
      body: JSON.stringify({ question_ids: questionIds }),
    });
  },
};
