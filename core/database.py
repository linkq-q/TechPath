# 文件用途：数据库初始化和 CRUD 操作，使用 SQLAlchemy 管理 SQLite（Phase 1 + Phase 2 + Phase 3 + Phase 4）

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


class StudySession(Base):
    """带学会话记录（Phase 3）"""
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mode = Column(Text)          # repo_analysis / topic_explain / learning_path
    input_content = Column(Text) # 用户输入的内容（URL/话题/目标岗位）
    report_json = Column(Text)   # 生成报告的 JSON 字符串
    created_at = Column(DateTime, default=datetime.utcnow)


class BilibiliPortfolio(Base):
    """B站竞品作品集记录（Phase 3）"""
    __tablename__ = "bilibili_portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_url = Column(Text)
    uploader = Column(Text)
    title = Column(Text)
    publish_date = Column(Text)
    cohort = Column(Text)        # 届别，如 2026届
    stage = Column(Text)         # 求职阶段：实习 / 秋招
    tech_tags = Column(Text)     # JSON 字符串，技术标签列表
    grade = Column(Text)         # S / A / B / C
    score = Column(Text)         # 综合评分（数字字符串）
    analyzed_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# Phase 4 新增表：学习历史 / 知识节点 / 技能注册表
# ============================================================

class LearningHistory(Base):
    """完整学习历史记录（Phase 4）"""
    __tablename__ = "learning_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_type = Column(Text)       # repo_analysis / topic_explain / learning_path / exam
    title = Column(Text)
    input_content = Column(Text)
    full_report = Column(Text)        # 完整报告 Markdown
    qa_history = Column(Text)         # JSON 字符串，问答记录列表
    knowledge_tags = Column(Text)     # JSON 字符串，相关知识点标签
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeNode(Base):
    """知识网络节点（Phase 4）"""
    __tablename__ = "knowledge_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)         # 知识点名称
    category = Column(Text)                     # 分类：渲染/AIGC/工具/编程
    description = Column(Text)                  # 一句话描述
    related_nodes = Column(Text)                # JSON：相关知识点名称列表
    source_history_ids = Column(Text)           # JSON：来源学习历史 id 列表
    mastery_level = Column(Integer, default=0)  # 0-100 掌握度
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SkillsRegistry(Base):
    """Agent Skill 注册表（Phase 4）"""
    __tablename__ = "skills_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    description = Column(Text)
    trigger_keywords = Column(Text)   # JSON 字符串
    content_path = Column(Text)       # .skill.md 文件路径
    metadata_json = Column(Text)      # 完整 YAML frontmatter
    is_active = Column(Integer, default=1)  # 0=禁用 1=启用
    created_at = Column(DateTime, default=datetime.utcnow)


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


# ---------- StudySession CRUD ----------

