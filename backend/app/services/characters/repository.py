from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.models.characters import ChapterCharacterState


class CharacterStateRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.row_factory = sqlite3.Row
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS character_review_state (
                    chapter_id TEXT PRIMARY KEY,
                    chapter_content_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    state_json TEXT NOT NULL
                )
                """
            )

    def load(self, chapter_id: str) -> ChapterCharacterState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT state_json
                FROM character_review_state
                WHERE chapter_id = ?
                """,
                (chapter_id,),
            ).fetchone()
        if row is None:
            return None
        return ChapterCharacterState.model_validate_json(row["state_json"])

    def save(self, state: ChapterCharacterState) -> ChapterCharacterState:
        payload = state.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO character_review_state (
                    chapter_id,
                    chapter_content_hash,
                    updated_at,
                    state_json
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chapter_id) DO UPDATE SET
                    chapter_content_hash = excluded.chapter_content_hash,
                    updated_at = excluded.updated_at,
                    state_json = excluded.state_json
                """,
                (
                    state.chapterId,
                    state.chapterContentHash,
                    state.updatedAt,
                    payload,
                ),
            )
        return state
