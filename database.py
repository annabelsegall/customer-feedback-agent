from typing import Optional, Generator
from sqlmodel import Field, SQLModel, Session, create_engine

class TicketMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    whatsapp_number: str = Field(index=True)
    github_issue_id: int = Field(index=True)
    repo_name: str
    issue_title: str

sqlite_url = "sqlite:///database.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
