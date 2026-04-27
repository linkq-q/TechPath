# 文件用途：数据库初始化和 CRUD 操作，使用 SQLAlchemy 管理 SQLite（Phase 1 + Phase 2）

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, Text, create_engine, or_
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 数据库文件路径
DB_PATH = Path(__file__).parent.parent / "data" / "techpath.db"
DB_URL = f"sqlite:///{DB_PATH}"

engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


class KnowledgeItem(Base):
    """知识库条目"""
    __tablename__ = "knowledge_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    content_summary = Column(Text)
    full_text = Column(Text)
    source_type = Column(Text)  # github / video / article / text
    source_url = Column(Text)
    tags = Column(Text)  # JSON 字符串，如 '["python", "ai"]'
    created_at = Column(DateTime, default=datetime.utcnow)


class ExamSession(Base):
    """检验会话记录"""
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_item_ids = Column(Text)  # JSON 字符串
    questions_json = Column(Text)
    answers_json = Column(Text)
    report_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    """对话历史记录"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Text)
    role = Column(Text)  # user / assistant / tool
    content = Column(Text)
    tool_calls_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class JdRecord(Base):
    """岗位 JD 爬取记录"""
    __tablename__ = "jd_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text)           # bosszp / niuke / zhihu
    company = Column(Text)
    title = Column(Text)
    location = Column(Text)
    requirements_raw = Column(Text)   # 原始 JD 文本
    skills_extracted = Column(Text)   # JSON 字符串，提取的技能列表
    crawled_at = Column(DateTime, default=datetime.utcnow)


class JdAnalysis(Base):
    """JD 情报分析结果"""
    __tablename__ = "jd_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(DateTime, default=datetime.utcnow)
    top_skills_json = Column(Text)     # JSON: [{"skill": "python", "count": 15}, ...]
    new_keywords_json = Column(Text)   # JSON: ["新关键词1", ...]
    trend_changes = Column(Text)       # 文字描述趋势变化
    sample_count = Column(Integer)


def init_db() -> None:
    """初始化数据库，创建表结构（如不存在则创建）"""
    global engine, SessionLocal
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _get_session() -> Session:
    """获取数据库会话"""
    if SessionLocal is None:
        init_db()
    return SessionLocal()


# ---------- KnowledgeItem CRUD ----------

def save_knowledge_item(
    title: str,
    content_summary: str,
    full_text: str,
    source_type: str,
    source_url: str = "",
    tags: list = None,
) -> int:
    """保存一条知识库条目，返回新记录的 id"""
    with _get_session() as session:
        item = KnowledgeItem(
            title=title,
            content_summary=content_summary,
            full_text=full_text,
            source_type=source_type,
            source_url=source_url,
            tags=json.dumps(tags or [], ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item.id


def get_all_knowledge_items() -> list[dict]:
    """获取所有知识库条目，按创建时间倒序"""
    with _get_session() as session:
        items = (
            session.query(KnowledgeItem)
            .order_by(KnowledgeItem.created_at.desc())
            .all()
        )
        return [_item_to_dict(i) for i in items]


def delete_knowledge_item(item_id: int) -> bool:
    """删除指定 id 的知识库条目，返回是否成功"""
    with _get_session() as session:
        item = session.query(KnowledgeItem).filter(KnowledgeItem.id == item_id).first()
        if item is None:
            return False
        session.delete(item)
        session.commit()
        return True


def search_knowledge_items(query: str) -> list[dict]:
    """关键词搜索知识库（title / content_summary / tags），最多返回 5 条"""
    with _get_session() as session:
        pattern = f"%{query}%"
        items = (
            session.query(KnowledgeItem)
            .filter(
                or_(
                    KnowledgeItem.title.like(pattern),
                    KnowledgeItem.content_summary.like(pattern),
                    KnowledgeItem.tags.like(pattern),
                )
            )
            .limit(5)
            .all()
        )
        return [_item_to_dict(i) for i in items]


def _item_to_dict(item: KnowledgeItem) -> dict:
    """将 ORM 对象转换为字典"""
    return {
        "id": item.id,
        "title": item.title,
        "content_summary": item.content_summary,
        "full_text": item.full_text,
        "source_type": item.source_type,
        "source_url": item.source_url,
        "tags": json.loads(item.tags) if item.tags else [],
        "created_at": item.created_at.isoformat() if item.created_at else "",
    }


# ---------- ExamSession CRUD ----------

def save_exam_session(
    knowledge_item_ids: list,
    questions_json: str = "",
    answers_json: str = "",
    report_json: str = "",
) -> int:
    """保存检验会话记录，返回新记录的 id"""
    with _get_session() as session:
        exam = ExamSession(
            knowledge_item_ids=json.dumps(knowledge_item_ids, ensure_ascii=False),
            questions_json=questions_json,
            answers_json=answers_json,
            report_json=report_json,
            created_at=datetime.utcnow(),
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)
        return exam.id


# ---------- Conversation CRUD ----------

def save_conversation(
    session_id: str,
    role: str,
    content: str,
    tool_calls_json: str = "",
) -> int:
    """保存一条对话记录，返回新记录的 id"""
    with _get_session() as session:
        conv = Conversation(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls_json=tool_calls_json,
            created_at=datetime.utcnow(),
        )
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return conv.id


def get_conversations(session_id: str) -> list[dict]:
    """获取指定会话的所有对话记录，按时间顺序"""
    with _get_session() as session:
        convs = (
            session.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.created_at.asc())
            .all()
        )
        return [
            {
                "id": c.id,
                "session_id": c.session_id,
                "role": c.role,
                "content": c.content,
                "tool_calls_json": c.tool_calls_json,
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in convs
        ]


# ---------- JdRecord CRUD ----------

def save_jd_record(
    platform: str,
    company: str,
    title: str,
    location: str,
    requirements_raw: str,
    skills_extracted: list = None,
) -> int:
    """保存一条 JD 爬取记录，返回新记录的 id"""
    with _get_session() as session:
        record = JdRecord(
            platform=platform,
            company=company,
            title=title,
            location=location,
            requirements_raw=requirements_raw,
            skills_extracted=json.dumps(skills_extracted or [], ensure_ascii=False),
            crawled_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def get_all_jd_records(limit: int = 200) -> list[dict]:
    """获取所有 JD 记录，按爬取时间倒序"""
    with _get_session() as session:
        records = (
            session.query(JdRecord)
            .order_by(JdRecord.crawled_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "platform": r.platform,
                "company": r.company,
                "title": r.title,
                "location": r.location,
                "requirements_raw": r.requirements_raw,
                "skills_extracted": json.loads(r.skills_extracted) if r.skills_extracted else [],
                "crawled_at": r.crawled_at.isoformat() if r.crawled_at else "",
            }
            for r in records
        ]


# ---------- JdAnalysis CRUD ----------

def save_jd_analysis(
    top_skills_json: str,
    new_keywords_json: str,
    trend_changes: str,
    sample_count: int,
) -> int:
    """保存一次 JD 分析结果，返回新记录的 id"""
    with _get_session() as session:
        analysis = JdAnalysis(
            analysis_date=datetime.utcnow(),
            top_skills_json=top_skills_json,
            new_keywords_json=new_keywords_json,
            trend_changes=trend_changes,
            sample_count=sample_count,
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
        return analysis.id


def get_latest_jd_analysis(n: int = 3) -> list[dict]:
    """获取最近 n 次 JD 分析结果"""
    with _get_session() as session:
        analyses = (
            session.query(JdAnalysis)
            .order_by(JdAnalysis.analysis_date.desc())
            .limit(n)
            .all()
        )
        return [
            {
                "id": a.id,
                "analysis_date": a.analysis_date.isoformat() if a.analysis_date else "",
                "top_skills": json.loads(a.top_skills_json) if a.top_skills_json else [],
                "new_keywords": json.loads(a.new_keywords_json) if a.new_keywords_json else [],
                "trend_changes": a.trend_changes or "",
                "sample_count": a.sample_count or 0,
            }
            for a in analyses
        ]
