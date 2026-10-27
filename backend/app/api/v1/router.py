"""
Aggregates all /api/v1 routers.

Future bricks add their routers here (e.g. profile, chat, transactions)
instead of registering them directly on the app in main.py. This keeps
main.py stable as the API surface grows.
"""

from fastapi import APIRouter

from app.api.v1 import auth, chat, evidence, feedback, health, holdings, market_research, news, privacy, profile, recommendations, spending, transactions, validation

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(evidence.router)
api_v1_router.include_router(feedback.router)
api_v1_router.include_router(privacy.router)
api_v1_router.include_router(health.router)
api_v1_router.include_router(profile.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(validation.router)
api_v1_router.include_router(transactions.router)
api_v1_router.include_router(spending.router)
api_v1_router.include_router(recommendations.router)
api_v1_router.include_router(market_research.router)
api_v1_router.include_router(news.router)
api_v1_router.include_router(holdings.router)
