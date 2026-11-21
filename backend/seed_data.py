"""Default questions and scenarios, safe to run repeatedly."""
import json
from sqlalchemy import text

DEFAULT_QUESTIONS = [
    ('age','About You','How old are you?','number',None),
    ('occupation','About You','What do you currently do?','text',None),
    ('traits','About You','If you could describe yourself in three words, what would they be?','text',None),
    ('satisfaction','About You','On a scale of 1–10, how satisfied are you with your life right now?','scale',{'min':1,'max':10}),
    ('decision','Personality','When making an important decision, what do you rely on most?','single_choice',['Logic and facts','Feelings and intuition','Advice from others','A combination of these']),
    ('failure','Personality','How do you usually respond to failure?','single_choice',['Analyse what went wrong and try again','Feel discouraged but eventually recover','Look for a different opportunity','Avoid similar situations in the future']),
    ('risk','Personality','Which best describes your attitude towards risk?','single_choice',['I strongly prefer stability and security','I prefer stability but occasionally take risks',"I'm comfortable taking calculated risks",'I enjoy uncertainty and new challenges']),
    ('social','Personality','What gives you the most energy?','single_choice',['Spending time alone','Spending time with a few close friends','Meeting and interacting with many people','It depends on my mood and situation']),
    ('values','Values & Ambitions','What matters most to you in life?','single_choice',['Career success and achievement','Family, love, and relationships','Freedom and independence','Financial security and stability','Personal growth and learning','Making a positive difference in the world']),
    ('goal','Values & Ambitions','What is the biggest goal you want to achieve within the next 10 years?','text',None),
    ('success','Values & Ambitions','What does a successful life look like to you personally?','text',None),
    ('obstacle','Values & Ambitions',"What is the biggest challenge or concern you're currently facing?",'text',None),
    ('balance','Lifestyle','How would you describe your current work-life balance?','single_choice',['My life revolves around work or studies','I prioritise work but make time for myself','I maintain a healthy balance','I prioritise my personal life and well-being']),
    ('money','Lifestyle','Which best describes your financial habits?','single_choice',['I regularly save and invest','I carefully budget my spending','I prefer spending money on experiences','I spend freely and focus on enjoying the present']),
    ('location','Lifestyle','Where would you ideally like to live in 10 years?','text',None),
    ('relationships','Lifestyle','Which relationships are most important to you right now?','single_choice',['Family','Romantic partner','Close friends','Colleagues and professional connections','A combination of these']),
    ('future_job','Your Future Self','What kind of career or role do you imagine yourself having 10 years from now?','text',None),
    ('future_life','Your Future Self','What is one thing you absolutely want your future self to have achieved or experienced?','text',None),
    ('future_question','Your Future Self','If you could ask your future self one question, what would it be?','text',None),
    ('tone','Your Future Self','How would you like your future self to communicate with you?','single_choice',['Warm, compassionate, and encouraging','Honest, direct, and realistic','Motivational and challenging','Calm, logical, and thoughtful']),
    # Topics the future self should avoid. An empty list means "no restrictions".
    ('restricted_topics','Conversation Boundaries','Which topics would you prefer your future self to avoid discussing?','multiple_choice',['Health','Finances','Religion','Political views','Relationships','Family']),
]


def seed_data(conn):
    for code, name, description in [
        ('corporate','Corporate Me','A possible future staying on a corporate career path'),
        ('entrepreneur','Entrepreneur Me','A possible future building a business'),
        ('academic','Academic Me','A possible future pursuing study or research')]:
        conn.execute(text('''INSERT INTO public.dim_scenario(scenario_code,scenario_name,description)
                             VALUES (:code,:name,:description) ON CONFLICT (scenario_code) DO NOTHING'''),
                     {'code':code,'name':name,'description':description})
    questionnaire_id = conn.execute(text('''INSERT INTO public.dim_questionnaire
        (questionnaire_code,version,title,description) VALUES ('future-self',1,'Future Self Questionnaire',
        '21 questions for a possible future self')
        ON CONFLICT (questionnaire_code,version) DO UPDATE SET title = EXCLUDED.title
        RETURNING questionnaire_id''')).scalar_one()
    # On existing DB, earlier question_code values may already exist. Link only unassigned questions.
    for i,(code,cat,txt,kind,opts) in enumerate(DEFAULT_QUESTIONS,1):
        import json
        conn.execute(text('''INSERT INTO public.dim_question
            (questionnaire_id,question_code,category,question_text,response_type,options,display_order)
            VALUES (:qid,:code,:cat,:question,:kind,CAST(:opts AS jsonb),:pos)
            ON CONFLICT (question_code) DO UPDATE SET
                questionnaire_id = COALESCE(public.dim_question.questionnaire_id, EXCLUDED.questionnaire_id)'''),
            {'qid':questionnaire_id,'code':code,'cat':cat,'question':txt,'kind':kind,
             'opts':json.dumps(opts) if opts is not None else None,'pos':i})
    print(f'Seeded scenarios and questionnaire ({len(DEFAULT_QUESTIONS)} questions; existing questions kept).')

