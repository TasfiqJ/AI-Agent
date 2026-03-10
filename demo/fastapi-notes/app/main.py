"""FastAPI Notes API — demo target for test-guardian evaluation."""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Notes API", version="1.0.0")

# In-memory store
_notes: list[dict] = []
_next_id = 1


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


@app.get("/api/notes")
async def list_notes(
    tag: str | None = Query(None, description="Filter by tag"),
    limit: int = Query(50, ge=1, le=100),
):
    """List all notes. Supports filtering by tag."""
    notes = _notes
    if tag:
        notes = [n for n in notes if tag in n.get("tags", [])]
    return {"notes": notes[:limit], "count": len(notes[:limit])}


@app.post("/api/notes", status_code=201)
async def create_note(note: NoteCreate):
    """Create a new note."""
    global _next_id
    new_note = {
        "id": _next_id,
        "title": note.title,
        "content": note.content,
        "tags": note.tags,
    }
    _next_id += 1
    _notes.append(new_note)
    return new_note


@app.get("/api/notes/{note_id}")
async def get_note(note_id: int):
    """Get a single note by ID."""
    note = next((n for n in _notes if n["id"] == note_id), None)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.put("/api/notes/{note_id}")
async def update_note(note_id: int, update: NoteUpdate):
    """Update an existing note."""
    note = next((n for n in _notes if n["id"] == note_id), None)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if update.title is not None:
        note["title"] = update.title
    if update.content is not None:
        note["content"] = update.content
    if update.tags is not None:
        note["tags"] = update.tags

    return note


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: int):
    """Delete a note."""
    global _notes
    original_len = len(_notes)
    _notes = [n for n in _notes if n["id"] != note_id]
    if len(_notes) == original_len:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Deleted"}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "fastapi-notes"}
