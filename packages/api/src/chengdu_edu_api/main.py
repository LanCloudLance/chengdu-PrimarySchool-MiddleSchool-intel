from fastapi import FastAPI

from chengdu_edu_api.routes import districts, jobs, policies, schools, sources

app = FastAPI(title="Chengdu Edu Intel API", version="0.1.0")

app.include_router(districts.router, prefix="/api")
app.include_router(schools.router, prefix="/api")
app.include_router(policies.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
