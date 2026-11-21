-- Run this in the Supabase SQL editor ONLY if dim_voice / dim_chat / dim_msg already exist.
-- (create_tables.py creates missing tables but never changes existing ones.)
-- Everything runs in one transaction: if any step fails, nothing is changed.

BEGIN;

-- 3. A voice belongs to the user, not to one chat.
ALTER TABLE public.dim_chat ADD COLUMN IF NOT EXISTS voice_id INTEGER
    REFERENCES public.dim_voice (voice_id) ON DELETE SET NULL;

-- Keep the existing chat <-> voice links before dropping dim_voice.chat_id.
UPDATE public.dim_chat c
SET voice_id = v.voice_id
FROM public.dim_voice v
WHERE v.chat_id = c.chat_id AND c.voice_id IS NULL;

ALTER TABLE public.dim_voice DROP COLUMN IF EXISTS chat_id;
ALTER TABLE public.dim_voice ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
-- NOTE: fails if a user already has the same voice twice; remove the duplicates first.
ALTER TABLE public.dim_voice ADD CONSTRAINT uq_voice_user_voice UNIQUE (id, voice);

-- 4. Messages know who wrote them and when.
-- Existing rows have no role; they are marked 'user' here. Fix any AI replies afterwards.
ALTER TABLE public.dim_msg ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';
ALTER TABLE public.dim_msg ALTER COLUMN role DROP DEFAULT;
ALTER TABLE public.dim_msg ADD CONSTRAINT ck_msg_role CHECK (role IN ('user', 'assistant'));
ALTER TABLE public.dim_msg ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS ix_msg_chat_created ON public.dim_msg (chat_id, created_at);

COMMIT;

-- After this, run `python create_tables.py` to create dim_qs and the 4 speaking style tables.