def save_study_session(
    mode: str,
    input_content: str,
    report_json: str,
) -> int:
    """保存一条带学会话记录，返回新记录的 id"""
    with _get_session() as session:
        record = StudySession(
            mode=mode,
            input_content=input_content,
            report_json=report_json,
            created_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def get_study_sessions(mode: str = "", limit: int = 20) -> list[dict]:
    """获取带学会话记录，可按 mode 过滤"""
    with _get_session() as session:
        q = session.query(StudySession).order_by(StudySession.created_at.desc())
        if mode:
            q = q.filter(StudySession.mode == mode)
        records = q.limit(limit).all()
        return [
            {
                "id": r.id,
                "mode": r.mode,
                "input_content": r.input_content,
                "report_json": r.report_json,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ]


# ---------- BilibiliPortfolio CRUD ----------

def save_bilibili_portfolio(
    video_url: str,
    uploader: str,
    title: str,
    publish_date: str,
    cohort: str,
    stage: str,
    tech_tags: list,
    grade: str = "",
    score: str = "",
) -> int:
    """保存一条 B站作品集记录，返回新记录的 id"""
    with _get_session() as session:
        record = BilibiliPortfolio(
            video_url=video_url,
            uploader=uploader,
            title=title,
            publish_date=publish_date,
            cohort=cohort,
            stage=stage,
            tech_tags=json.dumps(tech_tags or [], ensure_ascii=False),
            grade=grade,
            score=score,
            analyzed_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def get_bilibili_portfolios(
    cohort: str = "",
    stage: str = "",
    grade: str = "",
    limit: int = 200,
) -> list[dict]:
    """获取 B站作品集记录，支持按届别/阶段/评级过滤"""
    with _get_session() as session:
        q = session.query(BilibiliPortfolio).order_by(BilibiliPortfolio.analyzed_at.desc())
        if cohort:
            q = q.filter(BilibiliPortfolio.cohort == cohort)
        if stage:
            q = q.filter(BilibiliPortfolio.stage == stage)
        if grade:
            q = q.filter(BilibiliPortfolio.grade == grade)
        records = q.limit(limit).all()
        return [_portfolio_to_dict(r) for r in records]


def get_portfolio_stats() -> dict:
    """获取作品集统计数据：总数、各评级数量、最近分析时间"""
    with _get_session() as session:
        total = session.query(BilibiliPortfolio).count()
        grade_counts = {}
        for g in ["S", "A", "B", "C"]:
            grade_counts[g] = (
                session.query(BilibiliPortfolio)
                .filter(BilibiliPortfolio.grade == g)
                .count()
            )
        latest = (
            session.query(BilibiliPortfolio)
            .order_by(BilibiliPortfolio.analyzed_at.desc())
            .first()
        )
        return {
            "total": total,
            "grade_counts": grade_counts,
            "last_analyzed": latest.analyzed_at.isoformat() if latest and latest.analyzed_at else "",
        }


def update_portfolio_grade(video_url: str, grade: str, score: str) -> bool:
    """更新指定视频的评级结果"""
    with _get_session() as session:
        record = (
            session.query(BilibiliPortfolio)
            .filter(BilibiliPortfolio.video_url == video_url)
            .first()
        )
        if record is None:
            return False
        record.grade = grade
        record.score = score
        session.commit()
        return True


def _portfolio_to_dict(record: BilibiliPortfolio) -> dict:
    """将 ORM 对象转换为字典"""
    return {
        "id": record.id,
        "video_url": record.video_url,
        "uploader": record.uploader,
        "title": record.title,
        "publish_date": record.publish_date,
        "cohort": record.cohort,
        "stage": record.stage,
        "tech_tags": json.loads(record.tech_tags) if record.tech_tags else [],
        "grade": record.grade,
        "score": record.score,
        "analyzed_at": record.analyzed_at.isoformat() if record.analyzed_at else "",
    }


# ---------- LearningHistory CRUD ----------

def save_learning_history(
    session_type: str,
    title: str,
    input_content: str,
    full_report: str,
    qa_history: list = None,
    knowledge_tags: list = None,
) -> int:
    """保存完整学习历史记录，返回新记录的 id"""
    with _get_session() as session:
        record = LearningHistory(
            session_type=session_type,
            title=title,
            input_content=input_content,
            full_report=full_report,
            qa_history=json.dumps(qa_history or [], ensure_ascii=False),
            knowledge_tags=json.dumps(knowledge_tags or [], ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def get_learning_histories(session_type: str = None, limit: int = 50) -> list[dict]:
    """获取学习历史列表（不含 full_report），支持按类型过滤"""
    with _get_session() as session:
        q = session.query(LearningHistory).order_by(LearningHistory.created_at.desc())
        if session_type:
            q = q.filter(LearningHistory.session_type == session_type)
        records = q.limit(limit).all()
        return [
            {
                "id": r.id,
                "session_type": r.session_type,
                "title": r.title,
                "input_content": r.input_content,
                "knowledge_tags": json.loads(r.knowledge_tags) if r.knowledge_tags else [],
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ]


def get_learning_history_by_id(history_id: int) -> dict | None:
    """获取单条完整学习历史记录"""
    with _get_session() as session:
        r = session.query(LearningHistory).filter(LearningHistory.id == history_id).first()
        if r is None:
            return None
        return {
            "id": r.id,
            "session_type": r.session_type,
            "title": r.title,
            "input_content": r.input_content,
            "full_report": r.full_report,
            "qa_history": json.loads(r.qa_history) if r.qa_history else [],
            "knowledge_tags": json.loads(r.knowledge_tags) if r.knowledge_tags else [],
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }


# ---------- KnowledgeNode CRUD ----------

def save_knowledge_node(
    name: str,
    category: str = "",
    description: str = "",
    related_nodes: list = None,
    source_history_ids: list = None,
    mastery_level: int = 0,
) -> int:
    """新增知识节点，返回新记录的 id"""
    with _get_session() as session:
        node = KnowledgeNode(
            name=name,
            category=category,
            description=description,
            related_nodes=json.dumps(related_nodes or [], ensure_ascii=False),
            source_history_ids=json.dumps(source_history_ids or [], ensure_ascii=False),
            mastery_level=mastery_level,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(node)
        session.commit()
        session.refresh(node)
        return node.id


def get_all_knowledge_nodes() -> list[dict]:
    """获取所有知识节点"""
    with _get_session() as session:
        nodes = session.query(KnowledgeNode).order_by(KnowledgeNode.name).all()
        return [_node_to_dict(n) for n in nodes]


def get_knowledge_node_by_name(name: str) -> dict | None:
    """按名称查找知识节点"""
    with _get_session() as session:
        node = session.query(KnowledgeNode).filter(KnowledgeNode.name == name).first()
        return _node_to_dict(node) if node else None


def update_knowledge_node(
    name: str,
    category: str = None,
    description: str = None,
    related_nodes: list = None,
    source_history_ids: list = None,
    mastery_level: int = None,
) -> bool:
    """更新指定名称的知识节点，返回是否成功"""
    with _get_session() as session:
        node = session.query(KnowledgeNode).filter(KnowledgeNode.name == name).first()
        if node is None:
            return False
        if category is not None:
            node.category = category
        if description is not None:
            node.description = description
        if related_nodes is not None:
            node.related_nodes = json.dumps(related_nodes, ensure_ascii=False)
        if source_history_ids is not None:
            # 合并已有 id 列表
            existing = json.loads(node.source_history_ids) if node.source_history_ids else []
            merged = list(dict.fromkeys(existing + source_history_ids))
            node.source_history_ids = json.dumps(merged, ensure_ascii=False)
        if mastery_level is not None:
            node.mastery_level = max(0, min(100, mastery_level))
        node.updated_at = datetime.utcnow()
        session.commit()
        return True


def _node_to_dict(node: KnowledgeNode) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "category": node.category or "",
        "description": node.description or "",
        "related_nodes": json.loads(node.related_nodes) if node.related_nodes else [],
        "source_history_ids": json.loads(node.source_history_ids) if node.source_history_ids else [],
        "mastery_level": node.mastery_level or 0,
        "created_at": node.created_at.isoformat() if node.created_at else "",
        "updated_at": node.updated_at.isoformat() if node.updated_at else "",
    }


# ---------- SkillsRegistry CRUD ----------

def save_skill(
    name: str,
    description: str,
    trigger_keywords: list,
    content_path: str,
    metadata_json: str = "",
    is_active: int = 1,
) -> int:
    """注册一个 Skill，返回新记录的 id"""
    with _get_session() as session:
        # 如果已存在同名则更新
        existing = session.query(SkillsRegistry).filter(SkillsRegistry.name == name).first()
        if existing:
            existing.description = description
            existing.trigger_keywords = json.dumps(trigger_keywords, ensure_ascii=False)
            existing.content_path = content_path
            existing.metadata_json = metadata_json
            existing.is_active = is_active
            session.commit()
            return existing.id
        skill = SkillsRegistry(
            name=name,
            description=description,
            trigger_keywords=json.dumps(trigger_keywords, ensure_ascii=False),
            content_path=content_path,
            metadata_json=metadata_json,
            is_active=is_active,
            created_at=datetime.utcnow(),
        )
        session.add(skill)
        session.commit()
        session.refresh(skill)
        return skill.id


def get_all_skills() -> list[dict]:
    """获取所有已注册 Skill"""
    with _get_session() as session:
        skills = session.query(SkillsRegistry).order_by(SkillsRegistry.name).all()
        return [_skill_to_dict(s) for s in skills]


def toggle_skill(name: str, is_active: bool) -> bool:
    """启用或禁用指定 Skill"""
    with _get_session() as session:
        skill = session.query(SkillsRegistry).filter(SkillsRegistry.name == name).first()
        if skill is None:
            return False
        skill.is_active = 1 if is_active else 0
        session.commit()
        return True


def delete_skill(name: str) -> bool:
    """删除指定 Skill 注册记录"""
    with _get_session() as session:
        skill = session.query(SkillsRegistry).filter(SkillsRegistry.name == name).first()
        if skill is None:
            return False
        session.delete(skill)
        session.commit()
        return True


def _skill_to_dict(skill: SkillsRegistry) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description or "",
        "trigger_keywords": json.loads(skill.trigger_keywords) if skill.trigger_keywords else [],
        "content_path": skill.content_path or "",
        "metadata_json": skill.metadata_json or "",
        "is_active": bool(skill.is_active),
        "created_at": skill.created_at.isoformat() if skill.created_at else "",
    }


print("[database] 模块加载完成")
