from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List
import numpy as np
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from . import models
from .models import ContentResourceResponse, ContentResource
from .database import SessionLocal, engine
from .personality_scoring import score_axis, reverse_response, cronbach_alpha, item_total_correlation
import os
import google.generativeai as genai

# Configuração do banco e do modelo
models.Base.metadata.create_all(bind=engine)

# Carrega a chave da API do Google (usada para o Gemini)
#TODO LEMBRAR DE CHECAR A USAGEM DE CADA MODELO
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    print("AVISO: GOOGLE_API_KEY não definida. O coach de carreira não funcionará.")
else:
    genai.configure(api_key=API_KEY)

app = FastAPI()

origins = [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração da escala do quiz (-1 a 1)
#TODO DAR UM CHECK PQ NAO ABRANGE EDGE CASES
QUIZ_SCALE_K = 5

# Mapeia cada eixo de carreira às perguntas relevantes e seus pesos
#TODO ADICIONAR MAIS CARREIRAS
#TODO RE-AVALIAR OS PESOS POIS NAO COMBRE EDGE CASES
AXES_MAP = {
    "WEB_DEV": [
        ("q_like_visuals", 1.0),
        ("q_like_user_logic", 1.0),
        ("q_like_deep_math", -0.5),
        ("q_like_puzzles", 0.5)
    ],
    "DATA_SCIENCE": [
        ("q_like_deep_math", 1.0),
        ("q_like_stats", 1.0),
        ("q_like_patterns", 1.0),
        ("q_like_visuals", 0.5)
    ],
    "CYBERSECURITY": [
        ("q_like_rules", 1.0),
        ("q_like_puzzles", 1.0),
        ("q_like_breaking_things", 1.0),
        ("q_like_visuals", -1.0)
    ]
}

# Algumas perguntas são invertidas na análise
REVERSE_ITEMS = {"q_like_breaking_things": True}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class QuizSubmission(BaseModel):
    answers: Dict[str, int] = Field(..., example={"q1": 4, "q2": 2, "q3": 5})


class QuizResults(BaseModel):
    scores: Dict[str, float]
    user_id: int


class RecommendationRequest(BaseModel):
    scores: Dict[str, float]


class CoachRequest(BaseModel):
    scores: Dict[str, float]
    message: str


class CoachResponse(BaseModel):
    reply: str


@app.post("/recommendations", response_model=List[ContentResourceResponse])
async def get_recommendations(request: RecommendationRequest, db: Session = Depends(get_db)):
    scores = request.scores
    TOTAL_RECOMMENDATIONS = 5

    # Filtra apenas os eixos com afinidade positiva
    positive_axes = {axis: score for axis, score in scores.items() if score > 0}
    sorted_axes = sorted(positive_axes.items(), key=lambda item: item[1], reverse=True)

    if not sorted_axes:
        return []

    # Distribui as recomendações proporcionalmente aos scores
    recommendations_per_axis = {}
    total_score_sum = sum(positive_axes.values())

    if total_score_sum == 0:
        items_per_axis = TOTAL_RECOMMENDATIONS // len(sorted_axes)
        remainder = TOTAL_RECOMMENDATIONS % len(sorted_axes)
        for i, (axis, _) in enumerate(sorted_axes):
            recommendations_per_axis[axis] = items_per_axis + (1 if i < remainder else 0)
    else:
        remaining = TOTAL_RECOMMENDATIONS
        for i, (axis, score) in enumerate(sorted_axes):
            if i == len(sorted_axes) - 1:
                num_items = remaining
            else:
                num_items = int(round(score / total_score_sum * TOTAL_RECOMMENDATIONS))
                num_items = max(1, min(num_items, remaining))
            recommendations_per_axis[axis] = num_items
            remaining -= num_items
            if remaining <= 0:
                break

    # Busca os recursos no banco
    all_recommendations = []
    for axis, num_items in recommendations_per_axis.items():
        if num_items > 0:
            resources = db.query(ContentResource).filter(
                ContentResource.career_axis == axis
            ).limit(num_items).all()
            all_recommendations.extend(resources)

    return all_recommendations


@app.post("/quiz/submit", response_model=QuizResults)
async def submit_quiz(submission: QuizSubmission, db: Session = Depends(get_db)):
    user_answers = submission.answers
    results = {}

    # Cria um novo usuário e salva as respostas
    new_user = models.PersonalityUser()
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    db_responses = []
    for q_id, answer in user_answers.items():
        db_responses.append(
            models.PersonalityResponse(user_id=new_user.id, question_id=q_id, answer=answer)
        )
    db.add_all(db_responses)
    db.commit()

    # Calcula os scores para cada eixo de carreira
    for axis_name, mapping in AXES_MAP.items():
        score = score_axis(
            responses=user_answers,
            axis_map=mapping,
            scale_k=QUIZ_SCALE_K,
            reverse_items=REVERSE_ITEMS
        )
        results[axis_name] = score

    return QuizResults(scores=results, user_id=new_user.id)


@app.post("/quiz/coach", response_model=CoachResponse)
async def chat_with_coach(request: CoachRequest):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Serviço de IA não configurado.")

    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao inicializar modelo de IA: {e}")

    # Formata os scores de forma legível para o modelo
    scores_str = "\n".join([
        f"- {axis.replace('_', ' ').title()}: {score:.2f}" 
        for axis, score in request.scores.items()
    ])

    # Monta o prompt com contexto e instruções claras
    prompt = f"""
    Você é um conselheiro de carreira em TI, simpático e direto ao ponto.
    Um usuário fez um quiz e obteve os seguintes scores (escala de -1 a 1):
    {scores_str}

    Ele pergunta: "{request.message}"

    Dê uma resposta útil, personalizada e em português do Brasil. Baseie-se nos scores:
    se ele tem alta afinidade com Web Dev, por exemplo, oriente nessa direção.
    Seja encorajador e prático.
    """

    try:
        response = await model.generate_content_async(prompt)
        return CoachResponse(reply=response.text)
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        raise HTTPException(status_code=500, detail="Não foi possível gerar uma resposta no momento.")


# Funções auxiliares para análise estatística (usadas no /admin/stats)
def get_all_responses_for_axis(axis_name: str, db: Session) -> np.ndarray:
    try:
        item_ids = [q_id for q_id, _ in AXES_MAP[axis_name]]
    except KeyError:
        return np.array([[]])

    if not item_ids:
        return np.array([[]])

    all_responses = db.query(models.PersonalityResponse).filter(
        models.PersonalityResponse.question_id.in_(item_ids)
    ).all()

    user_answers = {}
    for resp in all_responses:
        user_answers.setdefault(resp.user_id, {})[resp.question_id] = resp.answer

    raw_matrix = []
    for answers in user_answers.values():
        if len(answers) == len(item_ids):
            row = [answers[q_id] for q_id in item_ids]
            raw_matrix.append(row)

    if not raw_matrix:
        return np.array([[]])

    # Aplica inversão onde necessário
    processed = []
    for row in raw_matrix:
        new_row = []
        for i, q_id in enumerate(item_ids):
            val = row[i]
            if REVERSE_ITEMS.get(q_id):
                val = reverse_response(val, k=QUIZ_SCALE_K)
            new_row.append(val)
        processed.append(new_row)

    return np.array(processed)


@app.get("/admin/stats/{axis_name}")
async def get_axis_reliability(axis_name: str, db: Session = Depends(get_db)):
    if axis_name not in AXES_MAP:
        raise HTTPException(status_code=404, detail="Eixo não encontrado")

    item_matrix = get_all_responses_for_axis(axis_name, db)

    if item_matrix.shape[0] < 2 or item_matrix.shape[1] < 2:
        return {
            "axis": axis_name,
            "error": "Dados insuficientes para análise estatística."
        }

    alpha = cronbach_alpha(item_matrix)
    correlations = item_total_correlation(item_matrix)
    item_ids = [q_id for q_id, _ in AXES_MAP[axis_name]]

    return {
        "axis": axis_name,
        "n_users": item_matrix.shape[0],
        "n_items": item_matrix.shape[1],
        "cronbach_alpha": alpha,
        "item_total_correlations": dict(zip(item_ids, correlations))
    }
