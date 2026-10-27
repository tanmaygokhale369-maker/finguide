from app.schemas.common import ApiBaseModel


class HealthResponse(ApiBaseModel):
    status: str
    app_name: str
    environment: str


class ReadinessResponse(ApiBaseModel):
    status: str
    database: str
