from fastapi import FastAPI
import connections
from starlette.middleware.cors import CORSMiddleware
from dateutil.parser import parse
from datetime import timedelta
from starlette.templating import Jinja2Templates
from starlette.requests import Request

# Zbuildit a spustit pomoci:
# docker build . -t py_weekend
# docker run -p 5000:5000 -e PORT=5000 py_weekend

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

templates = Jinja2Templates(directory="templates")


@app.get("/search/{source}/{destination}/{date_from}/{date_to}/{passengers}")
def searcg(
    source: str, destination: str, date_from: str, date_to: str, passengers: int
):
    conns = []
    d_from = parse(date_from)
    d_to = parse(date_to)
    delta = d_to - d_from
    for i in range(delta.days + 1):
        new_conns = connections.find_connections(
            source,
            destination,
            departure_date=(d_from + timedelta(days=i)).strftime("%Y-%m-%d"),
        )
        conns += new_conns

    return {"journeys": conns}


@app.get("/search")
def search(request: Request):
    return templates.TemplateResponse("search_vue.html", {"request": request})


# @app.get("/combinations/{source}/{destination}/{date_from}/{date_to}")
# def combinations(source: str, destination: str, date_from: str, date_to: str):
