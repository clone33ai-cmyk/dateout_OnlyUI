from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from typing import List
from pathlib import Path
import uuid, hashlib, shutil
from datetime import datetime

app = FastAPI(title="DateOut Demo")
app.add_middleware(SessionMiddleware, secret_key="dateout-demo-secret-change-in-prod")

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

users:   dict = {}
posts:   dict = {}
matches: dict = {}

INTERESTS = [
    "Travel", "Music", "Sports", "Fitness", "Food & Wine",
    "Art", "Reading", "Gaming", "Outdoors", "Dancing", "Cooking", "Photography",
]

def short_id():
    return str(uuid.uuid4())[:8].upper()

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def current_user(request: Request):
    uid = request.session.get("user_id")
    return users.get(uid) if uid else None

async def save_photos(photos: List[UploadFile], user_id: str) -> List[str]:
    saved = []
    for photo in photos:
        if not photo.filename or not photo.content_type.startswith("image/"):
            continue
        ext = photo.filename.rsplit(".", 1)[-1].lower()
        fname = f"{user_id}_{short_id()}.{ext}"
        fpath = UPLOAD_DIR / fname
        with open(fpath, "wb") as f:
            f.write(await photo.read())
        saved.append(f"/static/uploads/{fname}")
    return saved

# ── Home ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, "user": current_user(request)
    })

# ── Register: choose role ─────────────────────────────────────────────────────
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# ── Register: Woman ───────────────────────────────────────────────────────────
@app.get("/register/woman", response_class=HTMLResponse)
async def reg_woman_page(request: Request):
    return templates.TemplateResponse("register_woman.html", {"request": request, "error": None})

@app.post("/register/woman")
async def reg_woman(
    request: Request,
    name:     str  = Form(...),
    email:    str  = Form(...),
    password: str  = Form(...),
    bio:      str  = Form(...),
    age:      int  = Form(...),
    photos: List[UploadFile] = File(...),
):
    if any(u["email"] == email for u in users.values()):
        return templates.TemplateResponse("register_woman.html", {
            "request": request, "error": "That email is already registered."
        })
    valid = [p for p in photos if p.filename and p.content_type.startswith("image/")]
    if not valid:
        return templates.TemplateResponse("register_woman.html", {
            "request": request, "error": "Please upload at least one photo."
        })
    uid = short_id()
    urls = await save_photos(valid, uid)
    users[uid] = {
        "id": uid, "role": "woman", "name": name, "email": email,
        "password": hash_pw(password), "bio": bio, "age": age,
        "photos": urls, "interests": [],
        "joined": datetime.now().strftime("%b %Y"),
    }
    request.session["user_id"] = uid
    return RedirectResponse("/woman", status_code=303)

# ── Register: Man ─────────────────────────────────────────────────────────────
@app.get("/register/man", response_class=HTMLResponse)
async def reg_man_page(request: Request):
    return templates.TemplateResponse("register_man.html", {
        "request": request, "error": None, "all_interests": INTERESTS
    })

@app.post("/register/man")
async def reg_man(
    request: Request,
    name:      str  = Form(...),
    email:     str  = Form(...),
    password:  str  = Form(...),
    bio:       str  = Form(...),
    age:       int  = Form(...),
    interests: List[str] = Form(default=[]),
    photos: List[UploadFile] = File(...),
):
    if any(u["email"] == email for u in users.values()):
        return templates.TemplateResponse("register_man.html", {
            "request": request, "error": "That email is already registered.",
            "all_interests": INTERESTS
        })
    valid = [p for p in photos if p.filename and p.content_type.startswith("image/")]
    if not valid:
        return templates.TemplateResponse("register_man.html", {
            "request": request, "error": "Please upload at least one photo.",
            "all_interests": INTERESTS
        })
    uid = short_id()
    urls = await save_photos(valid, uid)
    users[uid] = {
        "id": uid, "role": "man", "name": name, "email": email,
        "password": hash_pw(password), "bio": bio, "age": age,
        "photos": urls, "interests": interests,
        "joined": datetime.now().strftime("%b %Y"),
    }
    request.session["user_id"] = uid
    return RedirectResponse("/man", status_code=303)

