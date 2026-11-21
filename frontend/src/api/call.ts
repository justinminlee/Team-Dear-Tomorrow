import { API_URL, ApiError, apiRequest } from "./auth";

export type ChatMessage = { role: "user" | "assistant"; content: string };
export type SpokenReply = { text: string; audio: string; audio_type: string };

export const callApi = {
  /** Cloned voices the future self can speak with, e.g. ["TJ", "Peter", "Indian"]. */
  voices: () => apiRequest<{ voices: string[]; default: string | null }>("/call/voices"),

  /** The future self's opening line, as text and base64 MP3, in the chosen voice. */
  start: (voice?: string) =>
    apiRequest<{ reply: SpokenReply }>("/call/start", { method: "POST", body: JSON.stringify({ voice: voice ?? null }) }),

  /** One exchange: the user's WAV recording in, the transcript and reply out. */
  async turn(wav: Blob, history: ChatMessage[], voice?: string): Promise<{ heard: string; reply: SpokenReply | null }> {
    const form = new FormData();
    form.append("audio", wav, "turn.wav");
    form.append("history", JSON.stringify(history));
    if (voice) form.append("voice", voice);
    let response: Response;
    try {
      // No Content-Type header: the browser sets the multipart boundary itself.
      response = await fetch(`${API_URL}/call/turn`, { method: "POST", body: form, credentials: "include" });
    } catch {
      throw new ApiError("Can't reach the server.", 0);
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new ApiError(typeof data.detail === "string" ? data.detail : "Request failed", response.status);
    }
    return data;
  },
};
