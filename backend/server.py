from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import httpx
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from supabase import create_client, Client

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Supabase client for auth verification
supabase_url = os.environ.get('SUPABASE_URL')
supabase_service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
supabase_client: Client = create_client(supabase_url, supabase_service_key)

# Gemini API key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== PYDANTIC MODELS ====================

class ProfileCreate(BaseModel):
    full_name: Optional[str] = None

class StartupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    stage: Optional[str] = "idea"
    website: Optional[str] = None

class StartupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    stage: Optional[str] = None
    website: Optional[str] = None

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "todo"
    priority: Optional[str] = "medium"
    assigned_to: Optional[str] = None
    milestone_id: Optional[str] = None
    due_date: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    milestone_id: Optional[str] = None
    due_date: Optional[str] = None

class MilestoneCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_date: Optional[str] = None

class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[str] = None
    status: Optional[str] = None

class FeedbackCreate(BaseModel):
    title: str
    content: Optional[str] = None
    category: Optional[str] = "product"
    rating: Optional[int] = 3
    source: Optional[str] = "internal"

class AIInsightRequest(BaseModel):
    startup_id: str
    prompt_type: Optional[str] = "general"

class PitchRequest(BaseModel):
    startup_id: str

class SubscriptionUpdate(BaseModel):
    plan: str

class MemberRoleUpdate(BaseModel):
    role: str

class TaskStatusUpdate(BaseModel):
    status: str

# Finance Models
class IncomeCreate(BaseModel):
    title: str
    amount: float
    category: Optional[str] = "revenue"  # revenue, investment, grant, other
    date: Optional[str] = None
    notes: Optional[str] = None

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: Optional[str] = "operations"  # salary, marketing, operations, infrastructure, other
    date: Optional[str] = None
    notes: Optional[str] = None

class InvestmentCreate(BaseModel):
    investor_name: str
    amount: float
    equity_percentage: Optional[float] = 0
    investment_type: Optional[str] = "seed"  # pre-seed, seed, series-a, series-b, angel, other
    date: Optional[str] = None
    notes: Optional[str] = None

class InvestorInviteCreate(BaseModel):
    email: str
    name: str

class JoinStartupRequest(BaseModel):
    invite_code: str

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

# ==================== AUTH DEPENDENCY ====================

async def get_current_user(request: Request):
    auth_header = request.headers.get('authorization', '')
    if not auth_header.startswith('Bearer '):
        logger.warning("Missing or invalid Authorization header format")
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.split(' ')[1]
    if not token or token == 'undefined' or token == 'null':
        logger.warning(f"Invalid token value: {token[:20] if token else 'empty'}...")
        raise HTTPException(status_code=401, detail="No valid token provided")
    try:
        user_response = supabase_client.auth.get_user(token)
        if not user_response or not user_response.user:
            logger.error("Supabase returned no user for token")
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        logger.info(f"User authenticated: {user_response.user.email}")
        return user_response.user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth error for token prefix {token[:30]}...: {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "StartupOps API is running"}

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/signup")
async def signup_user(body: SignupRequest):
    """Create user with auto-confirm so they can start immediately."""
    try:
        user_response = supabase_client.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True,
            "user_metadata": {"full_name": body.full_name or body.email.split("@")[0]},
        })
        return {"message": "Account created", "user_id": user_response.user.id}
    except Exception as e:
        error_msg = str(e)
        if "already been registered" in error_msg or "already exists" in error_msg:
            raise HTTPException(status_code=409, detail="An account with this email already exists. Please sign in.")
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=400, detail="Failed to create account")