# ── Login / Logout ────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = next(
        (u for u in users.values() if u["email"] == email and u["password"] == hash_pw(password)),
        None
    )
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "Invalid email or password."
        })
    request.session["user_id"] = user["id"]
    return RedirectResponse("/woman" if user["role"] == "woman" else "/man", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

# ── Woman dashboard ───────────────────────────────────────────────────────────
@app.get("/woman", response_class=HTMLResponse)
async def woman_dashboard(request: Request):
    user = current_user(request)
    if not user or user["role"] != "woman":
        return RedirectResponse("/login", status_code=303)
    my_posts = [p for p in posts.values() if p["user_id"] == user["id"]]
    return templates.TemplateResponse("woman.html", {
        "request": request, "user": user, "posts": my_posts
    })

@app.post("/woman/post")
async def create_post(
    request: Request,
    venue:      str = Form(...),
    date_idea:  str = Form(...),
    budget_min: int = Form(...),
    budget_max: int = Form(...),
):
    user = current_user(request)
    if not user or user["role"] != "woman":
        return RedirectResponse("/login", status_code=303)
    pid = short_id()
    posts[pid] = {
        "id": pid, "user_id": user["id"],
        "name": user["name"], "bio": user["bio"],
        "age": user["age"], "photos": user["photos"],
        "venue": venue, "date_idea": date_idea,
        "budget_min": budget_min, "budget_max": budget_max,
        "funded_by": None, "funded_by_user_id": None,
        "match_id": None,
        "created_at": datetime.now().strftime("%b %d, %Y"),
    }
    return RedirectResponse(f"/woman/post/{pid}", status_code=303)

@app.get("/woman/post/{post_id}", response_class=HTMLResponse)
async def post_detail(request: Request, post_id: str):
    post = posts.get(post_id)
    if not post:
        raise HTTPException(404)
    match = matches.get(post["match_id"]) if post["match_id"] else None
    man_profile = users.get(match["man_user_id"]) if match else None
    return templates.TemplateResponse("post_detail.html", {
        "request": request, "user": current_user(request),
        "post": post, "match": match, "man_profile": man_profile,
    })

# ── Man browse ────────────────────────────────────────────────────────────────
@app.get("/man", response_class=HTMLResponse)
async def man_browse(request: Request):
    user = current_user(request)
    if not user or user["role"] != "man":
        return RedirectResponse("/login", status_code=303)
    available = [p for p in posts.values() if not p["funded_by"]]
    return templates.TemplateResponse("man.html", {
        "request": request, "user": user, "posts": available
    })

@app.get("/man/fund/{post_id}", response_class=HTMLResponse)
async def fund_page(request: Request, post_id: str):
    user = current_user(request)
    if not user or user["role"] != "man":
        return RedirectResponse("/login", status_code=303)
    post = posts.get(post_id)
    if not post:
        raise HTTPException(404)
    if post["funded_by"]:
        raise HTTPException(400, "Already funded")
    return templates.TemplateResponse("fund.html", {
        "request": request, "user": user, "post": post,
        "woman_profile": users.get(post["user_id"]),
    })

@app.post("/man/fund/{post_id}")
async def fund_post(request: Request, post_id: str, budget: int = Form(...)):
    user = current_user(request)
    if not user or user["role"] != "man":
        return RedirectResponse("/login", status_code=303)
    post = posts.get(post_id)
    if not post or post["funded_by"]:
        raise HTTPException(400, "Not available")
    mid = short_id()
    matches[mid] = {
        "id": mid, "post_id": post_id,
        "woman_user_id": post["user_id"],
        "man_user_id": user["id"],
        "venue": post["venue"], "date_idea": post["date_idea"],
        "budget": budget,
        "matched_at": datetime.now().strftime("%b %d, %Y at %I:%M %p"),
    }
    posts[post_id]["funded_by"] = user["name"]
    posts[post_id]["funded_by_user_id"] = user["id"]
    posts[post_id]["match_id"] = mid
    return RedirectResponse(f"/match/{mid}", status_code=303)

# ── Match ─────────────────────────────────────────────────────────────────────
@app.get("/match/{match_id}", response_class=HTMLResponse)
async def match_view(request: Request, match_id: str):
    match = matches.get(match_id)
    if not match:
        raise HTTPException(404)
    return templates.TemplateResponse("match.html", {
        "request": request, "user": current_user(request),
        "match": match,
        "woman": users.get(match["woman_user_id"]),
        "man":   users.get(match["man_user_id"]),
    })

# ── Admin ─────────────────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "users":   list(users.values()),
        "posts":   list(posts.values()),
        "matches": list(matches.values()),
    })
