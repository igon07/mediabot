from fastapi import FastAPI
import db



app = FastAPI()

@app.get("/")
def root():
    return {"message" : "API is running"}

@app.get("/tags")
def read_tags(limit: int = 20, offset: int = 0, category: str = None):
    rows = db.get_tags(limit=limit, offset=offset, category=category)
    return [{"id": r[0], "name": r[1], "count": r[2]} for r in rows]

