from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Tuple
import numpy as np
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from . import models
from .models import ContentResourceResponse, ContentResource
from .database import SessionLocal, engine
from .personality_scoring import score_axis, reverse_response, cronbach_alpha, item_total_correlation


models.Base.metadata.create_all(bind=engine)

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

QUIZ_SCALE_K = 5

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


REVERSE_ITEMS = {"q_like_breaking_things": True}  # Example


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


@app.post("/recommendations", response_model=List[ContentResourceResponse])
async def get_recommendations(request: RecommendationRequest, db: Session = Depends(get_db)):
    scores = request.scores
    TOTAL_RECOMMENDATIONS = 5

    positive_axes = {axis: score for axis, score in scores.items() if score > 0}
    sorted_axes = sorted(positive_axes.items(), key=lambda item: item[1], reverse=True)

    if not sorted_axes:
        return []

    recommendations_per_axis = {}
    total_score_sum = sum(positive_axes.values())


    if total_score_sum == 0:

        if sorted_axes:
            items_per_axis = TOTAL_RECOMMENDATIONS // len(sorted_axes)
            for i, (axis, score) in enumerate(sorted_axes):
                if i == 0:
                    recommendations_per_axis[axis] = items_per_axis + (TOTAL_RECOMMENDATIONS % len(sorted_axes))
                else:
                    recommendations_per_axis[axis] = items_per_axis
        else:
            return []
    else:
        remaining_items = TOTAL_RECOMMENDATIONS
        for i, (axis, score) in enumerate(sorted_axes):
            if i == len(sorted_axes) - 1:
                num_items = remaining_items
            else:
                num_items = int(round(score / total_score_sum * TOTAL_RECOMMENDATIONS))

                num_items = min(num_items, remaining_items)

            recommendations_per_axis[axis] = num_items
            remaining_items -= num_items
            if remaining_items <= 0 and i < len(sorted_axes) - 1:
                for j in range(i + 1, len(sorted_axes)):
                    recommendations_per_axis[sorted_axes[j][0]] = 0
                break


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
    """
    Receives quiz answers, calculates scores, AND saves
    the answers to the database.
    """
    user_answers = submission.answers
    results = {}


    new_user = models.PersonalityUser()
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    db_responses = []
    for q_id, answer in user_answers.items():
        db_responses.append(
            models.PersonalityResponse(
                user_id=new_user.id,
                question_id=q_id,
                answer=answer
            )
        )

    db.add_all(db_responses)
    db.commit()

    for axis_name, mapping in AXES_MAP.items():
        score = score_axis(
            responses=user_answers,
            axis_map=mapping,
            scale_k=QUIZ_SCALE_K,
            reverse_items=REVERSE_ITEMS
        )
        results[axis_name] = score

    return QuizResults(scores=results, user_id=new_user.id)



def get_all_responses_for_axis(axis_name: str, db: Session) -> np.ndarray:
    print(f"Fetching REAL responses for axis: {axis_name}")

    try:
        item_ids = [q_id for q_id, w in AXES_MAP[axis_name]]
    except KeyError:
        return np.array([[]])  # Return empty matrix if axis_name is invalid

    if not item_ids:
        return np.array([[]])

    all_responses = db.query(models.PersonalityResponse).filter(
        models.PersonalityResponse.question_id.in_(item_ids)
    ).all()

    user_answers_map = {}
    for resp in all_responses:
        if resp.user_id not in user_answers_map:
            user_answers_map[resp.user_id] = {}
        user_answers_map[resp.user_id][resp.question_id] = resp.answer

    raw_matrix = []
    for user_id, answers in user_answers_map.items():
        if len(answers) == len(item_ids):
            row = [answers[q_id] for q_id in item_ids]
            raw_matrix.append(row)

    if not raw_matrix:
        return np.array([[]])

    processed_matrix = []
    for row in raw_matrix:
        processed_row = []
        for i, q_id in enumerate(item_ids):
            answer = row[i]
            if REVERSE_ITEMS.get(q_id, False):
                answer = reverse_response(answer, k=QUIZ_SCALE_K)
            processed_row.append(answer)
        processed_matrix.append(processed_row)

    return np.array(processed_matrix)


@app.get("/admin/stats/{axis_name}")
async def get_axis_reliability(axis_name: str, db: Session = Depends(get_db)):
    if axis_name not in AXES_MAP:
        raise HTTPException(status_code=404, detail="Axis not found")

    item_matrix = get_all_responses_for_axis(axis_name, db=db)

    if item_matrix.shape[0] < 2 or item_matrix.shape[1] < 2:
        return {
            "axis": axis_name,
            "error": "Not enough data (users or items) to calculate stats."
        }

    alpha = cronbach_alpha(item_matrix)
    item_correlations = item_total_correlation(item_matrix)

    item_ids = [q_id for q_id, w in AXES_MAP[axis_name]]

    return {
        "axis": axis_name,
        "n_users": item_matrix.shape[0],
        "n_items": item_matrix.shape[1],
        "cronbach_alpha": alpha,
        "item_total_correlations": dict(zip(item_ids, item_correlations))
    }