@api_router.post("/auth/verify")
async def verify_and_sync_profile(body: ProfileCreate, user=Depends(get_current_user)):
    existing = await db.profiles.find_one({"id": user.id}, {"_id": 0})
    if existing:
        return existing
    profile = {
        "id": user.id,
        "email": user.email,
        "full_name": body.full_name or user.user_metadata.get("full_name", "") or user.user_metadata.get("name", "") or user.email.split("@")[0],
        "avatar_url": user.user_metadata.get("avatar_url", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.profiles.insert_one(profile)
    return {k: v for k, v in profile.items() if k != "_id"}

@api_router.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    profile = await db.profiles.find_one({"id": user.id}, {"_id": 0})
    if not profile:
        profile = {
            "id": user.id,
            "email": user.email,
            "full_name": user.user_metadata.get("full_name", "") or user.user_metadata.get("name", "") or user.email.split("@")[0],
            "avatar_url": user.user_metadata.get("avatar_url", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.profiles.insert_one(profile)
        return {k: v for k, v in profile.items() if k != "_id"}
    return profile

@api_router.put("/auth/profile")
async def update_profile(body: ProfileCreate, user=Depends(get_current_user)):
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.full_name:
        updates["full_name"] = body.full_name
    await db.profiles.update_one({"id": user.id}, {"$set": updates})
    profile = await db.profiles.find_one({"id": user.id}, {"_id": 0})
    return profile

# ==================== STARTUP ROUTES ====================

@api_router.post("/startups")
async def create_startup(body: StartupCreate, user=Depends(get_current_user)):
    invite_code = str(uuid.uuid4())[:8].upper()
    startup = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "description": body.description or "",
        "industry": body.industry or "",
        "stage": body.stage or "idea",
        "website": body.website or "",
        "founder_id": user.id,
        "invite_code": invite_code,
        "subscription_plan": "free",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.startups.insert_one(startup)
    member = {
        "id": str(uuid.uuid4()),
        "startup_id": startup["id"],
        "user_id": user.id,
        "role": "founder",
        "joined_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.startup_members.insert_one(member)
    return {k: v for k, v in startup.items() if k != "_id"}

@api_router.get("/startups")
async def get_user_startups(user=Depends(get_current_user)):
    memberships = await db.startup_members.find({"user_id": user.id}, {"_id": 0}).to_list(100)
    startup_ids = [m["startup_id"] for m in memberships]
    startups = await db.startups.find({"id": {"$in": startup_ids}}, {"_id": 0}).to_list(100)
    for s in startups:
        membership = next((m for m in memberships if m["startup_id"] == s["id"]), None)
        s["user_role"] = membership["role"] if membership else "member"
    return startups

@api_router.get("/startups/{startup_id}")
async def get_startup(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this startup")
    startup = await db.startups.find_one({"id": startup_id}, {"_id": 0})
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    startup["user_role"] = member["role"]
    return startup

@api_router.put("/startups/{startup_id}")
async def update_startup(startup_id: str, body: StartupUpdate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id}, {"_id": 0})
    if not member or member["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can update startup")
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["name", "description", "industry", "stage", "website"]:
        val = getattr(body, field, None)
        if val is not None:
            updates[field] = val
    await db.startups.update_one({"id": startup_id}, {"$set": updates})
    startup = await db.startups.find_one({"id": startup_id}, {"_id": 0})
    return startup

@api_router.post("/startups/join")
async def join_startup(body: JoinStartupRequest, user=Depends(get_current_user)):
    startup = await db.startups.find_one({"invite_code": body.invite_code}, {"_id": 0})
    if not startup:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    existing = await db.startup_members.find_one({"startup_id": startup["id"], "user_id": user.id})
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    member_count = await db.startup_members.count_documents({"startup_id": startup["id"]})
    plan = startup.get("subscription_plan", "free")
    max_members = 5 if plan == "free" else 999
    if member_count >= max_members:
        raise HTTPException(status_code=400, detail=f"Team limit reached for {plan} plan")
    member = {
        "id": str(uuid.uuid4()),
        "startup_id": startup["id"],
        "user_id": user.id,
        "role": "member",
        "joined_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.startup_members.insert_one(member)
    return {k: v for k, v in startup.items() if k != "_id"}

# ==================== TASK ROUTES ====================

@api_router.post("/startups/{startup_id}/tasks")
async def create_task(startup_id: str, body: TaskCreate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    task = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "title": body.title,
        "description": body.description or "",
        "status": body.status or "todo",
        "priority": body.priority or "medium",
        "assigned_to": body.assigned_to,
        "created_by": user.id,
        "milestone_id": body.milestone_id,
        "due_date": body.due_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tasks.insert_one(task)
    return {k: v for k, v in task.items() if k != "_id"}

@api_router.get("/startups/{startup_id}/tasks")
async def get_tasks(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    tasks = await db.tasks.find({"startup_id": startup_id}, {"_id": 0}).to_list(1000)
    return tasks

@api_router.put("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate, user=Depends(get_current_user)):
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    member = await db.startup_members.find_one({"startup_id": task["startup_id"], "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["title", "description", "status", "priority", "assigned_to", "milestone_id", "due_date"]:
        val = getattr(body, field, None)
        if val is not None:
            updates[field] = val
    await db.tasks.update_one({"id": task_id}, {"$set": updates})
    updated = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return updated

@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user=Depends(get_current_user)):
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    member = await db.startup_members.find_one({"startup_id": task["startup_id"], "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    await db.tasks.delete_one({"id": task_id})
    return {"success": True}

@api_router.patch("/tasks/{task_id}/status")
async def update_task_status(task_id: str, body: TaskStatusUpdate, user=Depends(get_current_user)):
    """Update only the status of a task - allows assigned members to update status"""
    logger.info(f"Updating task status: task_id={task_id}, new_status={body.status}, user_id={user.id}")
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        logger.error(f"Task not found: task_id={task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    member = await db.startup_members.find_one({"startup_id": task["startup_id"], "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    
    # Check if user is assigned to the task OR is founder/manager
    is_assigned = task.get("assigned_to") == user.id
    is_manager_or_founder = member["role"] in ["founder", "manager"]
    
    if not is_assigned and not is_manager_or_founder:
        raise HTTPException(status_code=403, detail="You can only update status of tasks assigned to you")
    
    valid_statuses = ["todo", "in_progress", "review", "done"]
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    await db.tasks.update_one(
        {"id": task_id}, 
        {"$set": {"status": body.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    logger.info(f"Task status updated successfully: task_id={task_id}")
    return updated

# ==================== MILESTONE ROUTES ====================

@api_router.post("/startups/{startup_id}/milestones")
async def create_milestone(startup_id: str, body: MilestoneCreate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    milestone = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "title": body.title,
        "description": body.description or "",
        "target_date": body.target_date,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.milestones.insert_one(milestone)
    return {k: v for k, v in milestone.items() if k != "_id"}

@api_router.get("/startups/{startup_id}/milestones")
async def get_milestones(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    milestones = await db.milestones.find({"startup_id": startup_id}, {"_id": 0}).to_list(100)
    for m in milestones:
        tasks = await db.tasks.find({"milestone_id": m["id"]}, {"_id": 0}).to_list(100)
        total = len(tasks)
        done = len([t for t in tasks if t.get("status") == "done"])
        m["progress"] = int((done / total) * 100) if total > 0 else 0
        m["task_count"] = total
        m["tasks_done"] = done
    return milestones

@api_router.put("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, body: MilestoneUpdate, user=Depends(get_current_user)):
    milestone = await db.milestones.find_one({"id": milestone_id}, {"_id": 0})
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    member = await db.startup_members.find_one({"startup_id": milestone["startup_id"], "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["title", "description", "target_date", "status"]:
        val = getattr(body, field, None)
        if val is not None:
            updates[field] = val
    await db.milestones.update_one({"id": milestone_id}, {"$set": updates})
    updated = await db.milestones.find_one({"id": milestone_id}, {"_id": 0})
    return updated

@api_router.delete("/milestones/{milestone_id}")
async def delete_milestone(milestone_id: str, user=Depends(get_current_user)):
    milestone = await db.milestones.find_one({"id": milestone_id}, {"_id": 0})
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    member = await db.startup_members.find_one({"startup_id": milestone["startup_id"], "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    await db.milestones.delete_one({"id": milestone_id})
    await db.tasks.update_many({"milestone_id": milestone_id}, {"$set": {"milestone_id": None}})
    return {"success": True}

# ==================== FEEDBACK ROUTES ====================

@api_router.post("/startups/{startup_id}/feedback")
async def create_feedback(startup_id: str, body: FeedbackCreate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    feedback = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "title": body.title,
        "content": body.content or "",
        "category": body.category or "product",
        "rating": body.rating or 3,
        "submitted_by": user.id,
        "source": body.source or "internal",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.feedback.insert_one(feedback)
    return {k: v for k, v in feedback.items() if k != "_id"}

@api_router.get("/startups/{startup_id}/feedback")
async def get_feedback(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    feedbacks = await db.feedback.find({"startup_id": startup_id}, {"_id": 0}).to_list(500)
    return feedbacks

# ==================== ANALYTICS ROUTES ====================

@api_router.get("/startups/{startup_id}/analytics")
async def get_analytics(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    tasks = await db.tasks.find({"startup_id": startup_id}, {"_id": 0}).to_list(1000)
    milestones = await db.milestones.find({"startup_id": startup_id}, {"_id": 0}).to_list(100)
    feedbacks = await db.feedback.find({"startup_id": startup_id}, {"_id": 0}).to_list(500)
    members = await db.startup_members.find({"startup_id": startup_id}, {"_id": 0}).to_list(100)

    task_stats = {"todo": 0, "in_progress": 0, "review": 0, "done": 0}
    priority_stats = {"low": 0, "medium": 0, "high": 0, "urgent": 0}
    for t in tasks:
        status = t.get("status", "todo")
        if status in task_stats:
            task_stats[status] += 1
        prio = t.get("priority", "medium")
        if prio in priority_stats:
            priority_stats[prio] += 1

    milestone_stats = {"pending": 0, "in_progress": 0, "completed": 0}
    for m in milestones:
        ms = m.get("status", "pending")
        if ms in milestone_stats:
            milestone_stats[ms] += 1

    feedback_by_category = {}
    avg_rating = 0
    if feedbacks:
        for f in feedbacks:
            cat = f.get("category", "other")
            feedback_by_category[cat] = feedback_by_category.get(cat, 0) + 1
        avg_rating = round(sum(f.get("rating", 0) for f in feedbacks) / len(feedbacks), 1)

    total_tasks = len(tasks)
    completed_tasks = task_stats["done"]
    completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": completion_rate,
        "task_stats": task_stats,
        "priority_stats": priority_stats,
        "total_milestones": len(milestones),
        "milestone_stats": milestone_stats,
        "total_feedback": len(feedbacks),
        "feedback_by_category": feedback_by_category,
        "avg_rating": avg_rating,
        "team_size": len(members),
    }

# ==================== AI ROUTES (GEMINI) ====================

@api_router.post("/ai/insights")
async def get_ai_insights(body: AIInsightRequest, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": body.startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    startup = await db.startups.find_one({"id": body.startup_id}, {"_id": 0})
    tasks = await db.tasks.find({"startup_id": body.startup_id}, {"_id": 0}).to_list(100)
    milestones = await db.milestones.find({"startup_id": body.startup_id}, {"_id": 0}).to_list(50)
    feedbacks = await db.feedback.find({"startup_id": body.startup_id}, {"_id": 0}).to_list(50)

    task_summary = f"Total tasks: {len(tasks)}, Done: {len([t for t in tasks if t.get('status')=='done'])}, In Progress: {len([t for t in tasks if t.get('status')=='in_progress'])}"
    milestone_summary = f"Total milestones: {len(milestones)}, Completed: {len([m for m in milestones if m.get('status')=='completed'])}"
    feedback_summary = f"Total feedback: {len(feedbacks)}"
    if feedbacks:
        avg = round(sum(f.get("rating", 0) for f in feedbacks) / len(feedbacks), 1)
        feedback_summary += f", Average rating: {avg}/5"

    prompt_map = {
        "general": f"Analyze this startup's progress and provide 3-5 actionable insights:\nStartup: {startup.get('name', 'Unknown')} ({startup.get('industry', 'Unknown')} - {startup.get('stage', 'idea')} stage)\n{task_summary}\n{milestone_summary}\n{feedback_summary}\nProvide specific, actionable recommendations for improvement.",
        "tasks": f"Suggest 5 strategic tasks for this startup:\nStartup: {startup.get('name', 'Unknown')} in {startup.get('industry', 'Unknown')} at {startup.get('stage', 'idea')} stage.\nCurrent tasks: {task_summary}\nSuggest tasks with title, description, and priority level.",
        "milestones": f"Suggest 3 key milestones for this startup:\nStartup: {startup.get('name', 'Unknown')} in {startup.get('industry', 'Unknown')} at {startup.get('stage', 'idea')} stage.\nCurrent milestones: {milestone_summary}\nSuggest milestones with clear deliverables and target timeframes.",
        "growth": f"Provide a growth strategy analysis:\nStartup: {startup.get('name', 'Unknown')} in {startup.get('industry', 'Unknown')} at {startup.get('stage', 'idea')} stage.\n{task_summary}\n{milestone_summary}\n{feedback_summary}\nSuggest growth strategies, metrics to track, and potential challenges."
    }
    prompt = prompt_map.get(body.prompt_type, prompt_map["general"])

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction="You are a startup advisor AI. Provide concise, actionable insights for early-stage founders. Format your response with clear sections using markdown. Be specific and practical."
        )
        response = model.generate_content(prompt)
        return {"insights": response.text, "prompt_type": body.prompt_type}
    except Exception as e:
        logger.error(f"AI insights error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

@api_router.post("/ai/pitch")
async def generate_pitch(body: PitchRequest, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": body.startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    startup = await db.startups.find_one({"id": body.startup_id}, {"_id": 0})
    tasks = await db.tasks.find({"startup_id": body.startup_id}, {"_id": 0}).to_list(100)
    milestones = await db.milestones.find({"startup_id": body.startup_id}, {"_id": 0}).to_list(50)
    feedbacks = await db.feedback.find({"startup_id": body.startup_id}, {"_id": 0}).to_list(50)
    members = await db.startup_members.find({"startup_id": body.startup_id}, {"_id": 0}).to_list(50)

    completed_tasks = len([t for t in tasks if t.get("status") == "done"])
    completed_milestones = len([m for m in milestones if m.get("status") == "completed"])
    avg_rating = round(sum(f.get("rating", 0) for f in feedbacks) / len(feedbacks), 1) if feedbacks else 0

    prompt = f"""Generate a compelling investor pitch outline for this startup:

Startup: {startup.get('name', 'Unknown')}
Industry: {startup.get('industry', 'Unknown')}
Stage: {startup.get('stage', 'idea')}
Description: {startup.get('description', 'No description')}
Website: {startup.get('website', 'N/A')}

Traction:
- Team size: {len(members)}
- Tasks completed: {completed_tasks}/{len(tasks)}
- Milestones achieved: {completed_milestones}/{len(milestones)}
- Average feedback rating: {avg_rating}/5

Generate a structured pitch with these sections:
1. **Problem Statement** - The problem being solved
2. **Solution** - How the startup solves it
3. **Market Opportunity** - TAM/SAM/SOM estimates
4. **Traction & Metrics** - Current progress and KPIs
5. **Business Model** - Revenue strategy
6. **Team** - Why this team can execute
7. **Roadmap** - Future milestones and vision
8. **The Ask** - What the startup needs from investors

Make it compelling, data-driven where possible, and suitable for a 5-minute pitch."""

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction="You are an expert startup pitch consultant. Create compelling, professional investor pitch outlines. Use markdown formatting with clear sections."
        )
        response = model.generate_content(prompt)
        return {"pitch": response.text, "startup_name": startup.get("name", "")}
    except Exception as e:
        logger.error(f"Pitch generation error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

# ==================== TEAM ROUTES ====================

@api_router.get("/startups/{startup_id}/members")
async def get_members(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    members = await db.startup_members.find({"startup_id": startup_id}, {"_id": 0}).to_list(100)
    result = []
    for m in members:
        profile = await db.profiles.find_one({"id": m["user_id"]}, {"_id": 0})
        result.append({
            "id": m["id"],
            "user_id": m["user_id"],
            "role": m["role"],
            "joined_at": m["joined_at"],
            "email": profile.get("email", "") if profile else "",
            "full_name": profile.get("full_name", "") if profile else "",
            "avatar_url": profile.get("avatar_url", "") if profile else "",
        })
    return result

@api_router.delete("/startups/{startup_id}/members/{user_id}")
async def remove_member(startup_id: str, user_id: str, user=Depends(get_current_user)):
    requester = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id}, {"_id": 0})
    if not requester or requester["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can remove members")
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    await db.startup_members.delete_one({"startup_id": startup_id, "user_id": user_id})
    return {"success": True}

@api_router.put("/startups/{startup_id}/members/{user_id}/role")
async def update_member_role(startup_id: str, user_id: str, body: MemberRoleUpdate, user=Depends(get_current_user)):
    logger.info(f"Updating member role: startup_id={startup_id}, target_user_id={user_id}, new_role={body.role}, requester_id={user.id}")
    requester = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id}, {"_id": 0})
    if not requester or requester["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can change roles")
    
    target_member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user_id}, {"_id": 0})
    logger.info(f"Target member lookup result: {target_member}")
    if not target_member:
        logger.error(f"Member not found: startup_id={startup_id}, user_id={user_id}")
        raise HTTPException(status_code=404, detail="Member not found")
    
    if target_member["role"] == "founder":
        raise HTTPException(status_code=400, detail="Cannot change founder role")
    
    if body.role not in ["manager", "member", "investor"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'manager', 'member', or 'investor'")
    
    await db.startup_members.update_one(
        {"startup_id": startup_id, "user_id": user_id},
        {"$set": {"role": body.role}}
    )
    logger.info(f"Member role updated successfully: user_id={user_id}, new_role={body.role}")
    return {"success": True, "role": body.role}

@api_router.get("/startups/{startup_id}/invite-code")
async def get_invite_code(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id}, {"_id": 0})
    if not member or member["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can view invite code")
    startup = await db.startups.find_one({"id": startup_id}, {"_id": 0})
    return {"invite_code": startup.get("invite_code", "")}

@api_router.post("/startups/{startup_id}/regenerate-invite")
async def regenerate_invite(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id}, {"_id": 0})
    if not member or member["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can regenerate invite code")
    new_code = str(uuid.uuid4())[:8].upper()
    await db.startups.update_one({"id": startup_id}, {"$set": {"invite_code": new_code}})
    return {"invite_code": new_code}

# ==================== SUBSCRIPTION ROUTES (MOCK) ====================

@api_router.get("/startups/{startup_id}/subscription")
async def get_subscription(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    sub = await db.subscriptions.find_one({"startup_id": startup_id}, {"_id": 0})
    if not sub:
        sub = {
            "id": str(uuid.uuid4()),
            "startup_id": startup_id,
            "plan": "free",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.subscriptions.insert_one(sub)
        return {k: v for k, v in sub.items() if k != "_id"}
    return sub

@api_router.post("/startups/{startup_id}/subscription")
async def update_subscription(startup_id: str, body: SubscriptionUpdate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id}, {"_id": 0})
    if not member or member["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can manage subscription")
    existing = await db.subscriptions.find_one({"startup_id": startup_id})
    if existing:
        await db.subscriptions.update_one(
            {"startup_id": startup_id},
            {"$set": {"plan": body.plan, "status": "active", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        sub = {
            "id": str(uuid.uuid4()),
            "startup_id": startup_id,
            "plan": body.plan,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.subscriptions.insert_one(sub)
    await db.startups.update_one({"id": startup_id}, {"$set": {"subscription_plan": body.plan}})
    sub = await db.subscriptions.find_one({"startup_id": startup_id}, {"_id": 0})
    return sub

# ==================== FINANCE ROUTES ====================

@api_router.post("/startups/{startup_id}/finance/income")
async def create_income(startup_id: str, body: IncomeCreate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member or member["role"] not in ["founder", "manager"]:
        raise HTTPException(status_code=403, detail="Only founders and managers can add income")
    income = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "title": body.title,
        "amount": body.amount,
        "category": body.category or "revenue",
        "date": body.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "notes": body.notes or "",
        "created_by": user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.income.insert_one(income)
    return {k: v for k, v in income.items() if k != "_id"}

@api_router.get("/startups/{startup_id}/finance/income")
async def get_income(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    income = await db.income.find({"startup_id": startup_id}, {"_id": 0}).sort("date", -1).to_list(500)
    return income

@api_router.delete("/startups/{startup_id}/finance/income/{income_id}")
async def delete_income(startup_id: str, income_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member or member["role"] not in ["founder", "manager"]:
        raise HTTPException(status_code=403, detail="Only founders and managers can delete income")
    await db.income.delete_one({"id": income_id, "startup_id": startup_id})
    return {"success": True}

@api_router.post("/startups/{startup_id}/finance/expenses")
async def create_expense(startup_id: str, body: ExpenseCreate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member or member["role"] not in ["founder", "manager"]:
        raise HTTPException(status_code=403, detail="Only founders and managers can add expenses")
    expense = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "title": body.title,
        "amount": body.amount,
        "category": body.category or "operations",
        "date": body.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "notes": body.notes or "",
        "created_by": user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.expenses.insert_one(expense)
    return {k: v for k, v in expense.items() if k != "_id"}

@api_router.get("/startups/{startup_id}/finance/expenses")
async def get_expenses(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    expenses = await db.expenses.find({"startup_id": startup_id}, {"_id": 0}).sort("date", -1).to_list(500)
    return expenses

@api_router.delete("/startups/{startup_id}/finance/expenses/{expense_id}")
async def delete_expense(startup_id: str, expense_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member or member["role"] not in ["founder", "manager"]:
        raise HTTPException(status_code=403, detail="Only founders and managers can delete expenses")
    await db.expenses.delete_one({"id": expense_id, "startup_id": startup_id})
    return {"success": True}

@api_router.post("/startups/{startup_id}/finance/investments")
async def create_investment(startup_id: str, body: InvestmentCreate, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member or member["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can add investments")
    investment = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "investor_name": body.investor_name,
        "amount": body.amount,
        "equity_percentage": body.equity_percentage or 0,
        "investment_type": body.investment_type or "seed",
        "date": body.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "notes": body.notes or "",
        "created_by": user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.investments.insert_one(investment)
    return {k: v for k, v in investment.items() if k != "_id"}

@api_router.get("/startups/{startup_id}/finance/investments")
async def get_investments(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    investments = await db.investments.find({"startup_id": startup_id}, {"_id": 0}).sort("date", -1).to_list(100)
    return investments

@api_router.delete("/startups/{startup_id}/finance/investments/{investment_id}")
async def delete_investment(startup_id: str, investment_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member or member["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can delete investments")
    await db.investments.delete_one({"id": investment_id, "startup_id": startup_id})
    return {"success": True}

@api_router.get("/startups/{startup_id}/finance/summary")
async def get_finance_summary(startup_id: str, user=Depends(get_current_user)):
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    
    income = await db.income.find({"startup_id": startup_id}, {"_id": 0}).to_list(500)
    expenses = await db.expenses.find({"startup_id": startup_id}, {"_id": 0}).to_list(500)
    investments = await db.investments.find({"startup_id": startup_id}, {"_id": 0}).to_list(100)
    
    total_income = sum(i.get("amount", 0) for i in income)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    total_investments = sum(inv.get("amount", 0) for inv in investments)
    total_equity_given = sum(inv.get("equity_percentage", 0) for inv in investments)
    
    # Monthly breakdown (last 6 months)
    from collections import defaultdict
    monthly_income = defaultdict(float)
    monthly_expenses = defaultdict(float)
    
    for i in income:
        month = i.get("date", "")[:7]  # YYYY-MM
        if month:
            monthly_income[month] += i.get("amount", 0)
    
    for e in expenses:
        month = e.get("date", "")[:7]
        if month:
            monthly_expenses[month] += e.get("amount", 0)
    
    # Category breakdown
    income_by_category = defaultdict(float)
    expenses_by_category = defaultdict(float)
    
    for i in income:
        income_by_category[i.get("category", "other")] += i.get("amount", 0)
    
    for e in expenses:
        expenses_by_category[e.get("category", "other")] += e.get("amount", 0)
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_investments": total_investments,
        "total_equity_given": total_equity_given,
        "net_balance": total_income + total_investments - total_expenses,
        "runway_months": round((total_income + total_investments - total_expenses) / max(total_expenses / max(len(set(e.get("date", "")[:7] for e in expenses)), 1), 1), 1) if total_expenses > 0 else 0,
        "monthly_income": dict(monthly_income),
        "monthly_expenses": dict(monthly_expenses),
        "income_by_category": dict(income_by_category),
        "expenses_by_category": dict(expenses_by_category),
        "investment_count": len(investments),
    }

# ==================== INVESTOR ROUTES ====================

@api_router.post("/startups/{startup_id}/investors/invite")
async def invite_investor(startup_id: str, body: InvestorInviteCreate, user=Depends(get_current_user)):
    """Founder invites an investor by email"""
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member or member["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can invite investors")
    
    # Create investor invite record
    invite = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "email": body.email.lower(),
        "name": body.name,
        "invite_code": str(uuid.uuid4())[:8].upper(),
        "status": "pending",
        "created_by": user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.investor_invites.insert_one(invite)
    return {k: v for k, v in invite.items() if k != "_id"}

@api_router.get("/startups/{startup_id}/investors")
async def get_investors(startup_id: str, user=Depends(get_current_user)):
    """Get all investors for a startup"""
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    
    # Get investor members
    investors = await db.startup_members.find({"startup_id": startup_id, "role": "investor"}, {"_id": 0}).to_list(100)
    result = []
    for inv in investors:
        profile = await db.profiles.find_one({"id": inv["user_id"]}, {"_id": 0})
        result.append({
            "id": inv["id"],
            "user_id": inv["user_id"],
            "role": "investor",
            "joined_at": inv.get("joined_at", ""),
            "email": profile.get("email", "") if profile else "",
            "full_name": profile.get("full_name", "") if profile else "",
        })
    
    # Also get pending invites
    pending = await db.investor_invites.find({"startup_id": startup_id, "status": "pending"}, {"_id": 0}).to_list(100)
    
    return {"investors": result, "pending_invites": pending}

@api_router.post("/investors/join")
async def join_as_investor(body: JoinStartupRequest, user=Depends(get_current_user)):
    """Investor joins using invite code"""
    invite = await db.investor_invites.find_one({"invite_code": body.invite_code.upper(), "status": "pending"})
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    
    startup_id = invite["startup_id"]
    
    # Check if already a member
    existing = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if existing:
        raise HTTPException(status_code=400, detail="Already a member of this startup")
    
    # Add as investor member
    membership = {
        "id": str(uuid.uuid4()),
        "startup_id": startup_id,
        "user_id": user.id,
        "role": "investor",
        "joined_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.startup_members.insert_one(membership)
    
    # Update invite status
    await db.investor_invites.update_one(
        {"id": invite["id"]},
        {"$set": {"status": "accepted", "accepted_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    startup = await db.startups.find_one({"id": startup_id}, {"_id": 0})
    return {"message": "Joined as investor", "startup": startup}

@api_router.delete("/startups/{startup_id}/investors/{user_id}")
async def remove_investor(startup_id: str, user_id: str, user=Depends(get_current_user)):
    """Remove an investor from startup"""
    requester = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not requester or requester["role"] != "founder":
        raise HTTPException(status_code=403, detail="Only founders can remove investors")
    
    await db.startup_members.delete_one({"startup_id": startup_id, "user_id": user_id, "role": "investor"})
    return {"success": True}

@api_router.get("/startups/{startup_id}/investor-view")
async def get_investor_view(startup_id: str, user=Depends(get_current_user)):
    """Special view for investors - shows financial summary and key metrics"""
    member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": user.id})
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    
    # Get startup info
    startup = await db.startups.find_one({"id": startup_id}, {"_id": 0})
    
    # Get financial data
    income = await db.income.find({"startup_id": startup_id}, {"_id": 0}).to_list(500)
    expenses = await db.expenses.find({"startup_id": startup_id}, {"_id": 0}).to_list(500)
    investments = await db.investments.find({"startup_id": startup_id}, {"_id": 0}).to_list(100)
    
    total_income = sum(i.get("amount", 0) for i in income)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    total_investments = sum(inv.get("amount", 0) for inv in investments)
    
    # Get team size
    members = await db.startup_members.find({"startup_id": startup_id}).to_list(100)
    
    # Get milestones progress
    milestones = await db.milestones.find({"startup_id": startup_id}, {"_id": 0}).to_list(50)
    completed_milestones = len([m for m in milestones if m.get("status") == "completed"])
    
    # Get tasks progress
    tasks = await db.tasks.find({"startup_id": startup_id}, {"_id": 0}).to_list(500)
    completed_tasks = len([t for t in tasks if t.get("status") == "done"])
    
    # Monthly burn rate
    from collections import defaultdict
    monthly_expenses = defaultdict(float)
    for e in expenses:
        month = e.get("date", "")[:7]
        if month:
            monthly_expenses[month] += e.get("amount", 0)
    
    avg_monthly_burn = sum(monthly_expenses.values()) / max(len(monthly_expenses), 1) if monthly_expenses else 0
    
    # Runway calculation
    current_balance = total_income + total_investments - total_expenses
    runway_months = round(current_balance / avg_monthly_burn, 1) if avg_monthly_burn > 0 else 0
    
    return {
        "startup": {
            "name": startup.get("name", ""),
            "industry": startup.get("industry", ""),
            "stage": startup.get("stage", ""),
            "description": startup.get("description", ""),
        },
        "financials": {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_investments": total_investments,
            "current_balance": current_balance,
            "avg_monthly_burn": round(avg_monthly_burn, 2),
            "runway_months": runway_months,
            "expenses_by_month": dict(sorted(monthly_expenses.items())[-6:]),  # Last 6 months
        },
        "metrics": {
            "team_size": len(members),
            "milestones_completed": completed_milestones,
            "milestones_total": len(milestones),
            "tasks_completed": completed_tasks,
            "tasks_total": len(tasks),
        },
        "investments": investments,
    }

# ==================== DEMO MODE ====================

DEMO_EMAIL = "demo@startupops.io"
DEMO_PASSWORD = "DemoUser2026!"

@api_router.post("/demo/setup")
async def setup_demo():
    """Create a demo user with pre-populated sample data"""
    try:
        # Try to create demo user via Supabase admin API
        try:
            user_response = supabase_client.auth.admin.create_user({
                "email": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
                "email_confirm": True,
                "user_metadata": {"full_name": "Demo Founder"}
            })
            demo_user_id = user_response.user.id
        except Exception:
            # User might already exist - try signing in to get their ID
            try:
                sign_in = supabase_client.auth.sign_in_with_password({
                    "email": DEMO_EMAIL,
                    "password": DEMO_PASSWORD
                })
                demo_user_id = sign_in.user.id
            except Exception:
                # Last resort: look up in profiles
                existing = await db.profiles.find_one({"email": DEMO_EMAIL}, {"_id": 0})
                if existing:
                    demo_user_id = existing["id"]
                else:
                    raise HTTPException(status_code=500, detail="Could not create demo user")

        # Create/update profile
        existing_profile = await db.profiles.find_one({"id": demo_user_id})
        if not existing_profile:
            profile = {
                "id": demo_user_id,
                "email": DEMO_EMAIL,
                "full_name": "Demo Founder",
                "avatar_url": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.profiles.insert_one(profile)

        # Check if demo startup already exists
        existing_startup = await db.startups.find_one({"founder_id": demo_user_id, "name": "NexaFlow AI"})
        if existing_startup:
            return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "message": "Demo ready"}

        # Check if demo invite code already exists (from previous run with different user)
        existing_invite = await db.startups.find_one({"invite_code": "DEMO2026"})
        if existing_invite:
            # Delete the old demo data to start fresh
            await db.startups.delete_one({"invite_code": "DEMO2026"})
            await db.startup_members.delete_many({"startup_id": existing_invite["id"]})
            await db.tasks.delete_many({"startup_id": existing_invite["id"]})
            await db.milestones.delete_many({"startup_id": existing_invite["id"]})
            await db.feedback.delete_many({"startup_id": existing_invite["id"]})
            await db.subscriptions.delete_many({"startup_id": existing_invite["id"]})

        # Create demo startup
        startup_id = str(uuid.uuid4())
        invite_code = "DEMO2026"
        startup = {
            "id": startup_id,
            "name": "NexaFlow AI",
            "description": "AI-powered workflow automation platform that helps mid-market companies reduce manual processes by 70% through intelligent document processing and task routing.",
            "industry": "ai_ml",
            "stage": "mvp",
            "website": "https://nexaflow.ai",
            "founder_id": demo_user_id,
            "invite_code": invite_code,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.startups.insert_one(startup)

        # Create founder membership
        await db.startup_members.insert_one({
            "id": str(uuid.uuid4()), "startup_id": startup_id,
            "user_id": demo_user_id, "role": "founder",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        })

        # Create demo team members as profiles + memberships
        team_data = [
            {"name": "Arjun Mehta", "email": "arjun@nexaflow.ai", "role": "member"},
            {"name": "Priya Sharma", "email": "priya@nexaflow.ai", "role": "member"},
            {"name": "Vikram Patel", "email": "vikram@nexaflow.ai", "role": "member"},
        ]
        for tm in team_data:
            tm_id = str(uuid.uuid4())
            await db.profiles.update_one(
                {"email": tm["email"]},
                {"$setOnInsert": {"id": tm_id, "email": tm["email"], "full_name": tm["name"], "avatar_url": "", "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
            member_profile = await db.profiles.find_one({"email": tm["email"]}, {"_id": 0})
            existing_member = await db.startup_members.find_one({"startup_id": startup_id, "user_id": member_profile["id"]})
            if not existing_member:
                await db.startup_members.insert_one({
                    "id": str(uuid.uuid4()), "startup_id": startup_id,
                    "user_id": member_profile["id"], "role": tm["role"],
                    "joined_at": datetime.now(timezone.utc).isoformat(),
                })

        # Get team member IDs for assignment
        all_members = await db.startup_members.find({"startup_id": startup_id}, {"_id": 0}).to_list(20)
        member_ids = [m["user_id"] for m in all_members]

        # Create demo milestones
        milestones_data = [
            {"title": "MVP Launch", "description": "Ship core AI document processing engine with basic UI", "target_date": "2026-03-15", "status": "in_progress"},
            {"title": "Beta Program", "description": "Onboard 20 pilot customers for feedback and validation", "target_date": "2026-05-01", "status": "pending"},
            {"title": "Series A Prep", "description": "Reach $50K MRR and prepare investor deck for fundraising", "target_date": "2026-08-01", "status": "pending"},
            {"title": "Market Validation", "description": "Conduct 50+ customer interviews and validate product-market fit", "target_date": "2026-02-28", "status": "completed"},
        ]
        milestone_ids = []
        for md in milestones_data:
            m_id = str(uuid.uuid4())
            milestone_ids.append(m_id)
            await db.milestones.insert_one({
                "id": m_id, "startup_id": startup_id,
                "title": md["title"], "description": md["description"],
                "target_date": md["target_date"], "status": md["status"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

        # Create demo tasks
        tasks_data = [
            {"title": "Design system architecture", "description": "Create microservices architecture diagram and API specs", "status": "done", "priority": "high", "milestone_id": milestone_ids[0]},
            {"title": "Build document parser", "description": "Implement PDF/DOCX parser using AI extraction", "status": "done", "priority": "high", "milestone_id": milestone_ids[0]},
            {"title": "Create REST API", "description": "Build FastAPI endpoints for document upload and processing", "status": "done", "priority": "high", "milestone_id": milestone_ids[0]},
            {"title": "Setup CI/CD pipeline", "description": "Configure GitHub Actions with automated testing and deployment", "status": "done", "priority": "medium", "milestone_id": milestone_ids[0]},
            {"title": "Build dashboard UI", "description": "React dashboard with document processing status and analytics", "status": "in_progress", "priority": "high", "milestone_id": milestone_ids[0]},
            {"title": "Implement user auth", "description": "OAuth2 + JWT authentication with role-based access control", "status": "done", "priority": "urgent", "milestone_id": milestone_ids[0]},
            {"title": "Write API documentation", "description": "OpenAPI/Swagger docs for all endpoints", "status": "in_progress", "priority": "medium", "milestone_id": milestone_ids[0]},
            {"title": "Create landing page", "description": "Marketing site with product demo video and signup flow", "status": "review", "priority": "medium", "milestone_id": milestone_ids[1]},
            {"title": "Beta onboarding flow", "description": "Self-serve onboarding wizard for new pilot customers", "status": "in_progress", "priority": "high", "milestone_id": milestone_ids[1]},
            {"title": "Customer feedback system", "description": "In-app feedback widget + NPS survey integration", "status": "todo", "priority": "medium", "milestone_id": milestone_ids[1]},
            {"title": "Usage analytics dashboard", "description": "Track document processing volume, user engagement metrics", "status": "todo", "priority": "medium", "milestone_id": milestone_ids[1]},
            {"title": "Pricing page design", "description": "Design and implement tiered pricing with feature comparison", "status": "review", "priority": "high", "milestone_id": milestone_ids[2]},
            {"title": "Financial model update", "description": "Update revenue projections with beta customer data", "status": "todo", "priority": "high", "milestone_id": milestone_ids[2]},
            {"title": "Investor pitch deck", "description": "Create 15-slide pitch deck with traction metrics", "status": "todo", "priority": "urgent", "milestone_id": milestone_ids[2]},
            {"title": "Competitive analysis", "description": "Deep-dive into competitors: DocuSign AI, Automation Anywhere", "status": "done", "priority": "medium", "milestone_id": milestone_ids[3]},
            {"title": "Customer interviews", "description": "Conduct 50 structured interviews with target personas", "status": "done", "priority": "high", "milestone_id": milestone_ids[3]},
            {"title": "Market sizing research", "description": "Calculate TAM/SAM/SOM for AI workflow automation", "status": "done", "priority": "medium", "milestone_id": milestone_ids[3]},
            {"title": "Setup error monitoring", "description": "Integrate Sentry for error tracking and alerting", "status": "todo", "priority": "low", "milestone_id": milestone_ids[0]},
            {"title": "Performance optimization", "description": "Optimize document processing to under 3s per page", "status": "todo", "priority": "medium", "milestone_id": milestone_ids[0]},
            {"title": "Security audit", "description": "Run OWASP security scan and fix vulnerabilities", "status": "todo", "priority": "urgent", "milestone_id": milestone_ids[1]},
        ]
        for i, td in enumerate(tasks_data):
            await db.tasks.insert_one({
                "id": str(uuid.uuid4()), "startup_id": startup_id,
                "title": td["title"], "description": td["description"],
                "status": td["status"], "priority": td["priority"],
                "assigned_to": member_ids[i % len(member_ids)],
                "created_by": demo_user_id,
                "milestone_id": td.get("milestone_id"),
                "due_date": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

        # Create demo feedback
        feedback_data = [
            {"title": "Document parsing accuracy impressive", "content": "Tested with 100 invoices, 97% accuracy rate on field extraction. Better than manual processing.", "category": "product", "rating": 5, "source": "external"},
            {"title": "UI needs dark mode", "content": "Several users requested dark mode support for the dashboard. Current white theme causes eye strain.", "category": "product", "rating": 3, "source": "internal"},
            {"title": "Integration with Slack needed", "content": "Most target customers use Slack. They want notifications when documents are processed.", "category": "technical", "rating": 4, "source": "external"},
            {"title": "Pricing seems competitive", "content": "Compared to Automation Anywhere ($40K/yr), our $199/mo is very attractive to mid-market.", "category": "business", "rating": 5, "source": "internal"},
            {"title": "Onboarding takes too long", "content": "Average time to first document processed is 25 minutes. Target should be under 5 minutes.", "category": "product", "rating": 2, "source": "external"},
            {"title": "Enterprise security requirements", "content": "Three enterprise leads require SOC2 compliance before signing. Need to prioritize.", "category": "business", "rating": 3, "source": "external"},
            {"title": "Mobile responsiveness lacking", "content": "Dashboard doesn't work well on tablets. Operations managers need mobile access.", "category": "technical", "rating": 2, "source": "internal"},
            {"title": "Great customer discovery insights", "content": "Interviews revealed pain point: 60% of time spent on manual document routing between departments.", "category": "market", "rating": 5, "source": "internal"},
            {"title": "API response time concerns", "content": "Batch processing of 50+ documents causes timeout. Need queue-based architecture.", "category": "technical", "rating": 3, "source": "internal"},
            {"title": "Competitor just raised Series B", "content": "DocFlow AI raised $25M. We need to move faster on key differentiators.", "category": "market", "rating": 4, "source": "internal"},
        ]
        for fd in feedback_data:
            await db.feedback.insert_one({
                "id": str(uuid.uuid4()), "startup_id": startup_id,
                "title": fd["title"], "content": fd["content"],
                "category": fd["category"], "rating": fd["rating"],
                "submitted_by": member_ids[feedback_data.index(fd) % len(member_ids)],
                "source": fd["source"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        # Create demo subscription
        await db.subscriptions.insert_one({
            "id": str(uuid.uuid4()), "startup_id": startup_id,
            "plan": "pro", "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "message": "Demo ready"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Demo setup error: {e}")
        raise HTTPException(status_code=500, detail=f"Demo setup failed: {str(e)}")

# ==================== APP SETUP ====================



# CORS Configuration - Allow Vercel frontend and local development
cors_origins_env = os.environ.get('CORS_ORIGINS', '*')
default_origins = [
    "https://startup-gamma-seven.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

if cors_origins_env == '*':
    cors_origins = ['*']
else:
    cors_origins = []
    for origin in cors_origins_env.split(','):
        origin = origin.strip()
        if origin:
            cors_origins.append(origin)
    # Also add defaults if not already present
    for default in default_origins:
        if default not in cors_origins:
            cors_origins.append(default)

logger.info(f"CORS origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins if cors_origins else ['*'],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    logger.info("StartupOps API starting up...")
    try:
        await db.profiles.create_index("id", unique=True)
        await db.startups.create_index("id", unique=True)
        await db.startups.create_index("invite_code", unique=True)
        await db.startup_members.create_index([("startup_id", 1), ("user_id", 1)], unique=True)
        await db.tasks.create_index("id", unique=True)
        await db.tasks.create_index("startup_id")
        await db.milestones.create_index("id", unique=True)
        await db.milestones.create_index("startup_id")
        await db.feedback.create_index("startup_id")
        await db.subscriptions.create_index("startup_id")
        logger.info("Database indexes created")
    except Exception as e:
        # Indexes may already exist, log and continue
        logger.warning(f"Index creation warning (may already exist): {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
